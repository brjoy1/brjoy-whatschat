"""
Webhook para receber mensagens do Evolution API.
Orquestra o fluxo de processamento de mensagens e extração de slots.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_slot_extractor
from app.services.slot_extractor import SlotExtractor
from app.models import Lead, WhatsAppSession, ConversationMessage, MessageRole, LeadStatus
from app.schemas import WebhookMessage, LeadImobiliaria
from app.core.security import encryption_manager
from datetime import datetime, timedelta
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter()


async def process_incoming_message(
    session_name: str,
    phone: str,
    message_text: str,
    message_id: str,
    db: Session,
    slot_extractor: SlotExtractor
):
    """
    Processa mensagem recebida e atualiza slots do lead.

    Args:
        session_name: Nome da sessão WhatsApp
        phone: Telefone do remetente
        message_text: Conteúdo da mensagem
        message_id: ID da mensagem no WhatsApp
        db: Sessão do banco
        slot_extractor: Extrator de slots
    """
    logger.info(f"📥 Processando mensagem de {phone}")

    # Buscar sessão
    session = db.query(WhatsAppSession).filter(
        WhatsAppSession.session_name == session_name
    ).first()

    if not session:
        logger.warning(f"⚠️ Sessão '{session_name}' não encontrada no banco")
        return

    # Criptografar telefone para busca
    try:
        encrypted_phone = encryption_manager.encrypt_phone(phone)
    except Exception as e:
        logger.error(f"❌ Erro ao criptografar telefone: {e}")
        return

    # Buscar ou criar lead
    lead = db.query(Lead).filter(
        Lead.session_id == session.id,
        Lead.phone == encrypted_phone
    ).first()

    if not lead:
        logger.info(f"✨ Novo lead: {phone}")
        lead = Lead(
            session_id=session.id,
            phone=encrypted_phone,
            status=LeadStatus.ACTIVE
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)

    # Verificar Shadow Mode
    if lead.shadow_mode:
        # Verificar se humano ainda está ativo (últimos 5 minutos)
        if lead.shadow_mode_since:
            time_since_shadow = datetime.utcnow() - lead.shadow_mode_since
            if time_since_shadow > timedelta(minutes=5):
                logger.info(f"🤖 Shadow mode expirou para lead {lead.id} - retomando IA")
                lead.shadow_mode = False
                lead.shadow_mode_since = None
                db.commit()
            else:
                logger.info(f"👤 Lead {lead.id} em shadow mode - IA pausada")
                return

    # Salvar mensagem do usuário
    user_message = ConversationMessage(
        lead_id=lead.id,
        role=MessageRole.USER,
        content=message_text,
        message_id=message_id
    )
    db.add(user_message)
    lead.total_messages += 1
    lead.last_interaction = datetime.utcnow()
    db.commit()

    # Buscar histórico de mensagens do usuário
    user_messages = db.query(ConversationMessage).filter(
        ConversationMessage.lead_id == lead.id,
        ConversationMessage.role == MessageRole.USER
    ).order_by(ConversationMessage.created_at.asc()).all()

    messages_text = [msg.content for msg in user_messages]

    # Extrair slots atuais
    current_slots = LeadImobiliaria(
        nome=lead.nome,
        telefone=phone,  # Usar não criptografado para extração
        email=encryption_manager.decrypt_email(lead.email) if lead.email else None,
        tipo_imovel=lead.tipo_imovel,
        finalidade=lead.finalidade,
        localizacao_desejada=lead.localizacao_desejada,
        num_quartos=lead.num_quartos,
        orcamento_min=lead.orcamento_min,
        orcamento_max=lead.orcamento_max,
        timeline=lead.timeline,
        observacoes=lead.observacoes
    )

    # Executar extração de slots
    logger.info(f"🧠 Extraindo slots para lead {lead.id}")
    updated_slots = await slot_extractor.extract_from_messages(messages_text, current_slots)

    # Atualizar lead com novos slots
    lead.nome = updated_slots.nome
    # Telefone já está salvo criptografado
    if updated_slots.email:
        lead.email = encryption_manager.encrypt_email(updated_slots.email)

    lead.tipo_imovel = updated_slots.tipo_imovel.value if updated_slots.tipo_imovel else None
    lead.finalidade = updated_slots.finalidade.value if updated_slots.finalidade else None
    lead.localizacao_desejada = updated_slots.localizacao_desejada
    lead.num_quartos = updated_slots.num_quartos
    lead.orcamento_min = updated_slots.orcamento_min
    lead.orcamento_max = updated_slots.orcamento_max
    lead.timeline = updated_slots.timeline.value if updated_slots.timeline else None
    lead.observacoes = updated_slots.observacoes

    # Atualizar métricas
    lead.slots_filled = updated_slots.slots_preenchidos()

    # Calcular score de qualificação (0-100)
    critical_filled = 4 - len(updated_slots.slots_criticos_faltando())
    qualification_score = (lead.slots_filled / 11) * 70 + (critical_filled / 4) * 30
    lead.qualification_score = round(qualification_score, 2)

    db.commit()
    db.refresh(lead)

    logger.info(f"✅ Lead {lead.id} atualizado: {lead.slots_filled}/11 slots, score {lead.qualification_score}")

    # Gerar próxima pergunta
    next_question = slot_extractor.get_next_question(updated_slots)

    if next_question:
        logger.info(f"❓ Próxima pergunta: {next_question}")

        # Salvar resposta da IA (será enviada via Celery)
        assistant_message = ConversationMessage(
            lead_id=lead.id,
            role=MessageRole.ASSISTANT,
            content=next_question
        )
        db.add(assistant_message)
        db.commit()

        # TODO FASE 4: Enfileirar envio via Celery com typing simulation
        # from app.tasks.message_tasks import send_message_with_humanization
        # send_message_with_humanization.delay(session_name, phone, next_question)

    else:
        # Lead completamente qualificado
        logger.info(f"🎉 Lead {lead.id} completamente qualificado!")
        lead.status = LeadStatus.QUALIFIED

        # Mensagem final
        final_message = (
            f"Perfeito, {lead.nome}! 🎉\n\n"
            "Tenho todas as informações necessárias. Nossa equipe entrará em contato "
            "em breve com opções personalizadas para você.\n\n"
            "Muito obrigado!"
        )

        assistant_message = ConversationMessage(
            lead_id=lead.id,
            role=MessageRole.ASSISTANT,
            content=final_message
        )
        db.add(assistant_message)
        db.commit()

        # TODO FASE 4: Enviar via Celery
        # send_message_with_humanization.delay(session_name, phone, final_message)


@router.post("/webhook")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    slot_extractor: SlotExtractor = Depends(get_slot_extractor)
):
    """
    Recebe webhooks do Evolution API.

    Processa eventos de mensagens recebidas e atualiza slots dos leads.

    Args:
        request: Request do FastAPI
        background_tasks: Tasks em background
        db: Sessão do banco
        slot_extractor: Extrator de slots

    Returns:
        dict: Confirmação de recebimento
    """
    try:
        # Parse body
        body = await request.json()
        logger.debug(f"📨 Webhook recebido: {json.dumps(body, indent=2)}")

        # Extrair dados do webhook
        event = body.get("event")
        instance = body.get("instance")
        data = body.get("data", {})

        # Processar apenas mensagens recebidas
        if event != "messages.upsert":
            logger.debug(f"Ignorando evento '{event}'")
            return {"status": "ignored", "reason": f"Event '{event}' not handled"}

        # Verificar se é mensagem de entrada (não enviada por nós)
        key = data.get("key", {})
        from_me = key.get("fromMe", False)

        if from_me:
            logger.debug("Ignorando mensagem enviada por nós")
            return {"status": "ignored", "reason": "Message from me"}

        # Extrair informações da mensagem
        message = data.get("message", {})
        conversation_text = (
            message.get("conversation") or
            message.get("extendedTextMessage", {}).get("text") or
            ""
        )

        if not conversation_text:
            logger.debug("Mensagem sem texto - ignorando")
            return {"status": "ignored", "reason": "No text content"}

        remote_jid = key.get("remoteJid", "")
        phone = remote_jid.replace("@s.whatsapp.net", "")
        message_id = key.get("id", "")

        # Processar em background
        background_tasks.add_task(
            process_incoming_message,
            instance,
            phone,
            conversation_text,
            message_id,
            db,
            slot_extractor
        )

        logger.info(f"✅ Mensagem de {phone} enfileirada para processamento")

        return {
            "status": "success",
            "message": "Webhook received and queued"
        }

    except Exception as e:
        logger.error(f"❌ Erro ao processar webhook: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

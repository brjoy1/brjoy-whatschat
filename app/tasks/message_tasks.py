"""
Tasks assíncronas para processamento de mensagens com Celery.

Tasks principais:
- send_message_with_humanization: Envia mensagem com typing simulation
- process_lead_qualification: Processa qualificação de lead
- cleanup_old_messages: Limpeza periódica
"""

from app.tasks.celery_app import celery_app
from app.services.evolution_client import EvolutionClient
from app.utils.typing_simulator import TypingSimulator
from app.utils.warmup_controller import WarmupController
from app.core.exceptions import EvolutionAPIError, WarmupViolationError
from app.config import settings
from app.database import SessionLocal
from app.models import ConversationMessage, Lead
from datetime import datetime, timedelta
import redis
import asyncio
import logging

logger = logging.getLogger(__name__)


def get_redis_client():
    """Helper para obter cliente Redis"""
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(EvolutionAPIError,)
)
def send_message_with_humanization(
    self,
    session_name: str,
    phone: str,
    message_text: str,
    enable_humanization: bool = True
):
    """
    Task para enviar mensagem com typing simulation.

    Args:
        session_name: Nome da sessão WhatsApp
        phone: Telefone do destinatário
        message_text: Conteúdo da mensagem
        enable_humanization: Se True, aplica delays humanizados

    Returns:
        dict: Resultado do envio

    Raises:
        WarmupViolationError: Se violar regras de warmup
        EvolutionAPIError: Se falhar ao enviar (com retry)
    """
    logger.info(f"📤 Task iniciada: enviar mensagem para {phone}")

    try:
        # Criar clientes
        evolution = EvolutionClient()
        redis_client = get_redis_client()
        warmup = WarmupController(redis_client)

        # Verificar se é novo contato
        is_new = warmup.is_contact_new(session_name, phone)

        if is_new:
            # Verificar limite de novos contatos
            can_contact, message = warmup.can_contact_new_number(
                session_name,
                phone,
                enforce=True
            )

            if not can_contact:
                logger.error(f"❌ Warmup violation: {message}")
                raise WarmupViolationError(message, {"session": session_name, "phone": phone})

            warmup.mark_contact_as_contacted(session_name, phone)

        # Verificar rate limit de mensagens
        can_send, message = warmup.can_send_message(
            session_name,
            phone,
            enforce=True
        )

        if not can_send:
            logger.error(f"❌ Rate limit violation: {message}")
            raise WarmupViolationError(message, {"session": session_name, "phone": phone})

        # Enviar mensagem com humanização
        async def send():
            simulator = TypingSimulator(evolution)
            return await simulator.send_with_humanization(
                session_name,
                phone,
                message_text,
                enable_humanization
            )

        # Executar corrotina
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result = loop.run_until_complete(send())

        logger.info(f"✅ Mensagem enviada com sucesso para {phone}")
        return {
            "status": "success",
            "phone": phone,
            "message_id": result.get("key", {}).get("id"),
            "humanized": enable_humanization
        }

    except WarmupViolationError:
        # Não fazer retry em violações de warmup
        raise

    except EvolutionAPIError as e:
        logger.error(f"❌ Erro ao enviar mensagem (retry {self.request.retries}/3): {e}")
        # Celery vai fazer retry automaticamente
        raise

    except Exception as e:
        logger.error(f"❌ Erro inesperado ao enviar mensagem: {e}", exc_info=True)
        raise


@celery_app.task(bind=True, max_retries=2)
def process_lead_qualification(self, lead_id: int):
    """
    Task para processar qualificação de lead em background.

    Args:
        lead_id: ID do lead

    Returns:
        dict: Resultado do processamento
    """
    logger.info(f"🔍 Processando qualificação do lead {lead_id}")

    db = SessionLocal()

    try:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()

        if not lead:
            logger.warning(f"⚠️ Lead {lead_id} não encontrado")
            return {"status": "not_found"}

        # Lógica de qualificação adicional aqui
        # (ex: enriquecer dados, verificar duplicados, etc)

        logger.info(f"✅ Lead {lead_id} processado")

        return {
            "status": "success",
            "lead_id": lead_id,
            "slots_filled": lead.slots_filled,
            "qualification_score": lead.qualification_score
        }

    except Exception as e:
        logger.error(f"❌ Erro ao processar lead {lead_id}: {e}", exc_info=True)
        raise

    finally:
        db.close()


@celery_app.task
def cleanup_old_messages():
    """
    Task periódica para limpar mensagens antigas (>30 dias).

    Returns:
        dict: Quantidade de mensagens removidas
    """
    logger.info("🧹 Iniciando limpeza de mensagens antigas")

    db = SessionLocal()

    try:
        cutoff_date = datetime.utcnow() - timedelta(days=30)

        # Buscar mensagens antigas
        old_messages = db.query(ConversationMessage).filter(
            ConversationMessage.created_at < cutoff_date
        ).all()

        count = len(old_messages)

        if count > 0:
            for msg in old_messages:
                db.delete(msg)

            db.commit()
            logger.info(f"✅ {count} mensagens antigas removidas")
        else:
            logger.info("ℹ️ Nenhuma mensagem antiga para remover")

        return {
            "status": "success",
            "messages_removed": count,
            "cutoff_date": cutoff_date.isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Erro ao limpar mensagens: {e}", exc_info=True)
        db.rollback()
        raise

    finally:
        db.close()


@celery_app.task
def send_bulk_messages(session_name: str, phones: list[str], message_text: str):
    """
    Task para enviar mensagens em massa (com rate limiting automático).

    Args:
        session_name: Nome da sessão
        phones: Lista de telefones
        message_text: Mensagem a enviar

    Returns:
        dict: Resultado do envio em massa
    """
    logger.info(f"📨 Enviando mensagem para {len(phones)} contatos")

    results = {
        "total": len(phones),
        "sent": 0,
        "failed": 0,
        "warmup_blocked": 0
    }

    for phone in phones:
        try:
            # Enfileirar cada envio individualmente (para respeitar warmup)
            send_message_with_humanization.delay(
                session_name,
                phone,
                message_text
            )
            results["sent"] += 1

        except WarmupViolationError:
            logger.warning(f"⚠️ Contato {phone} bloqueado por warmup")
            results["warmup_blocked"] += 1

        except Exception as e:
            logger.error(f"❌ Erro ao enfileirar {phone}: {e}")
            results["failed"] += 1

    logger.info(f"✅ Bulk send concluído: {results}")
    return results

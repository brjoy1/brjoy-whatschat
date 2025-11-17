"""
Gerenciador de contexto conversacional.

Responsabilidades:
- Manter histórico de mensagens
- Detectar Shadow Mode (humano assumiu controle)
- Gerenciar estado da conversa
"""

from sqlalchemy.orm import Session
from app.models import Lead, ConversationMessage, MessageRole
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class ConversationManager:
    """Gerencia contexto e histórico de conversas"""

    # Timeout para Shadow Mode (5 minutos de inatividade = IA retoma)
    SHADOW_MODE_TIMEOUT = timedelta(minutes=5)

    def __init__(self, db: Session):
        """
        Inicializa manager.

        Args:
            db: Sessão do banco de dados
        """
        self.db = db

    def get_conversation_history(
        self,
        lead_id: int,
        limit: int = 50
    ) -> List[ConversationMessage]:
        """
        Busca histórico de mensagens do lead.

        Args:
            lead_id: ID do lead
            limit: Quantidade máxima de mensagens

        Returns:
            List[ConversationMessage]: Mensagens ordenadas cronologicamente
        """
        messages = self.db.query(ConversationMessage).filter(
            ConversationMessage.lead_id == lead_id
        ).order_by(
            ConversationMessage.created_at.asc()
        ).limit(limit).all()

        return messages

    def get_user_messages(
        self,
        lead_id: int,
        limit: int = 20
    ) -> List[str]:
        """
        Retorna apenas mensagens do usuário (para extração de slots).

        Args:
            lead_id: ID do lead
            limit: Quantidade máxima

        Returns:
            List[str]: Conteúdo das mensagens
        """
        messages = self.db.query(ConversationMessage).filter(
            ConversationMessage.lead_id == lead_id,
            ConversationMessage.role == MessageRole.USER
        ).order_by(
            ConversationMessage.created_at.asc()
        ).limit(limit).all()

        return [msg.content for msg in messages]

    def add_message(
        self,
        lead_id: int,
        role: MessageRole,
        content: str,
        message_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> ConversationMessage:
        """
        Adiciona nova mensagem ao histórico.

        Args:
            lead_id: ID do lead
            role: Papel da mensagem (user/assistant/system)
            content: Conteúdo
            message_id: ID da mensagem no WhatsApp
            metadata: Dados extras

        Returns:
            ConversationMessage: Mensagem criada
        """
        message = ConversationMessage(
            lead_id=lead_id,
            role=role,
            content=content,
            message_id=message_id,
            metadata=metadata
        )

        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)

        logger.debug(f"💬 Mensagem adicionada: lead={lead_id}, role={role}")

        return message

    def check_shadow_mode(self, lead: Lead) -> Tuple[bool, Optional[str]]:
        """
        Verifica se humano assumiu controle da conversa (Shadow Mode).

        Shadow Mode detecta quando:
        1. Lead está marcado como shadow_mode=True
        2. Última mensagem foi há menos de 5 minutos

        Se humano está inativo >5min, IA retoma.

        Args:
            lead: Lead a verificar

        Returns:
            Tuple[bool, str]: (em_shadow_mode, motivo)
        """
        if not lead.shadow_mode:
            return (False, None)

        # Verificar timeout
        if not lead.shadow_mode_since:
            # Shadow mode ativo mas sem timestamp - assumir recente
            return (True, "Humano assumiu controle")

        time_inactive = datetime.utcnow() - lead.shadow_mode_since

        if time_inactive > self.SHADOW_MODE_TIMEOUT:
            # Timeout - desativar shadow mode
            logger.info(f"🤖 Shadow mode expirou para lead {lead.id} - IA retomando")
            lead.shadow_mode = False
            lead.shadow_mode_since = None
            self.db.commit()
            return (False, "Shadow mode expirado - IA retomada")

        return (True, f"Humano ativo (inativo há {int(time_inactive.total_seconds())}s)")

    def enable_shadow_mode(self, lead_id: int, reason: str = "Manual"):
        """
        Ativa Shadow Mode para um lead.

        Args:
            lead_id: ID do lead
            reason: Motivo da ativação
        """
        lead = self.db.query(Lead).filter(Lead.id == lead_id).first()

        if not lead:
            logger.warning(f"⚠️ Lead {lead_id} não encontrado")
            return

        lead.shadow_mode = True
        lead.shadow_mode_since = datetime.utcnow()
        self.db.commit()

        logger.info(f"👤 Shadow mode ativado para lead {lead_id}: {reason}")

        # Adicionar mensagem de sistema
        self.add_message(
            lead_id,
            MessageRole.SYSTEM,
            f"Shadow Mode ativado: {reason}"
        )

    def disable_shadow_mode(self, lead_id: int):
        """
        Desativa Shadow Mode para um lead.

        Args:
            lead_id: ID do lead
        """
        lead = self.db.query(Lead).filter(Lead.id == lead_id).first()

        if not lead:
            logger.warning(f"⚠️ Lead {lead_id} não encontrado")
            return

        lead.shadow_mode = False
        lead.shadow_mode_since = None
        self.db.commit()

        logger.info(f"🤖 Shadow mode desativado para lead {lead_id} - IA retomou")

        # Adicionar mensagem de sistema
        self.add_message(
            lead_id,
            MessageRole.SYSTEM,
            "Shadow Mode desativado - IA retomou"
        )

    def get_conversation_summary(self, lead_id: int) -> dict:
        """
        Gera resumo da conversa.

        Args:
            lead_id: ID do lead

        Returns:
            dict: Resumo com métricas
        """
        messages = self.get_conversation_history(lead_id)

        user_messages = [m for m in messages if m.role == MessageRole.USER]
        assistant_messages = [m for m in messages if m.role == MessageRole.ASSISTANT]
        system_messages = [m for m in messages if m.role == MessageRole.SYSTEM]

        if messages:
            first_message_date = messages[0].created_at
            last_message_date = messages[-1].created_at
            conversation_duration = last_message_date - first_message_date
        else:
            first_message_date = None
            last_message_date = None
            conversation_duration = timedelta(0)

        return {
            "lead_id": lead_id,
            "total_messages": len(messages),
            "user_messages": len(user_messages),
            "assistant_messages": len(assistant_messages),
            "system_messages": len(system_messages),
            "first_message": first_message_date.isoformat() if first_message_date else None,
            "last_message": last_message_date.isoformat() if last_message_date else None,
            "duration_seconds": int(conversation_duration.total_seconds())
        }

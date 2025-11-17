"""
Controlador de warmup para prevenir banimento no WhatsApp.

Implementa protocolo de warmup de 10 dias:
- Limita novos contatos por dia (20)
- Rate limiting de mensagens por hora (4)
- Tracking de ativação da sessão
"""

from datetime import datetime, timedelta
import redis
from typing import Optional, Tuple
from app.config import settings
from app.core.exceptions import WarmupViolationError
import logging

logger = logging.getLogger(__name__)


class WarmupController:
    """
    Implementa protocolo de warmup de 10 dias para prevenir ban.

    Regras:
    - Primeiros 10 dias: limite de 20 novos contatos/dia
    - Sempre: máximo 4 mensagens/hora por contato
    - Tracking de data de ativação da sessão
    """

    def __init__(self, redis_client: redis.Redis):
        """
        Inicializa controller.

        Args:
            redis_client: Cliente Redis para tracking
        """
        self.redis = redis_client
        self.WARMUP_DAYS = settings.WARMUP_DAYS
        self.MAX_NEW_CONTACTS_PER_DAY = settings.MAX_NEW_CONTACTS_PER_DAY
        self.MAX_MESSAGES_PER_HOUR = settings.MAX_MESSAGES_PER_HOUR

    def _get_session_start_date(self, session: str) -> Optional[datetime]:
        """
        Busca data de ativação da sessão.

        Args:
            session: Nome da sessão

        Returns:
            datetime: Data de ativação ou None
        """
        key = f"session:{session}:activated_at"
        timestamp = self.redis.get(key)

        if timestamp:
            return datetime.fromtimestamp(float(timestamp))

        return None

    def register_session_activation(self, session: str) -> None:
        """
        Registra ativação de uma nova sessão.

        Args:
            session: Nome da sessão
        """
        key = f"session:{session}:activated_at"

        if not self.redis.exists(key):
            self.redis.set(key, datetime.utcnow().timestamp())
            logger.info(f"✅ Sessão '{session}' ativada - warmup iniciado")
        else:
            logger.debug(f"Sessão '{session}' já estava ativada")

    def get_days_since_activation(self, session: str) -> int:
        """
        Retorna dias desde ativação da sessão.

        Args:
            session: Nome da sessão

        Returns:
            int: Número de dias (0 se não ativada)
        """
        start_date = self._get_session_start_date(session)

        if not start_date:
            return 0

        delta = datetime.utcnow() - start_date
        return delta.days

    def is_warmup_completed(self, session: str) -> bool:
        """
        Verifica se warmup foi completado.

        Args:
            session: Nome da sessão

        Returns:
            bool: True se >= 10 dias desde ativação
        """
        days = self.get_days_since_activation(session)
        return days >= self.WARMUP_DAYS

    def can_contact_new_number(
        self,
        session: str,
        phone: str,
        enforce: bool = True
    ) -> Tuple[bool, str]:
        """
        Verifica se pode iniciar conversa com novo contato.

        Args:
            session: Nome da sessão
            phone: Telefone do novo contato
            enforce: Se True, incrementa contador. Se False, apenas verifica.

        Returns:
            Tuple[bool, str]: (permitido, mensagem)

        Raises:
            WarmupViolationError: Se enforce=True e limite atingido
        """
        days = self.get_days_since_activation(session)

        # Sessão não ativada - permitir mas registrar
        if days == 0:
            if enforce:
                self.register_session_activation(session)
            return (True, "Primeira ativação - warmup iniciado")

        # Warmup completado - sem limites
        if days >= self.WARMUP_DAYS:
            return (True, "Sessão aquecida - sem limites")

        # Durante warmup - verificar limite diário
        today = datetime.utcnow().strftime("%Y-%m-%d")
        key = f"session:{session}:new_contacts:{today}"

        current_count = int(self.redis.get(key) or 0)

        if current_count >= self.MAX_NEW_CONTACTS_PER_DAY:
            message = (
                f"Limite diário de {self.MAX_NEW_CONTACTS_PER_DAY} novos contatos atingido "
                f"(warmup dia {days}/{self.WARMUP_DAYS})"
            )

            if enforce:
                logger.warning(f"⚠️ {message}")
                raise WarmupViolationError(
                    message,
                    {
                        "session": session,
                        "phone": phone,
                        "current_count": current_count,
                        "limit": self.MAX_NEW_CONTACTS_PER_DAY,
                        "warmup_day": days
                    }
                )

            return (False, message)

        # Permitido - incrementar se enforce
        if enforce:
            self.redis.incr(key)
            self.redis.expire(key, 86400)  # 24 horas

        message = f"Contato permitido ({current_count + 1}/{self.MAX_NEW_CONTACTS_PER_DAY} hoje, dia {days}/{self.WARMUP_DAYS})"
        logger.info(f"✅ {message}")

        return (True, message)

    def can_send_message(
        self,
        session: str,
        phone: str,
        enforce: bool = True
    ) -> Tuple[bool, str]:
        """
        Verifica rate limit de mensagens por contato.

        Args:
            session: Nome da sessão
            phone: Telefone do contato
            enforce: Se True, incrementa contador. Se False, apenas verifica.

        Returns:
            Tuple[bool, str]: (permitido, mensagem)

        Raises:
            WarmupViolationError: Se enforce=True e limite atingido
        """
        key = f"session:{session}:messages:{phone}:hour"
        current_count = int(self.redis.get(key) or 0)

        if current_count >= self.MAX_MESSAGES_PER_HOUR:
            message = (
                f"Limite de {self.MAX_MESSAGES_PER_HOUR} mensagens/hora atingido para {phone}"
            )

            if enforce:
                logger.warning(f"⚠️ {message}")
                raise WarmupViolationError(
                    message,
                    {
                        "session": session,
                        "phone": phone,
                        "current_count": current_count,
                        "limit": self.MAX_MESSAGES_PER_HOUR
                    }
                )

            return (False, message)

        # Permitido - incrementar se enforce
        if enforce:
            self.redis.incr(key)
            self.redis.expire(key, 3600)  # 1 hora

        message = f"Mensagem permitida ({current_count + 1}/{self.MAX_MESSAGES_PER_HOUR} na última hora)"
        logger.debug(f"✅ {message}")

        return (True, message)

    def is_contact_new(self, session: str, phone: str) -> bool:
        """
        Verifica se é um contato novo (primeira mensagem).

        Args:
            session: Nome da sessão
            phone: Telefone do contato

        Returns:
            bool: True se nunca enviou mensagem antes
        """
        key = f"session:{session}:contacted:{phone}"
        return not self.redis.exists(key)

    def mark_contact_as_contacted(self, session: str, phone: str) -> None:
        """
        Marca contato como já contatado.

        Args:
            session: Nome da sessão
            phone: Telefone do contato
        """
        key = f"session:{session}:contacted:{phone}"
        self.redis.set(key, "1", ex=86400 * 30)  # 30 dias

    def get_warmup_stats(self, session: str) -> dict:
        """
        Retorna estatísticas de warmup da sessão.

        Args:
            session: Nome da sessão

        Returns:
            dict: Estatísticas
        """
        days = self.get_days_since_activation(session)
        completed = self.is_warmup_completed(session)

        today = datetime.utcnow().strftime("%Y-%m-%d")
        new_contacts_today_key = f"session:{session}:new_contacts:{today}"
        new_contacts_today = int(self.redis.get(new_contacts_today_key) or 0)

        return {
            "session": session,
            "days_since_activation": days,
            "warmup_completed": completed,
            "warmup_progress_pct": min(100, (days / self.WARMUP_DAYS) * 100),
            "new_contacts_today": new_contacts_today,
            "new_contacts_limit": self.MAX_NEW_CONTACTS_PER_DAY,
            "messages_per_hour_limit": self.MAX_MESSAGES_PER_HOUR
        }

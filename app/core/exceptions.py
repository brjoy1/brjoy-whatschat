"""
Exceções customizadas da aplicação.
"""

from typing import Any, Optional


class AgenticSlotFillingError(Exception):
    """Exceção base para todas as exceções da aplicação"""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class EvolutionAPIError(AgenticSlotFillingError):
    """Erro ao comunicar com Evolution API"""
    pass


class SlotExtractionError(AgenticSlotFillingError):
    """Erro ao extrair slots da mensagem"""
    pass


class WarmupViolationError(AgenticSlotFillingError):
    """Violação das regras de warmup"""
    pass


class DatabaseError(AgenticSlotFillingError):
    """Erro de operação no banco de dados"""
    pass


class EncryptionError(AgenticSlotFillingError):
    """Erro ao criptografar/descriptografar dados"""
    pass


class SessionNotFoundError(AgenticSlotFillingError):
    """Sessão WhatsApp não encontrada"""
    pass


class LeadNotFoundError(AgenticSlotFillingError):
    """Lead não encontrado"""
    pass

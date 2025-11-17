"""
Dependências para injeção no FastAPI.
"""

from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.services.evolution_client import get_evolution_client, EvolutionClient
from app.services.slot_extractor import get_slot_extractor, SlotExtractor
from app.config import settings
import redis
import logging

logger = logging.getLogger(__name__)

# Redis client singleton
_redis_client: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    """
    Dependency injection para Redis.

    Returns:
        redis.Redis: Cliente Redis configurado
    """
    global _redis_client

    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True
        )
        logger.info("✅ Redis client inicializado")

    return _redis_client


async def verify_api_key(apikey: Optional[str] = Header(None)) -> str:
    """
    Verifica API key do webhook Evolution API.

    Args:
        apikey: Header apikey

    Returns:
        str: API key validada

    Raises:
        HTTPException: Se API key inválida
    """
    if not apikey:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key não fornecida"
        )

    if apikey != settings.EVOLUTION_API_KEY:
        logger.warning(f"⚠️ Tentativa de acesso com API key inválida: {apikey[:10]}...")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key inválida"
        )

    return apikey


# Type aliases para dependency injection
DatabaseDep = Depends(get_db)
EvolutionClientDep = Depends(get_evolution_client)
SlotExtractorDep = Depends(get_slot_extractor)
RedisDep = Depends(get_redis)

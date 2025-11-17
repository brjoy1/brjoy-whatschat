"""
Endpoints de health check e status do sistema.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.api.deps import get_db, get_redis, get_evolution_client
from app.services.evolution_client import EvolutionClient
from app.core.exceptions import EvolutionAPIError
import redis
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/")
async def health_check():
    """
    Health check básico.

    Returns:
        dict: Status da aplicação
    """
    return {
        "status": "healthy",
        "service": "agentic-slot-filling-api",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/detailed")
async def detailed_health_check(
    db: Session = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
    evolution: EvolutionClient = Depends(get_evolution_client)
):
    """
    Health check detalhado com status de todos os serviços.

    Returns:
        dict: Status detalhado de cada componente
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {}
    }

    # Check Database
    try:
        db.execute(text("SELECT 1"))
        health_status["services"]["database"] = {
            "status": "healthy",
            "message": "PostgreSQL conectado"
        }
    except Exception as e:
        logger.error(f"❌ Database health check falhou: {e}")
        health_status["services"]["database"] = {
            "status": "unhealthy",
            "message": str(e)
        }
        health_status["status"] = "unhealthy"

    # Check Redis
    try:
        redis_client.ping()
        health_status["services"]["redis"] = {
            "status": "healthy",
            "message": "Redis conectado"
        }
    except Exception as e:
        logger.error(f"❌ Redis health check falhou: {e}")
        health_status["services"]["redis"] = {
            "status": "unhealthy",
            "message": str(e)
        }
        health_status["status"] = "unhealthy"

    # Check Evolution API
    try:
        await evolution.check_health()
        health_status["services"]["evolution_api"] = {
            "status": "healthy",
            "message": "Evolution API disponível"
        }
    except (EvolutionAPIError, Exception) as e:
        logger.error(f"❌ Evolution API health check falhou: {e}")
        health_status["services"]["evolution_api"] = {
            "status": "unhealthy",
            "message": str(e)
        }
        health_status["status"] = "degraded"  # Não crítico para API

    return health_status

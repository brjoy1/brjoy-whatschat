"""
Aplicação FastAPI principal do Agentic Slot Filling.

Orquestra:
- Recebimento de webhooks WhatsApp
- Extração de slots com PydanticAI
- Gerenciamento de sessões
- API de consulta de leads
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import settings
from app.core.logging import setup_logging
from app.services.evolution_client import get_evolution_client
from app.core.exceptions import EvolutionAPIError
import logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia startup e shutdown da aplicação.

    Startup:
    - Configura logging
    - Valida conexão com Evolution API
    - Inicializa serviços

    Shutdown:
    - Fecha conexões
    - Limpa recursos
    """
    logger.info("🚀 Iniciando Agentic Slot Filling API...")
    logger.info(f"Versão: {app.version}")
    logger.info(f"Ambiente: {'DEBUG' if settings.DEBUG else 'PRODUCTION'}")

    # Validar conexão com Evolution API
    try:
        evolution = await get_evolution_client()
        logger.info("✅ Conectado à Evolution API")
    except (EvolutionAPIError, Exception) as e:
        logger.warning(f"⚠️ Evolution API não disponível no startup: {e}")
        logger.warning("Aplicação continuará, mas funcionalidades WhatsApp podem estar indisponíveis")

    # Importar routers (aqui para evitar import circular)
    from app.api import webhook, sessions, leads, health

    # Registrar routers
    app.include_router(health.router, prefix="/health", tags=["Health"])
    app.include_router(webhook.router, prefix="/api/v1", tags=["Webhook"])
    app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["Sessions"])
    app.include_router(leads.router, prefix="/api/v1/leads", tags=["Leads"])

    logger.info("✅ Routers registrados")
    logger.info("🎉 Aplicação iniciada com sucesso!")

    yield

    # Shutdown
    logger.info("🛑 Encerrando aplicação...")

    try:
        evolution = await get_evolution_client()
        await evolution.close()
        logger.info("✅ Conexão Evolution API fechada")
    except Exception as e:
        logger.error(f"⚠️ Erro ao fechar Evolution API: {e}")

    logger.info("👋 Aplicação encerrada")


# Criar aplicação FastAPI
app = FastAPI(
    title="Agentic Slot Filling API",
    description="Sistema de triagem inteligente para WhatsApp usando IA agêntica",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,  # Swagger apenas em debug
    redoc_url="/redoc" if settings.DEBUG else None
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else [],  # Restringir em produção
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """
    Endpoint raiz - informações básicas da API.

    Returns:
        dict: Informações da API
    """
    return {
        "service": "Agentic Slot Filling API",
        "version": app.version,
        "status": "running",
        "docs": "/docs" if settings.DEBUG else "disabled",
        "endpoints": {
            "health": "/health",
            "webhook": "/api/v1/webhook",
            "sessions": "/api/v1/sessions",
            "leads": "/api/v1/leads"
        }
    }


# Exception handlers
from fastapi import Request
from fastapi.responses import JSONResponse
from app.core.exceptions import (
    AgenticSlotFillingError,
    EvolutionAPIError,
    SlotExtractionError,
    WarmupViolationError
)


@app.exception_handler(AgenticSlotFillingError)
async def agentic_error_handler(request: Request, exc: AgenticSlotFillingError):
    """Handler para exceções customizadas da aplicação"""
    logger.error(f"❌ {exc.__class__.__name__}: {exc.message}", extra=exc.details)

    return JSONResponse(
        status_code=500,
        content={
            "error": exc.__class__.__name__,
            "message": exc.message,
            "details": exc.details
        }
    )


@app.exception_handler(EvolutionAPIError)
async def evolution_error_handler(request: Request, exc: EvolutionAPIError):
    """Handler específico para erros da Evolution API"""
    logger.error(f"❌ Evolution API Error: {exc.message}", extra=exc.details)

    return JSONResponse(
        status_code=503,
        content={
            "error": "EvolutionAPIError",
            "message": "Serviço WhatsApp temporariamente indisponível",
            "details": exc.details
        }
    )


@app.exception_handler(WarmupViolationError)
async def warmup_error_handler(request: Request, exc: WarmupViolationError):
    """Handler para violações de warmup"""
    logger.warning(f"⚠️ Warmup Violation: {exc.message}", extra=exc.details)

    return JSONResponse(
        status_code=429,
        content={
            "error": "WarmupViolationError",
            "message": exc.message,
            "details": exc.details
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )

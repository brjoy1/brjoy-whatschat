"""
Endpoints para gerenciamento de sessões WhatsApp.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_evolution_client, get_redis
from app.services.evolution_client import EvolutionClient
from app.core.exceptions import EvolutionAPIError, SessionNotFoundError
from app.models import WhatsAppSession, SessionStatus
from app.schemas import SessionCreate, SessionResponse
from typing import List
from datetime import datetime
import redis
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/qr", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session_and_get_qr(
    session_data: SessionCreate,
    db: Session = Depends(get_db),
    evolution: EvolutionClient = Depends(get_evolution_client),
    redis_client: redis.Redis = Depends(get_redis)
):
    """
    Cria nova sessão WhatsApp e retorna QR code.

    Args:
        session_data: Dados da sessão (session_name)

    Returns:
        SessionResponse: Sessão criada com QR code

    Raises:
        HTTPException: Se sessão já existe ou erro ao criar
    """
    # Verificar se sessão já existe
    existing = db.query(WhatsAppSession).filter(
        WhatsAppSession.session_name == session_data.session_name
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Sessão '{session_data.session_name}' já existe"
        )

    try:
        # Criar instância no Evolution API
        logger.info(f"Criando instância WhatsApp: {session_data.session_name}")
        instance_response = await evolution.create_instance(session_data.session_name)

        # Gerar QR code
        qr_response = await evolution.get_qr_code(session_data.session_name)

        qr_code = qr_response.get("qrcode", {}).get("base64") or qr_response.get("code")

        # Salvar no banco
        session = WhatsAppSession(
            session_name=session_data.session_name,
            status=SessionStatus.PENDING,
            qr_code=qr_code,
            metadata=instance_response
        )

        db.add(session)
        db.commit()
        db.refresh(session)

        logger.info(f"✅ Sessão '{session_data.session_name}' criada com sucesso")

        return session

    except EvolutionAPIError as e:
        logger.error(f"❌ Erro ao criar sessão: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/", response_model=List[SessionResponse])
def list_sessions(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Lista todas as sessões WhatsApp.

    Args:
        skip: Offset de paginação
        limit: Limite de resultados

    Returns:
        List[SessionResponse]: Lista de sessões
    """
    sessions = db.query(WhatsAppSession).offset(skip).limit(limit).all()
    return sessions


@router.get("/{session_name}", response_model=SessionResponse)
async def get_session(
    session_name: str,
    db: Session = Depends(get_db),
    evolution: EvolutionClient = Depends(get_evolution_client)
):
    """
    Busca sessão pelo nome e atualiza status.

    Args:
        session_name: Nome da sessão

    Returns:
        SessionResponse: Dados da sessão

    Raises:
        HTTPException: Se sessão não encontrada
    """
    session = db.query(WhatsAppSession).filter(
        WhatsAppSession.session_name == session_name
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sessão '{session_name}' não encontrada"
        )

    # Atualizar status da conexão
    try:
        state = await evolution.get_connection_state(session_name)
        connection_state = state.get("state")

        if connection_state == "open":
            session.status = SessionStatus.CONNECTED
            session.last_connection = datetime.utcnow()

            # Registrar ativação para warmup
            if not session.activated_at:
                session.activated_at = datetime.utcnow()
                logger.info(f"✅ Sessão '{session_name}' ativada (warmup iniciado)")

        elif connection_state == "close":
            session.status = SessionStatus.DISCONNECTED

        db.commit()
        db.refresh(session)

    except EvolutionAPIError as e:
        logger.warning(f"⚠️ Não foi possível atualizar status de '{session_name}': {e}")

    return session


@router.delete("/{session_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_name: str,
    db: Session = Depends(get_db),
    evolution: EvolutionClient = Depends(get_evolution_client)
):
    """
    Remove sessão WhatsApp completamente.

    Args:
        session_name: Nome da sessão

    Raises:
        HTTPException: Se sessão não encontrada
    """
    session = db.query(WhatsAppSession).filter(
        WhatsAppSession.session_name == session_name
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sessão '{session_name}' não encontrada"
        )

    try:
        # Remover do Evolution API
        await evolution.delete_instance(session_name)

        # Remover do banco (cascata remove leads e mensagens)
        db.delete(session)
        db.commit()

        logger.info(f"✅ Sessão '{session_name}' removida")

    except EvolutionAPIError as e:
        logger.error(f"❌ Erro ao remover sessão: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/{session_name}/logout", status_code=status.HTTP_200_OK)
async def logout_session(
    session_name: str,
    db: Session = Depends(get_db),
    evolution: EvolutionClient = Depends(get_evolution_client)
):
    """
    Desconecta sessão WhatsApp (mantém dados).

    Args:
        session_name: Nome da sessão

    Returns:
        dict: Status do logout

    Raises:
        HTTPException: Se sessão não encontrada
    """
    session = db.query(WhatsAppSession).filter(
        WhatsAppSession.session_name == session_name
    ).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sessão '{session_name}' não encontrada"
        )

    try:
        # Logout no Evolution API
        result = await evolution.logout_instance(session_name)

        # Atualizar status
        session.status = SessionStatus.DISCONNECTED
        db.commit()

        logger.info(f"✅ Logout realizado para '{session_name}'")

        return {
            "message": f"Sessão '{session_name}' desconectada",
            "result": result
        }

    except EvolutionAPIError as e:
        logger.error(f"❌ Erro ao fazer logout: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

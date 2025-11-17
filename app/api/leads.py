"""
Endpoints para gerenciamento de leads capturados.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.models import Lead, LeadStatus, ConversationMessage
from app.schemas import LeadResponse
from app.core.security import encryption_manager
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=List[LeadResponse])
def list_leads(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
    status_filter: Optional[LeadStatus] = None,
    session_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Lista leads capturados com filtros opcionais.

    Args:
        skip: Offset de paginação
        limit: Limite de resultados (máx 1000)
        status_filter: Filtrar por status (active, qualified, etc)
        session_id: Filtrar por ID da sessão

    Returns:
        List[LeadResponse]: Lista de leads

    Note:
        Telefones e emails são descriptografados automaticamente
    """
    query = db.query(Lead)

    # Aplicar filtros
    if status_filter:
        query = query.filter(Lead.status == status_filter)

    if session_id:
        query = query.filter(Lead.session_id == session_id)

    # Ordenar por interação mais recente
    leads = query.order_by(Lead.last_interaction.desc()).offset(skip).limit(limit).all()

    # Descriptografar dados sensíveis
    for lead in leads:
        if lead.phone:
            try:
                lead.phone = encryption_manager.decrypt_phone(lead.phone)
            except Exception as e:
                logger.warning(f"⚠️ Erro ao descriptografar telefone do lead {lead.id}: {e}")

        if lead.email:
            try:
                lead.email = encryption_manager.decrypt_email(lead.email)
            except Exception as e:
                logger.warning(f"⚠️ Erro ao descriptografar email do lead {lead.id}: {e}")

    return leads


@router.get("/{lead_id}", response_model=LeadResponse)
def get_lead(
    lead_id: int,
    db: Session = Depends(get_db)
):
    """
    Busca lead pelo ID.

    Args:
        lead_id: ID do lead

    Returns:
        LeadResponse: Dados do lead

    Raises:
        HTTPException: Se lead não encontrado
    """
    lead = db.query(Lead).filter(Lead.id == lead_id).first()

    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead {lead_id} não encontrado"
        )

    # Descriptografar dados sensíveis
    if lead.phone:
        try:
            lead.phone = encryption_manager.decrypt_phone(lead.phone)
        except Exception as e:
            logger.warning(f"⚠️ Erro ao descriptografar telefone: {e}")

    if lead.email:
        try:
            lead.email = encryption_manager.decrypt_email(lead.email)
        except Exception as e:
            logger.warning(f"⚠️ Erro ao descriptografar email: {e}")

    return lead


@router.get("/{lead_id}/messages")
def get_lead_messages(
    lead_id: int,
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db)
):
    """
    Retorna histórico de mensagens do lead.

    Args:
        lead_id: ID do lead
        limit: Limite de mensagens (máx 500)

    Returns:
        dict: Mensagens ordenadas cronologicamente

    Raises:
        HTTPException: Se lead não encontrado
    """
    lead = db.query(Lead).filter(Lead.id == lead_id).first()

    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead {lead_id} não encontrado"
        )

    messages = db.query(ConversationMessage).filter(
        ConversationMessage.lead_id == lead_id
    ).order_by(ConversationMessage.created_at.asc()).limit(limit).all()

    return {
        "lead_id": lead_id,
        "total_messages": len(messages),
        "messages": [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at,
                "metadata": msg.metadata
            }
            for msg in messages
        ]
    }


@router.patch("/{lead_id}/status")
def update_lead_status(
    lead_id: int,
    new_status: LeadStatus,
    db: Session = Depends(get_db)
):
    """
    Atualiza status do lead.

    Args:
        lead_id: ID do lead
        new_status: Novo status

    Returns:
        dict: Lead atualizado

    Raises:
        HTTPException: Se lead não encontrado
    """
    lead = db.query(Lead).filter(Lead.id == lead_id).first()

    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead {lead_id} não encontrado"
        )

    old_status = lead.status
    lead.status = new_status
    db.commit()
    db.refresh(lead)

    logger.info(f"✅ Lead {lead_id} status atualizado: {old_status} → {new_status}")

    return {
        "lead_id": lead_id,
        "old_status": old_status,
        "new_status": new_status,
        "message": "Status atualizado com sucesso"
    }


@router.get("/stats/summary")
def get_leads_stats(
    session_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Retorna estatísticas agregadas dos leads.

    Args:
        session_id: Filtrar por sessão específica

    Returns:
        dict: Estatísticas
    """
    query = db.query(Lead)

    if session_id:
        query = query.filter(Lead.session_id == session_id)

    total = query.count()

    stats = {
        "total_leads": total,
        "by_status": {},
        "avg_slots_filled": 0,
        "qualified_leads": 0
    }

    # Count por status
    for status_value in LeadStatus:
        count = query.filter(Lead.status == status_value).count()
        stats["by_status"][status_value.value] = count

    # Média de slots preenchidos
    if total > 0:
        avg_slots = db.query(Lead).with_entities(
            db.func.avg(Lead.slots_filled)
        ).filter(Lead.session_id == session_id if session_id else True).scalar()

        stats["avg_slots_filled"] = round(float(avg_slots or 0), 2)

    # Leads qualificados (4 campos críticos preenchidos)
    stats["qualified_leads"] = query.filter(Lead.slots_filled >= 4).count()

    return stats

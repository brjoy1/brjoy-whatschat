"""
Modelos SQLAlchemy para o banco de dados.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON, Enum, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum
from datetime import datetime


class SessionStatus(str, enum.Enum):
    """Status da sessão WhatsApp"""
    PENDING = "pending"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    FAILED = "failed"


class LeadStatus(str, enum.Enum):
    """Status do lead"""
    ACTIVE = "active"
    QUALIFIED = "qualified"
    UNQUALIFIED = "unqualified"
    ARCHIVED = "archived"


class MessageRole(str, enum.Enum):
    """Papel da mensagem"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class WhatsAppSession(Base):
    """Sessão WhatsApp conectada via Evolution API"""

    __tablename__ = "whatsapp_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_name = Column(String(255), unique=True, nullable=False, index=True)
    status = Column(Enum(SessionStatus), default=SessionStatus.PENDING, nullable=False)

    # Informações da conta conectada
    phone_number = Column(String(255), nullable=True)  # Criptografado
    account_name = Column(String(255), nullable=True)

    # Controle de warmup
    activated_at = Column(DateTime(timezone=True), nullable=True)
    warmup_completed = Column(Boolean, default=False)

    # Metadados
    qr_code = Column(Text, nullable=True)
    last_connection = Column(DateTime(timezone=True), nullable=True)
    metadata = Column(JSON, nullable=True)  # Dados extras

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relacionamentos
    leads = relationship("Lead", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<WhatsAppSession(session_name='{self.session_name}', status='{self.status}')>"


class Lead(Base):
    """Lead capturado via WhatsApp"""

    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("whatsapp_sessions.id"), nullable=False)
    phone = Column(String(255), nullable=False, index=True)  # Criptografado
    status = Column(Enum(LeadStatus), default=LeadStatus.ACTIVE, nullable=False)

    # Dados do lead (slots preenchidos)
    nome = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)  # Criptografado

    # Preferências do imóvel
    tipo_imovel = Column(String(50), nullable=True)
    finalidade = Column(String(50), nullable=True)
    localizacao_desejada = Column(String(255), nullable=True)
    num_quartos = Column(Integer, nullable=True)

    # Orçamento
    orcamento_min = Column(Float, nullable=True)
    orcamento_max = Column(Float, nullable=True)

    # Timeline e extras
    timeline = Column(String(50), nullable=True)
    observacoes = Column(Text, nullable=True)

    # Métricas de qualificação
    slots_filled = Column(Integer, default=0)
    total_messages = Column(Integer, default=0)
    qualification_score = Column(Float, nullable=True)  # 0-100

    # Shadow Mode
    shadow_mode = Column(Boolean, default=False)  # True se humano assumiu
    shadow_mode_since = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_interaction = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relacionamentos
    session = relationship("WhatsAppSession", back_populates="leads")
    messages = relationship("ConversationMessage", back_populates="lead", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Lead(id={self.id}, phone='{self.phone}', status='{self.status}', slots={self.slots_filled})>"


class ConversationMessage(Base):
    """Mensagem da conversa com o lead"""

    __tablename__ = "conversation_messages"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)

    role = Column(Enum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)

    # Metadados da mensagem
    message_id = Column(String(255), nullable=True)  # ID da mensagem no WhatsApp
    metadata = Column(JSON, nullable=True)  # Dados extras (tipo de mídia, etc)

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relacionamentos
    lead = relationship("Lead", back_populates="messages")

    def __repr__(self):
        return f"<ConversationMessage(id={self.id}, lead_id={self.lead_id}, role='{self.role}')>"

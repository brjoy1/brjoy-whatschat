"""
Schemas Pydantic para validação de dados e extração de slots.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum
from datetime import datetime


# Enums para slots
class TipoImovel(str, Enum):
    CASA = "casa"
    APARTAMENTO = "apartamento"
    TERRENO = "terreno"
    COMERCIAL = "comercial"


class Finalidade(str, Enum):
    COMPRAR = "comprar"
    ALUGAR = "alugar"


class Timeline(str, Enum):
    URGENTE = "urgente"
    UM_MES = "1_mes"
    TRES_MESES = "3_meses"
    SEM_PRESSA = "sem_pressa"


# Schema principal de Lead
class LeadImobiliaria(BaseModel):
    """
    Schema validado de lead para imobiliária.
    Usado pelo PydanticAI para extração de slots.
    """

    # Dados de contato
    nome: Optional[str] = Field(None, description="Nome completo")
    telefone: Optional[str] = Field(None, description="Telefone com DDD")
    email: Optional[str] = Field(None, description="Email válido")

    # Preferências do imóvel
    tipo_imovel: Optional[TipoImovel] = Field(None, description="Tipo de imóvel desejado")
    finalidade: Optional[Finalidade] = Field(None, description="Comprar ou alugar")
    localizacao_desejada: Optional[str] = Field(None, description="Bairro, cidade ou região")
    num_quartos: Optional[int] = Field(None, ge=0, le=10, description="Número de quartos")

    # Orçamento
    orcamento_min: Optional[float] = Field(None, ge=0, description="Orçamento mínimo em reais")
    orcamento_max: Optional[float] = Field(None, ge=0, description="Orçamento máximo em reais")

    # Timeline e extras
    timeline: Optional[Timeline] = Field(None, description="Urgência da compra/aluguel")
    observacoes: Optional[str] = Field(None, description="Informações adicionais")

    @field_validator('telefone')
    @classmethod
    def validar_telefone_brasileiro(cls, v):
        """Valida formato de telefone brasileiro (10 ou 11 dígitos)"""
        if v:
            apenas_numeros = ''.join(filter(str.isdigit, v))
            if len(apenas_numeros) not in [10, 11]:
                raise ValueError('Telefone deve ter 10 ou 11 dígitos (com DDD)')
        return v

    @field_validator('orcamento_max')
    @classmethod
    def orcamento_max_maior_que_min(cls, v, info):
        """Valida que orçamento máximo é maior que mínimo"""
        if v and info.data.get('orcamento_min') and v < info.data['orcamento_min']:
            raise ValueError('Orçamento máximo deve ser maior que mínimo')
        return v

    def slots_preenchidos(self) -> int:
        """Retorna quantidade de slots não-nulos"""
        return sum(1 for field in self.model_fields if getattr(self, field) is not None)

    def slots_criticos_faltando(self) -> list[str]:
        """Retorna lista de campos críticos ainda vazios"""
        criticos = ['nome', 'telefone', 'tipo_imovel', 'finalidade']
        return [field for field in criticos if getattr(self, field) is None]

    def to_dict(self) -> dict:
        """Converte para dicionário, incluindo enums como strings"""
        return self.model_dump(mode='json')


# Schemas para API requests/responses
class SessionCreate(BaseModel):
    """Schema para criar nova sessão WhatsApp"""
    session_name: str = Field(..., min_length=1, max_length=255)


class SessionResponse(BaseModel):
    """Schema de resposta com informações da sessão"""
    id: int
    session_name: str
    status: str
    qr_code: Optional[str] = None
    phone_number: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class LeadResponse(BaseModel):
    """Schema de resposta com informações do lead"""
    id: int
    session_id: int
    phone: str
    status: str
    nome: Optional[str] = None
    email: Optional[str] = None
    tipo_imovel: Optional[str] = None
    finalidade: Optional[str] = None
    localizacao_desejada: Optional[str] = None
    num_quartos: Optional[int] = None
    orcamento_min: Optional[float] = None
    orcamento_max: Optional[float] = None
    timeline: Optional[str] = None
    observacoes: Optional[str] = None
    slots_filled: int
    total_messages: int
    qualification_score: Optional[float] = None
    shadow_mode: bool
    created_at: datetime
    last_interaction: datetime

    class Config:
        from_attributes = True


class WebhookMessage(BaseModel):
    """Schema para mensagens recebidas do webhook Evolution API"""
    instance: str
    data: dict
    destination: Optional[str] = None
    date_time: Optional[str] = None
    sender: Optional[str] = None
    server_url: Optional[str] = None
    apikey: Optional[str] = None

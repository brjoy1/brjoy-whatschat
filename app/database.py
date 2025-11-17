"""
Configuração do SQLAlchemy e gerenciamento de sessões.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Engine do SQLAlchemy
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # Verifica conexão antes de usar
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,  # Recicla conexões após 1 hora
    echo=settings.DEBUG,  # SQL logging em modo debug
    connect_args={
        "connect_timeout": 10,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
    } if "postgresql" in settings.DATABASE_URL else {}
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base para modelos
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency injection para FastAPI.
    Fornece sessão do banco e garante fechamento.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Inicializa o banco de dados (cria tabelas)"""
    logger.info("Criando tabelas do banco de dados...")
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Tabelas criadas com sucesso")


def drop_db() -> None:
    """Remove todas as tabelas (CUIDADO: USE APENAS EM DESENVOLVIMENTO)"""
    if not settings.DEBUG:
        raise RuntimeError("drop_db() só pode ser executado em modo DEBUG")

    logger.warning("⚠️ Removendo todas as tabelas...")
    Base.metadata.drop_all(bind=engine)
    logger.warning("✅ Tabelas removidas")

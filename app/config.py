"""
Configurações centralizadas da aplicação usando Pydantic Settings.
Todas as variáveis de ambiente são validadas e type-safe.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import logging


class Settings(BaseSettings):
    """Configurações da aplicação com validação Pydantic"""

    # App
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Evolution API
    EVOLUTION_BASE_URL: str = "http://localhost:8080"
    EVOLUTION_API_KEY: str

    # AI APIs
    GEMINI_API_KEY: str
    OPENAI_API_KEY: Optional[str] = None

    # Webhook
    WEBHOOK_BASE_URL: Optional[str] = None

    # Security
    ENCRYPTION_KEY: Optional[str] = None  # Fernet key (auto-gerada se não fornecida)

    # Warmup Settings
    WARMUP_DAYS: int = 10
    MAX_NEW_CONTACTS_PER_DAY: int = 20
    MAX_MESSAGES_PER_HOUR: int = 4

    # Retry Settings
    MAX_RETRY_ATTEMPTS: int = 5
    RETRY_MIN_WAIT: int = 4
    RETRY_MAX_WAIT: int = 60

    # Shadow Mode Settings
    SHADOW_MODE_TIMEOUT: int = 300  # 5 minutos de inatividade do humano

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    def setup_logging(self) -> None:
        """Configura logging da aplicação"""
        logging.basicConfig(
            level=getattr(logging, self.LOG_LEVEL.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


# Instância global de configurações
settings = Settings()
settings.setup_logging()

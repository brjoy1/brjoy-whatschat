"""
Configuração de logging estruturado com suporte a JSON.
"""

import logging
import sys
from pythonjsonlogger import jsonlogger
from app.config import settings


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Formatador JSON customizado com campos adicionais"""

    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)

        # Adicionar campos customizados
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        log_record['timestamp'] = self.formatTime(record, self.datefmt)

        # Adicionar informações de contexto se disponíveis
        if hasattr(record, 'session'):
            log_record['session'] = record.session
        if hasattr(record, 'phone'):
            log_record['phone'] = record.phone
        if hasattr(record, 'lead_id'):
            log_record['lead_id'] = record.lead_id


def setup_logging():
    """Configura logging da aplicação"""

    # Determinar formato baseado em DEBUG
    if settings.DEBUG:
        # Formato legível para desenvolvimento
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        # Formato JSON para produção
        formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    # Configurar handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Configurar root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    root_logger.addHandler(handler)

    # Silenciar loggers muito verbosos
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO)


class LoggerAdapter(logging.LoggerAdapter):
    """Adapter para adicionar contexto aos logs"""

    def process(self, msg, kwargs):
        # Adicionar campos extras ao log
        if 'extra' not in kwargs:
            kwargs['extra'] = {}

        kwargs['extra'].update(self.extra)
        return msg, kwargs


def get_logger(name: str, **context):
    """Retorna logger com contexto adicional"""
    logger = logging.getLogger(name)
    if context:
        return LoggerAdapter(logger, context)
    return logger

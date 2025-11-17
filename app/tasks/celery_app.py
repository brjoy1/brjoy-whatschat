"""
Configuração do Celery para processamento assíncrono de mensagens.

Tarefas:
- Envio de mensagens com typing simulation
- Processamento de slots em background
- Sincronização com Evolution API
"""

from celery import Celery
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Criar app Celery
celery_app = Celery(
    "agentic_slot_filling",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.message_tasks"]
)

# Configurações do Celery
celery_app.conf.update(
    # Serialização
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task routing
    task_routes={
        "app.tasks.message_tasks.send_message_with_humanization": {
            "queue": "messages"
        },
        "app.tasks.message_tasks.process_lead_qualification": {
            "queue": "processing"
        },
    },

    # Retry settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # Result backend
    result_expires=3600,  # 1 hora

    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,

    # Logging
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s",
)

# Beat schedule (tarefas periódicas)
celery_app.conf.beat_schedule = {
    # Exemplo: limpeza de dados antigos a cada 24h
    "cleanup-old-messages": {
        "task": "app.tasks.message_tasks.cleanup_old_messages",
        "schedule": 86400.0,  # 24 horas
    },
}

logger.info("✅ Celery app configurado")

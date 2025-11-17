#!/usr/bin/env python3
"""
Script para inicializar o banco de dados.

Cria todas as tabelas necessárias usando SQLAlchemy.

Uso:
    python scripts/init_db.py
"""

import sys
import os

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import init_db, drop_db, engine
from app.config import settings
from sqlalchemy import inspect
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_existing_tables():
    """Verifica tabelas existentes"""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    return tables


def main():
    """Função principal"""
    logger.info("🚀 Inicializando banco de dados...")
    logger.info(f"Database URL: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'local'}")

    # Verificar tabelas existentes
    existing_tables = check_existing_tables()

    if existing_tables:
        logger.info(f"📋 Tabelas existentes: {', '.join(existing_tables)}")

        response = input("\n⚠️ Algumas tabelas já existem. Deseja recriá-las? (yes/no): ")

        if response.lower() == "yes":
            if not settings.DEBUG:
                logger.error("❌ Não é possível dropar tabelas em produção (DEBUG=false)")
                sys.exit(1)

            logger.warning("🗑️ Removendo tabelas existentes...")
            drop_db()
        else:
            logger.info("✅ Mantendo tabelas existentes")
            return

    # Criar tabelas
    logger.info("📝 Criando tabelas...")
    init_db()

    # Verificar criação
    new_tables = check_existing_tables()
    logger.info(f"✅ Tabelas criadas: {', '.join(new_tables)}")

    logger.info("\n🎉 Banco de dados inicializado com sucesso!")
    logger.info("\nPróximos passos:")
    logger.info("1. Criar sessão WhatsApp: python scripts/create_session.py --session <nome>")
    logger.info("2. Escanear QR code no WhatsApp")
    logger.info("3. Iniciar aplicação: docker-compose up backend")


if __name__ == "__main__":
    main()

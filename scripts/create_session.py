#!/usr/bin/env python3
"""
Script para criar sessão WhatsApp e gerar QR code.

Uso:
    python scripts/create_session.py --session minha-empresa
    python scripts/create_session.py --session minha-empresa --show-qr
"""

import sys
import os
import argparse
import asyncio

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import WhatsAppSession, SessionStatus
from app.services.evolution_client import EvolutionClient
from app.core.exceptions import EvolutionAPIError
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_whatsapp_session(session_name: str, show_qr: bool = False):
    """
    Cria sessão WhatsApp e exibe QR code.

    Args:
        session_name: Nome da sessão
        show_qr: Se True, exibe QR code no terminal
    """
    db = SessionLocal()

    try:
        # Verificar se sessão já existe
        existing = db.query(WhatsAppSession).filter(
            WhatsAppSession.session_name == session_name
        ).first()

        if existing:
            logger.warning(f"⚠️ Sessão '{session_name}' já existe no banco")
            logger.info(f"Status atual: {existing.status}")

            if existing.status == SessionStatus.CONNECTED:
                logger.info("✅ Sessão já está conectada!")
                return

            response = input("\nDeseja gerar novo QR code? (yes/no): ")
            if response.lower() != "yes":
                logger.info("❌ Operação cancelada")
                return

        # Criar Evolution client
        logger.info("📡 Conectando à Evolution API...")
        evolution = EvolutionClient()

        # Aguardar Evolution API estar pronta
        await evolution.check_health()

        # Criar instância
        logger.info(f"🔨 Criando instância '{session_name}'...")

        try:
            instance_response = await evolution.create_instance(session_name)
            logger.info("✅ Instância criada")
        except EvolutionAPIError as e:
            if "already exists" in str(e).lower():
                logger.warning("⚠️ Instância já existe no Evolution API")
            else:
                raise

        # Gerar QR code
        logger.info("📱 Gerando QR code...")
        qr_response = await evolution.get_qr_code(session_name)

        # Extrair QR code
        qr_code = qr_response.get("qrcode", {}).get("base64") or qr_response.get("code")

        if not qr_code:
            logger.error("❌ Não foi possível gerar QR code")
            logger.debug(f"Resposta: {qr_response}")
            return

        # Salvar no banco
        if existing:
            existing.qr_code = qr_code
            existing.status = SessionStatus.PENDING
            db.commit()
            logger.info("✅ QR code atualizado no banco")
        else:
            session = WhatsAppSession(
                session_name=session_name,
                status=SessionStatus.PENDING,
                qr_code=qr_code,
                metadata=instance_response
            )
            db.add(session)
            db.commit()
            logger.info("✅ Sessão criada no banco")

        # Exibir instruções
        logger.info("\n" + "="*60)
        logger.info("📱 QR CODE GERADO COM SUCESSO!")
        logger.info("="*60)

        if show_qr:
            # Tentar exibir QR code no terminal (requer qrcode package)
            try:
                import qrcode
                qr = qrcode.QRCode()
                qr.add_data(qr_code)
                qr.make()
                qr.print_ascii(invert=True)
            except ImportError:
                logger.warning("⚠️ Pacote 'qrcode' não instalado - não é possível exibir QR no terminal")
                logger.info("Instale com: pip install qrcode")

        logger.info("\nPara escanear o QR code:")
        logger.info("1. Abra WhatsApp no celular")
        logger.info("2. Vá em Configurações > Aparelhos conectados")
        logger.info("3. Toque em 'Conectar um aparelho'")
        logger.info("4. Escaneie o QR code exibido")
        logger.info("\nOu acesse via API:")
        logger.info(f"GET http://localhost:8000/api/v1/sessions/{session_name}")
        logger.info("\n" + "="*60)

        # Aguardar conexão
        logger.info("\n⏳ Aguardando conexão... (pressione Ctrl+C para cancelar)")

        for i in range(60):  # Aguardar até 60 segundos
            await asyncio.sleep(1)

            state = await evolution.get_connection_state(session_name)
            connection_state = state.get("state")

            if connection_state == "open":
                logger.info("\n✅ WhatsApp conectado com sucesso!")

                # Atualizar no banco
                session = db.query(WhatsAppSession).filter(
                    WhatsAppSession.session_name == session_name
                ).first()

                if session:
                    session.status = SessionStatus.CONNECTED
                    db.commit()

                logger.info(f"🎉 Sessão '{session_name}' está pronta para uso!")
                return

        logger.warning("\n⚠️ Timeout aguardando conexão")
        logger.info("Você pode verificar o status depois com:")
        logger.info(f"GET http://localhost:8000/api/v1/sessions/{session_name}")

    except KeyboardInterrupt:
        logger.info("\n\n❌ Operação cancelada pelo usuário")

    except Exception as e:
        logger.error(f"\n❌ Erro ao criar sessão: {e}", exc_info=True)

    finally:
        db.close()


def main():
    """Função principal"""
    parser = argparse.ArgumentParser(description="Criar sessão WhatsApp e gerar QR code")

    parser.add_argument(
        "--session",
        "-s",
        required=True,
        help="Nome da sessão (ex: minha-empresa)"
    )

    parser.add_argument(
        "--show-qr",
        action="store_true",
        help="Exibir QR code no terminal (requer pacote qrcode)"
    )

    args = parser.parse_args()

    # Executar
    asyncio.run(create_whatsapp_session(args.session, args.show_qr))


if __name__ == "__main__":
    main()

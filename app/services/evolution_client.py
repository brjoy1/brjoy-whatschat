"""
Cliente HTTP para Evolution API v2 com retry exponencial.

IMPORTANTE: Evolution API demora 20-30s para subir (Chrome headless).
Implementa retry automático para lidar com startup lento (FIX CRÍTICO 3).
"""

import httpx
from typing import Optional, Dict, Any
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from app.config import settings
from app.core.exceptions import EvolutionAPIError
import logging

logger = logging.getLogger(__name__)


class EvolutionClient:
    """
    Cliente HTTP para Evolution API v2.

    Features:
    - Retry exponencial automático (4s → 8s → 16s → 32s → 60s)
    - Health check com timeout de até 120s
    - Gerenciamento de conexões WhatsApp
    - Envio de mensagens e status de digitação
    """

    def __init__(self):
        self.base_url = settings.EVOLUTION_BASE_URL
        self.api_key = settings.EVOLUTION_API_KEY

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "apikey": self.api_key,
                "Content-Type": "application/json"
            },
            timeout=httpx.Timeout(
                connect=10.0,  # Conexão
                read=20.0,     # Leitura
                write=20.0,    # Escrita
                pool=5.0       # Pool de conexões
            ),
            limits=httpx.Limits(
                max_keepalive_connections=5,
                max_connections=10
            )
        )

    @retry(
        stop=stop_after_attempt(settings.MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(
            multiplier=1,
            min=settings.RETRY_MIN_WAIT,
            max=settings.RETRY_MAX_WAIT
        ),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.ConnectTimeout, httpx.TimeoutException)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    async def check_health(self) -> bool:
        """
        Health check com retry exponencial.

        🔧 FIX CRÍTICO 3: Retry automático
        Timing: 4s → 8s → 16s → 32s → 60s
        Total: até 120s de espera

        Returns:
            bool: True se API está disponível

        Raises:
            EvolutionAPIError: Se API não responder após todos os retries
        """
        try:
            response = await self.client.get("/")
            response.raise_for_status()
            logger.info("✅ Evolution API está disponível")
            return True
        except httpx.HTTPError as e:
            logger.warning(f"⚠️ Evolution API ainda não disponível: {e}")
            raise

    async def create_instance(self, session_name: str) -> Dict[str, Any]:
        """
        Cria nova instância WhatsApp.

        Args:
            session_name: Nome único da sessão

        Returns:
            dict: Dados da instância criada
        """
        try:
            payload = {
                "instanceName": session_name,
                "qrcode": True,
                "integration": "WHATSAPP-BAILEYS"
            }

            response = await self.client.post("/instance/create", json=payload)
            response.raise_for_status()
            logger.info(f"✅ Instância '{session_name}' criada")
            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"❌ Erro ao criar instância: {e}")
            raise EvolutionAPIError(
                f"Falha ao criar instância: {e}",
                {"session_name": session_name, "error": str(e)}
            )

    async def get_qr_code(self, session_name: str) -> Dict[str, Any]:
        """
        Gera QR code para conectar WhatsApp.

        Args:
            session_name: Nome da sessão

        Returns:
            dict: Contém 'code' (base64) ou 'pairingCode'
        """
        try:
            response = await self.client.get(f"/instance/connect/{session_name}")
            response.raise_for_status()
            logger.info(f"✅ QR code gerado para '{session_name}'")
            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"❌ Erro ao gerar QR code: {e}")
            raise EvolutionAPIError(
                f"Falha ao gerar QR: {e}",
                {"session_name": session_name, "error": str(e)}
            )

    async def get_connection_state(self, session_name: str) -> Dict[str, str]:
        """
        Verifica estado da conexão WhatsApp.

        Args:
            session_name: Nome da sessão

        Returns:
            dict: {"state": "open"|"close"|"connecting"}
        """
        try:
            response = await self.client.get(f"/instance/connectionState/{session_name}")
            response.raise_for_status()
            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"❌ Erro ao verificar estado: {e}")
            raise EvolutionAPIError(
                f"Falha ao verificar estado: {e}",
                {"session_name": session_name, "error": str(e)}
            )

    async def send_message(
        self,
        session_name: str,
        phone: str,
        text: str
    ) -> Dict[str, Any]:
        """
        Envia mensagem de texto.

        Args:
            session_name: Nome da sessão
            phone: Número com DDD (ex: 5511999999999)
            text: Conteúdo da mensagem

        Returns:
            dict: Dados da mensagem enviada
        """
        try:
            payload = {
                "number": phone,
                "text": text
            }

            response = await self.client.post(
                f"/message/sendText/{session_name}",
                json=payload
            )
            response.raise_for_status()
            logger.info(f"✅ Mensagem enviada para {phone}")
            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"❌ Erro ao enviar mensagem: {e}")
            raise EvolutionAPIError(
                f"Falha ao enviar mensagem: {e}",
                {"session_name": session_name, "phone": phone, "error": str(e)}
            )

    async def send_seen(self, session_name: str, phone: str) -> None:
        """
        Marca mensagens como lidas.

        Args:
            session_name: Nome da sessão
            phone: Número com DDD
        """
        try:
            payload = {
                "remoteJid": f"{phone}@s.whatsapp.net"
            }

            await self.client.post(
                f"/chat/markMessageAsRead/{session_name}",
                json=payload
            )
            logger.debug(f"✅ Mensagens marcadas como lidas para {phone}")

        except httpx.HTTPError as e:
            logger.warning(f"⚠️ Erro ao marcar como lido: {e}")
            # Não lança exceção - falha em 'seen' não é crítica

    async def update_presence(
        self,
        session_name: str,
        phone: str,
        state: str
    ) -> None:
        """
        Atualiza status de presença (digitando/pausado).

        Args:
            session_name: Nome da sessão
            phone: Número com DDD
            state: "composing" (digitando) ou "paused"
        """
        try:
            payload = {
                "number": phone,
                "state": state
            }

            await self.client.post(
                f"/chat/updatePresence/{session_name}",
                json=payload
            )
            logger.debug(f"✅ Presença atualizada para '{state}' - {phone}")

        except httpx.HTTPError as e:
            logger.warning(f"⚠️ Erro ao atualizar presença: {e}")
            # Não lança exceção - falha em presença não é crítica

    async def start_typing(self, session_name: str, phone: str) -> None:
        """Inicia indicador de digitação"""
        await self.update_presence(session_name, phone, "composing")

    async def stop_typing(self, session_name: str, phone: str) -> None:
        """Para indicador de digitação"""
        await self.update_presence(session_name, phone, "paused")

    async def logout_instance(self, session_name: str) -> Dict[str, Any]:
        """
        Desconecta sessão WhatsApp (mantém instância).

        Args:
            session_name: Nome da sessão

        Returns:
            dict: Status do logout
        """
        try:
            response = await self.client.delete(f"/instance/logout/{session_name}")
            response.raise_for_status()
            logger.info(f"✅ Logout realizado para '{session_name}'")
            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"❌ Erro ao fazer logout: {e}")
            raise EvolutionAPIError(
                f"Falha ao fazer logout: {e}",
                {"session_name": session_name, "error": str(e)}
            )

    async def delete_instance(self, session_name: str) -> Dict[str, Any]:
        """
        Remove instância completamente.

        Args:
            session_name: Nome da sessão

        Returns:
            dict: Status da remoção
        """
        try:
            response = await self.client.delete(f"/instance/delete/{session_name}")
            response.raise_for_status()
            logger.info(f"✅ Instância '{session_name}' removida")
            return response.json()

        except httpx.HTTPError as e:
            logger.error(f"❌ Erro ao remover instância: {e}")
            raise EvolutionAPIError(
                f"Falha ao remover instância: {e}",
                {"session_name": session_name, "error": str(e)}
            )

    async def close(self) -> None:
        """Fecha conexão HTTP"""
        await self.client.aclose()
        logger.debug("✅ Cliente Evolution API fechado")


# Singleton para dependency injection (thread-safe)
import threading

_evolution_client: Optional[EvolutionClient] = None
_client_lock = threading.Lock()


async def get_evolution_client() -> EvolutionClient:
    """
    Dependency injection para FastAPI.
    Cria instância única e valida conexão (thread-safe).

    Returns:
        EvolutionClient: Cliente configurado
    """
    global _evolution_client

    # Double-checked locking pattern
    if _evolution_client is None:
        with _client_lock:
            if _evolution_client is None:
                _evolution_client = EvolutionClient()
                await _evolution_client.check_health()

    return _evolution_client

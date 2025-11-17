"""
Simulador de digitação humana para humanização de mensagens WhatsApp.

Implementa delays realistas entre ações:
- Leitura de mensagem (seen)
- Tempo de processamento cognitivo
- Indicador de digitação
- Pausa antes de enviar
"""

import asyncio
import random
from app.services.evolution_client import EvolutionClient
import logging

logger = logging.getLogger(__name__)


class TypingSimulator:
    """
    Simula comportamento humano ao enviar mensagens.

    Padrão de timing:
    1. Marcar como lido (instantâneo)
    2. Delay de leitura: 2-4s (tempo para ler a mensagem)
    3. Iniciar digitação
    4. Tempo de digitação: ~1.2s por caractere (com limite 3-30s)
    5. Parar digitação
    6. Pausa antes de enviar: 0.5-2s
    7. Enviar mensagem
    """

    # Constantes de timing (em segundos)
    READ_DELAY_MIN = 2.0
    READ_DELAY_MAX = 4.0

    TYPING_SPEED_MIN = 1.0  # segundos por caractere
    TYPING_SPEED_MAX = 1.5
    TYPING_TIME_MIN = 3.0   # tempo mínimo de digitação
    TYPING_TIME_MAX = 30.0  # tempo máximo de digitação

    PRE_SEND_DELAY_MIN = 0.5
    PRE_SEND_DELAY_MAX = 2.0

    def __init__(self, evolution_client: EvolutionClient):
        """
        Inicializa simulador.

        Args:
            evolution_client: Cliente da Evolution API
        """
        self.client = evolution_client

    async def send_with_humanization(
        self,
        session: str,
        phone: str,
        message: str,
        enable_humanization: bool = True
    ) -> dict:
        """
        Envia mensagem com delays humanizados.

        Args:
            session: Nome da sessão WhatsApp
            phone: Número do destinatário
            message: Conteúdo da mensagem
            enable_humanization: Se False, envia imediatamente

        Returns:
            dict: Resposta da Evolution API
        """
        if not enable_humanization:
            logger.info(f"📤 Enviando mensagem SEM humanização para {phone}")
            return await self.client.send_message(session, phone, message)

        logger.info(f"🤖 Iniciando envio humanizado para {phone}")

        try:
            # Passo 1: Marcar como lido
            await self.client.send_seen(session, phone)
            logger.debug("✓ Mensagem marcada como lida")

            # Passo 2: Delay de leitura (2-4s)
            read_delay = random.uniform(self.READ_DELAY_MIN, self.READ_DELAY_MAX)
            logger.debug(f"⏱️ Aguardando {read_delay:.1f}s (leitura)")
            await asyncio.sleep(read_delay)

            # Passo 3: Iniciar digitação
            await self.client.start_typing(session, phone)
            logger.debug("✓ Digitação iniciada")

            # Passo 4: Calcular tempo de digitação baseado no tamanho
            chars = len(message)
            typing_time = chars * random.uniform(self.TYPING_SPEED_MIN, self.TYPING_SPEED_MAX)

            # Limitar entre min e max
            typing_time = max(self.TYPING_TIME_MIN, min(typing_time, self.TYPING_TIME_MAX))

            logger.debug(f"⏱️ Digitando por {typing_time:.1f}s ({chars} caracteres)")
            await asyncio.sleep(typing_time)

            # Passo 5: Parar digitação
            await self.client.stop_typing(session, phone)
            logger.debug("✓ Digitação parada")

            # Passo 6: Pausa antes de enviar
            pre_send_delay = random.uniform(self.PRE_SEND_DELAY_MIN, self.PRE_SEND_DELAY_MAX)
            logger.debug(f"⏱️ Aguardando {pre_send_delay:.1f}s (antes de enviar)")
            await asyncio.sleep(pre_send_delay)

            # Passo 7: Enviar mensagem
            response = await self.client.send_message(session, phone, message)
            logger.info(f"✅ Mensagem humanizada enviada para {phone}")

            return response

        except Exception as e:
            logger.error(f"❌ Erro ao enviar mensagem humanizada: {e}")
            # Tentar enviar sem humanização em caso de erro
            logger.warning("⚠️ Tentando enviar sem humanização...")
            return await self.client.send_message(session, phone, message)

    def calculate_total_delay(self, message: str) -> float:
        """
        Calcula tempo total estimado de delay (útil para testes).

        Args:
            message: Mensagem a ser enviada

        Returns:
            float: Tempo total em segundos
        """
        read_delay = (self.READ_DELAY_MIN + self.READ_DELAY_MAX) / 2

        chars = len(message)
        typing_time = chars * ((self.TYPING_SPEED_MIN + self.TYPING_SPEED_MAX) / 2)
        typing_time = max(self.TYPING_TIME_MIN, min(typing_time, self.TYPING_TIME_MAX))

        pre_send_delay = (self.PRE_SEND_DELAY_MIN + self.PRE_SEND_DELAY_MAX) / 2

        total = read_delay + typing_time + pre_send_delay
        return total


async def send_humanized_message(
    evolution_client: EvolutionClient,
    session: str,
    phone: str,
    message: str
) -> dict:
    """
    Função helper para enviar mensagem humanizada.

    Args:
        evolution_client: Cliente da Evolution API
        session: Nome da sessão
        phone: Número do destinatário
        message: Conteúdo da mensagem

    Returns:
        dict: Resposta da Evolution API
    """
    simulator = TypingSimulator(evolution_client)
    return await simulator.send_with_humanization(session, phone, message)

"""
Gerador de respostas contextuais para conversas.

Complementa o slot_extractor gerando respostas mais naturais
além das perguntas de slot filling.
"""

from app.schemas import LeadImobiliaria
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class ResponseGenerator:
    """Gera respostas contextuais e naturais"""

    # Templates de respostas
    GREETING_RESPONSES = [
        "Olá! 👋 Sou o assistente virtual da {empresa}. Como posso ajudar você hoje?",
        "Oi! 😊 Seja bem-vindo(a)! Estou aqui para ajudar a encontrar o imóvel ideal. Como posso te ajudar?",
        "Olá! Tudo bem? Sou o assistente da {empresa}. No que posso te ajudar?",
    ]

    ACKNOWLEDGMENT_RESPONSES = [
        "Entendi! ✅",
        "Perfeito! 👍",
        "Ótimo! 😊",
        "Certo! ✓",
        "Anotado! 📝",
    ]

    def __init__(self, empresa_nome: str = "Imobiliária"):
        """
        Inicializa generator.

        Args:
            empresa_nome: Nome da empresa para personalizar respostas
        """
        self.empresa_nome = empresa_nome

    def generate_greeting(self, nome: Optional[str] = None) -> str:
        """
        Gera saudação inicial.

        Args:
            nome: Nome do lead (se conhecido)

        Returns:
            str: Mensagem de saudação
        """
        import random
        base_greeting = random.choice(self.GREETING_RESPONSES)
        greeting = base_greeting.format(empresa=self.empresa_nome)

        if nome:
            greeting = f"Olá, {nome}! 👋 " + greeting

        return greeting

    def generate_acknowledgment(self) -> str:
        """
        Gera resposta de reconhecimento rápida.

        Returns:
            str: Mensagem de reconhecimento
        """
        import random
        return random.choice(self.ACKNOWLEDGMENT_RESPONSES)

    def generate_qualification_complete(self, lead: LeadImobiliaria) -> str:
        """
        Gera mensagem de finalização quando lead está qualificado.

        Args:
            lead: Lead com todos slots preenchidos

        Returns:
            str: Mensagem de conclusão
        """
        nome = lead.nome or "cliente"

        message = f"Perfeito, {nome}! 🎉\n\n"
        message += "Tenho todas as informações que preciso:\n\n"

        # Resumir informações
        if lead.tipo_imovel and lead.finalidade:
            tipo_texto = "comprar" if lead.finalidade == "comprar" else "alugar"
            message += f"🏠 {tipo_texto.capitalize()} {lead.tipo_imovel}\n"

        if lead.localizacao_desejada:
            message += f"📍 {lead.localizacao_desejada}\n"

        if lead.num_quartos:
            message += f"🛏️ {lead.num_quartos} quartos\n"

        if lead.orcamento_max:
            message += f"💰 Até R$ {lead.orcamento_max:,.2f}\n"

        message += "\n"
        message += "Nossa equipe entrará em contato em breve com opções personalizadas para você.\n\n"
        message += "Muito obrigado! 😊"

        return message

    def generate_partial_summary(self, lead: LeadImobiliaria) -> str:
        """
        Gera resumo parcial das informações coletadas.

        Args:
            lead: Lead com slots parcialmente preenchidos

        Returns:
            str: Resumo das informações
        """
        slots_filled = lead.slots_preenchidos()

        if slots_filled == 0:
            return "Vou te ajudar a encontrar o imóvel ideal! Vamos começar?"

        message = "Deixa eu resumir o que já entendi:\n\n"

        if lead.tipo_imovel:
            message += f"✓ Tipo: {lead.tipo_imovel}\n"

        if lead.finalidade:
            message += f"✓ Finalidade: {lead.finalidade}\n"

        if lead.localizacao_desejada:
            message += f"✓ Localização: {lead.localizacao_desejada}\n"

        if lead.num_quartos:
            message += f"✓ Quartos: {lead.num_quartos}\n"

        if lead.orcamento_max:
            message += f"✓ Orçamento: até R$ {lead.orcamento_max:,.2f}\n"

        message += f"\nTenho {slots_filled} de 11 informações. "
        message += "Vamos continuar?"

        return message

    def generate_error_response(self, error_type: str = "generic") -> str:
        """
        Gera mensagem de erro amigável.

        Args:
            error_type: Tipo de erro (generic, timeout, unavailable)

        Returns:
            str: Mensagem de erro
        """
        error_messages = {
            "generic": (
                "Desculpe, tive um problema temporário. 😅\n"
                "Pode repetir sua mensagem, por favor?"
            ),
            "timeout": (
                "Ops, demorei demais para responder. 😓\n"
                "Ainda está aí? Podemos continuar?"
            ),
            "unavailable": (
                "Estou com dificuldades técnicas no momento. 🔧\n"
                "Nossa equipe já foi notificada. Tente novamente em instantes!"
            ),
        }

        return error_messages.get(error_type, error_messages["generic"])

    def generate_clarification_request(self, field: str) -> str:
        """
        Gera pedido de esclarecimento para campo específico.

        Args:
            field: Campo que precisa de esclarecimento

        Returns:
            str: Mensagem pedindo esclarecimento
        """
        clarifications = {
            "tipo_imovel": "Você está procurando casa, apartamento, terreno ou imóvel comercial? 🏠",
            "finalidade": "Você quer comprar ou alugar? 🤝",
            "localizacao_desejada": "Em qual bairro ou região você prefere? 📍",
            "num_quartos": "Quantos quartos você precisa? 🛏️",
            "orcamento_max": "Qual é o seu orçamento máximo? 💰",
            "nome": "Qual é o seu nome? 😊",
            "telefone": "Qual o melhor telefone para contato (com DDD)? 📱",
            "email": "Qual é o seu e-mail? 📧",
        }

        return clarifications.get(
            field,
            f"Pode me dar mais informações sobre {field}?"
        )

    def generate_warmup_limit_message(self) -> str:
        """
        Gera mensagem quando limite de warmup é atingido.

        Returns:
            str: Mensagem explicando o atraso
        """
        return (
            "Obrigado pelo contato! 🙏\n\n"
            "Estamos com alto volume de conversas no momento. "
            "Nossa equipe entrará em contato em breve.\n\n"
            "Fique à vontade para deixar suas informações e preferências aqui "
            "que responderemos assim que possível!"
        )


# Singleton para uso global
_response_generator: Optional[ResponseGenerator] = None


def get_response_generator(empresa_nome: str = "Imobiliária") -> ResponseGenerator:
    """
    Dependency injection para ResponseGenerator.

    Args:
        empresa_nome: Nome da empresa

    Returns:
        ResponseGenerator: Generator configurado
    """
    global _response_generator

    if _response_generator is None:
        _response_generator = ResponseGenerator(empresa_nome)

    return _response_generator

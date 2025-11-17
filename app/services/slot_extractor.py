"""
Extrator de slots usando PydanticAI + Gemini Flash.

Features:
- Extração type-safe com validação automática
- Merge inteligente de slots incrementais
- Geração de perguntas contextual
- Tolerância a erros de digitação e gírias
"""

from pydantic_ai import Agent
from pydantic_ai.models.gemini import GeminiModel
import google.generativeai as genai
from app.schemas import LeadImobiliaria
from app.config import settings
from app.core.exceptions import SlotExtractionError
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class SlotExtractor:
    """Extrator de slots usando PydanticAI + Gemini Flash"""

    SYSTEM_PROMPT = """Você é um assistente inteligente de triagem para imobiliária brasileira.

INSTRUÇÕES CRÍTICAS:
1. Extraia TODAS as informações mencionadas pelo cliente
2. Se algo não foi dito, deixe como null (NUNCA invente dados)
3. Seja tolerante com erros de digitação e gírias brasileiras
4. Entenda variações comuns:
   - "apto" = apartamento
   - "ap" = apartamento
   - "to procurando" = finalidade comprar
   - "quero alugar" = finalidade alugar
   - "casa" = tipo_imovel casa

5. Interprete datas relativas:
   - "urgente", "rápido", "logo" = timeline urgente
   - "mês que vem", "próximo mês" = timeline 1_mes
   - "3 meses", "alguns meses" = timeline 3_meses
   - "sem pressa", "qualquer hora" = timeline sem_pressa

6. Normalize orçamentos:
   - "500 mil" → 500000.0
   - "R$ 300k" → 300000.0
   - "trezentos mil" → 300000.0
   - "meio milhão" → 500000.0
   - "1.5 milhão" → 1500000.0

7. Telefones:
   - Se vier sem DDD ou incompleto, deixe null
   - Aceite formatos: (11) 99999-9999, 11999999999, 11 9 9999-9999

8. Localizações:
   - Normalize bairros conhecidos de SP: "pinheiros", "morumbi", "vila mariana"
   - Mantenha como digitado se não reconhecer

EXEMPLOS DE EXTRAÇÃO:

Cliente: "quero apto 2 quartos pinheiros 500k"
→ tipo_imovel=apartamento, num_quartos=2, localizacao=Pinheiros, orcamento_max=500000

Cliente: "preciso urgente uma casa"
→ tipo_imovel=casa, timeline=urgente

Cliente: "meu orçamento é até 300 mil pra alugar"
→ orcamento_max=300000, finalidade=alugar

Cliente: "meu nome é João Silva, telefone 11 98765-4321"
→ nome=João Silva, telefone=11987654321

Cliente: "quero comprar um terreno na zona sul, até 200k"
→ tipo_imovel=terreno, finalidade=comprar, localizacao_desejada=Zona Sul, orcamento_max=200000

IMPORTANTE: Seja preciso e não force interpretações. Se não tiver certeza, deixe null.
"""

    def __init__(self):
        """Inicializa agente PydanticAI com Gemini Flash"""
        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)

            self.agent = Agent(
                model=GeminiModel('gemini-1.5-flash'),
                result_type=LeadImobiliaria,
                system_prompt=self.SYSTEM_PROMPT,
                retries=3
            )

            logger.info("✅ SlotExtractor inicializado com Gemini Flash")

        except Exception as e:
            logger.error(f"❌ Erro ao inicializar SlotExtractor: {e}")
            raise SlotExtractionError(
                f"Falha ao configurar Gemini: {e}",
                {"error": str(e)}
            )

    async def extract_from_messages(
        self,
        messages: list[str],
        current_slots: Optional[LeadImobiliaria] = None
    ) -> LeadImobiliaria:
        """
        Extrai slots de uma lista de mensagens.

        Args:
            messages: Lista de mensagens do cliente
            current_slots: Slots já preenchidos (para merge incremental)

        Returns:
            LeadImobiliaria: Slots atualizados

        Raises:
            SlotExtractionError: Se extração falhar
        """
        try:
            # Montar contexto da conversa
            contexto = "\n".join([f"Cliente: {msg}" for msg in messages])

            # Adicionar slots já preenchidos ao contexto
            if current_slots:
                slots_preenchidos = {
                    k: v for k, v in current_slots.model_dump().items()
                    if v is not None
                }
                if slots_preenchidos:
                    contexto += f"\n\n[Informações já coletadas: {slots_preenchidos}]"

            # Executar extração com PydanticAI
            logger.debug(f"Extraindo slots de {len(messages)} mensagens")
            result = await self.agent.run(
                f"Extraia as informações desta conversa:\n\n{contexto}"
            )

            extracted = result.data

            # Merge com slots existentes (prioriza novos dados)
            if current_slots:
                merged_data = current_slots.model_dump()

                for field, value in extracted.model_dump().items():
                    if value is not None:
                        merged_data[field] = value

                final_lead = LeadImobiliaria(**merged_data)
            else:
                final_lead = extracted

            slots_count = final_lead.slots_preenchidos()
            logger.info(f"✅ Slots extraídos: {slots_count}/11")

            return final_lead

        except Exception as e:
            logger.error(f"❌ Erro na extração de slots: {e}")

            # Retorna slots atuais em caso de erro
            if current_slots:
                return current_slots

            # Se não há slots atuais, retorna schema vazio
            return LeadImobiliaria()

    def get_next_question(self, lead: LeadImobiliaria) -> Optional[str]:
        """
        Gera próxima pergunta baseada em slots faltantes.

        Prioridade:
        1. Campos críticos (nome, telefone, tipo_imovel, finalidade)
        2. Campos importantes (localização, quartos, orçamento, timeline)
        3. Campos opcionais (observações)

        Args:
            lead: Lead com slots atuais

        Returns:
            str: Próxima pergunta ou None se todos slots críticos preenchidos
        """
        # Verificar campos críticos
        criticos_faltando = lead.slots_criticos_faltando()

        if criticos_faltando:
            perguntas_criticas = {
                'nome': "Antes de continuarmos, qual é o seu nome? 😊",
                'telefone': "Qual o melhor telefone para contato (com DDD)? 📱",
                'tipo_imovel': "Você está procurando casa, apartamento ou outro tipo de imóvel? 🏠",
                'finalidade': "Você quer comprar ou alugar? 🤝"
            }

            return perguntas_criticas.get(criticos_faltando[0])

        # Campos críticos preenchidos - perguntar campos importantes
        if not lead.localizacao_desejada:
            return "Em qual região ou bairro você prefere? 📍"

        if not lead.num_quartos and lead.tipo_imovel in ["apartamento", "casa"]:
            return "Quantos quartos você precisa? 🛏️"

        if not lead.orcamento_max:
            if lead.finalidade == "alugar":
                return "Qual é o valor máximo de aluguel que você pode pagar? 💰"
            else:
                return "Qual é o seu orçamento máximo para compra? 💰"

        if not lead.timeline:
            return "Qual a urgência? É para logo ou pode ser nos próximos meses? ⏰"

        # Todos campos importantes preenchidos
        return None

    def generate_qualification_summary(self, lead: LeadImobiliaria) -> str:
        """
        Gera resumo de qualificação do lead.

        Args:
            lead: Lead com slots preenchidos

        Returns:
            str: Resumo formatado
        """
        slots = lead.slots_preenchidos()
        criticos = len(lead.slots_criticos_faltando())

        summary_parts = [
            f"📊 Qualificação: {slots}/11 campos preenchidos",
        ]

        if criticos == 0:
            summary_parts.append("✅ Campos críticos completos")
        else:
            summary_parts.append(f"⚠️ {criticos} campos críticos faltando")

        # Adicionar informações principais
        if lead.tipo_imovel:
            tipo_texto = "Comprar" if lead.finalidade == "comprar" else "Alugar"
            summary_parts.append(f"🏠 {tipo_texto} {lead.tipo_imovel}")

        if lead.localizacao_desejada:
            summary_parts.append(f"📍 {lead.localizacao_desejada}")

        if lead.orcamento_max:
            summary_parts.append(f"💰 Até R$ {lead.orcamento_max:,.2f}")

        if lead.timeline:
            summary_parts.append(f"⏰ {lead.timeline}")

        return " | ".join(summary_parts)


# Singleton para dependency injection
_slot_extractor: Optional[SlotExtractor] = None


def get_slot_extractor() -> SlotExtractor:
    """
    Dependency injection para FastAPI.

    Returns:
        SlotExtractor: Extrator configurado
    """
    global _slot_extractor

    if _slot_extractor is None:
        _slot_extractor = SlotExtractor()

    return _slot_extractor

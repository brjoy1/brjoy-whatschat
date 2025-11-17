#!/usr/bin/env python3
"""
Script para testar extração de slots com PydanticAI.

Uso:
    python scripts/test_extraction.py
    python scripts/test_extraction.py --interactive
"""

import sys
import os
import asyncio
import argparse

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.slot_extractor import SlotExtractor
from app.schemas import LeadImobiliaria
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Casos de teste
TEST_CASES = [
    {
        "name": "Caso completo",
        "messages": [
            "Oi, quero comprar um apartamento de 2 quartos em Pinheiros",
            "Meu orçamento é até 500 mil",
            "Meu nome é João Silva",
            "Telefone é 11 98765-4321"
        ],
        "expected_slots": 7
    },
    {
        "name": "Gírias e abreviações",
        "messages": [
            "to procurando um apto no morumbi",
            "preciso urgente, até 300k"
        ],
        "expected_slots": 4
    },
    {
        "name": "Normalização de valores",
        "messages": [
            "quero alugar uma casa",
            "meu orçamento é 5 mil por mês",
            "3 quartos, zona sul"
        ],
        "expected_slots": 5
    },
    {
        "name": "Incremental (merge de slots)",
        "messages": [
            "Procuro casa",
            "Para comprar",
            "Em Campinas",
            "Até 400 mil"
        ],
        "expected_slots": 4
    },
]


async def test_extraction_case(extractor: SlotExtractor, test_case: dict):
    """
    Testa um caso de extração.

    Args:
        extractor: SlotExtractor
        test_case: Dicionário com caso de teste
    """
    logger.info("\n" + "="*60)
    logger.info(f"📝 Teste: {test_case['name']}")
    logger.info("="*60)

    messages = test_case["messages"]
    expected_slots = test_case.get("expected_slots", 0)

    # Extrair slots
    logger.info("\n📥 Mensagens:")
    for i, msg in enumerate(messages, 1):
        logger.info(f"  {i}. {msg}")

    logger.info("\n🧠 Extraindo slots...")
    lead = await extractor.extract_from_messages(messages)

    # Exibir resultado
    logger.info("\n✅ Slots extraídos:")
    logger.info(f"  Total: {lead.slots_preenchidos()}/{11} slots")

    slots_dict = lead.model_dump()
    for field, value in slots_dict.items():
        if value is not None:
            logger.info(f"  ✓ {field}: {value}")

    # Verificar campos críticos
    missing_critical = lead.slots_criticos_faltando()
    if missing_critical:
        logger.warning(f"\n⚠️ Campos críticos faltando: {', '.join(missing_critical)}")
    else:
        logger.info("\n✅ Todos campos críticos preenchidos!")

    # Gerar próxima pergunta
    next_question = extractor.get_next_question(lead)
    if next_question:
        logger.info(f"\n❓ Próxima pergunta: {next_question}")
    else:
        logger.info("\n🎉 Lead completamente qualificado!")

    # Verificar expectativa
    if expected_slots > 0:
        if lead.slots_preenchidos() >= expected_slots:
            logger.info(f"\n✅ PASSOU: {lead.slots_preenchidos()} >= {expected_slots} slots esperados")
        else:
            logger.warning(f"\n⚠️ FALHOU: {lead.slots_preenchidos()} < {expected_slots} slots esperados")

    # Resumo de qualificação
    summary = extractor.generate_qualification_summary(lead)
    logger.info(f"\n📊 {summary}")


async def interactive_mode(extractor: SlotExtractor):
    """
    Modo interativo para testar extração.

    Args:
        extractor: SlotExtractor
    """
    logger.info("\n" + "="*60)
    logger.info("🎮 MODO INTERATIVO")
    logger.info("="*60)
    logger.info("Digite mensagens como se fosse um cliente interessado em imóveis.")
    logger.info("Digite 'sair' para encerrar.\n")

    messages = []
    current_lead = LeadImobiliaria()

    while True:
        try:
            message = input("Cliente: ").strip()

            if not message:
                continue

            if message.lower() in ["sair", "exit", "quit"]:
                logger.info("\n👋 Encerrando modo interativo")
                break

            messages.append(message)

            # Extrair slots
            logger.info("🧠 Analisando...")
            current_lead = await extractor.extract_from_messages(messages, current_lead)

            # Exibir slots atualizados
            logger.info(f"\n📊 Slots: {current_lead.slots_preenchidos()}/11")

            slots_dict = current_lead.model_dump()
            filled = {k: v for k, v in slots_dict.items() if v is not None}

            if filled:
                logger.info("Informações coletadas:")
                for field, value in filled.items():
                    logger.info(f"  ✓ {field}: {value}")

            # Gerar próxima pergunta
            next_question = extractor.get_next_question(current_lead)

            if next_question:
                logger.info(f"\nAssistente: {next_question}\n")
            else:
                logger.info("\n🎉 Lead completamente qualificado!")
                summary = extractor.generate_qualification_summary(current_lead)
                logger.info(f"📊 {summary}\n")

                response = input("\nComeçar nova conversa? (yes/no): ")
                if response.lower() == "yes":
                    messages = []
                    current_lead = LeadImobiliaria()
                    logger.info("\n🔄 Nova conversa iniciada\n")
                else:
                    break

        except KeyboardInterrupt:
            logger.info("\n\n👋 Encerrando...")
            break

        except Exception as e:
            logger.error(f"\n❌ Erro: {e}", exc_info=True)


async def run_tests(interactive: bool = False):
    """
    Executa testes de extração.

    Args:
        interactive: Se True, entra em modo interativo
    """
    logger.info("🚀 Inicializando SlotExtractor...")

    try:
        extractor = SlotExtractor()
        logger.info("✅ SlotExtractor inicializado")

        if interactive:
            await interactive_mode(extractor)
        else:
            # Executar casos de teste
            for test_case in TEST_CASES:
                await test_extraction_case(extractor, test_case)

            logger.info("\n" + "="*60)
            logger.info("✅ Todos os testes concluídos!")
            logger.info("="*60)
            logger.info("\nPara modo interativo:")
            logger.info("python scripts/test_extraction.py --interactive")

    except Exception as e:
        logger.error(f"❌ Erro ao executar testes: {e}", exc_info=True)


def main():
    """Função principal"""
    parser = argparse.ArgumentParser(description="Testar extração de slots")

    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Modo interativo (conversa em tempo real)"
    )

    args = parser.parse_args()

    # Executar
    asyncio.run(run_tests(args.interactive))


if __name__ == "__main__":
    main()

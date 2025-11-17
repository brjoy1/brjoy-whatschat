#!/usr/bin/env python3
"""
Script para gerar chave de criptografia Fernet.

A chave gerada deve ser adicionada ao .env como ENCRYPTION_KEY.

Uso:
    python scripts/generate_encryption_key.py
"""

from cryptography.fernet import Fernet


def main():
    """Gera nova chave Fernet"""
    print("🔐 Gerando chave de criptografia Fernet...\n")

    # Gerar chave
    key = Fernet.generate_key()
    key_str = key.decode()

    print("="*60)
    print("✅ CHAVE GERADA COM SUCESSO!")
    print("="*60)
    print(f"\n{key_str}\n")
    print("="*60)
    print("\n📝 Adicione esta chave ao arquivo .env:\n")
    print(f"ENCRYPTION_KEY={key_str}")
    print("\n⚠️ IMPORTANTE:")
    print("- Mantenha esta chave em segredo")
    print("- Não commite no Git")
    print("- Se perder a chave, dados criptografados serão irrecuperáveis")
    print("- Use a mesma chave em todos os ambientes (dev, staging, prod)")
    print("\n" + "="*60)


if __name__ == "__main__":
    main()

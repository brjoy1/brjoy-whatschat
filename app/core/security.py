"""
Funções de segurança e criptografia.
Implementa criptografia Fernet para dados sensíveis (LGPD compliance).
"""

from cryptography.fernet import Fernet
from app.config import settings
from app.core.exceptions import EncryptionError
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class EncryptionManager:
    """Gerenciador de criptografia para dados sensíveis"""

    def __init__(self):
        """Inicializa com chave Fernet"""
        if settings.ENCRYPTION_KEY:
            self.key = settings.ENCRYPTION_KEY.encode()
        else:
            # Auto-gera chave se não fornecida (APENAS PARA DESENVOLVIMENTO)
            self.key = Fernet.generate_key()
            logger.warning(
                "⚠️ ENCRYPTION_KEY não definida! Gerando chave temporária. "
                "Em produção, defina ENCRYPTION_KEY no .env"
            )

        try:
            self.fernet = Fernet(self.key)
        except Exception as e:
            raise EncryptionError(
                f"Falha ao inicializar Fernet: {e}",
                {"error": str(e)}
            )

    def encrypt(self, plaintext: str) -> str:
        """Criptografa texto usando Fernet"""
        if not plaintext:
            return ""

        try:
            encrypted_bytes = self.fernet.encrypt(plaintext.encode())
            return encrypted_bytes.decode()
        except Exception as e:
            raise EncryptionError(
                f"Falha ao criptografar dados: {e}",
                {"error": str(e)}
            )

    def decrypt(self, ciphertext: str) -> str:
        """Descriptografa texto usando Fernet"""
        if not ciphertext:
            return ""

        try:
            decrypted_bytes = self.fernet.decrypt(ciphertext.encode())
            return decrypted_bytes.decode()
        except Exception as e:
            raise EncryptionError(
                f"Falha ao descriptografar dados: {e}",
                {"error": str(e)}
            )

    def encrypt_phone(self, phone: str) -> str:
        """Criptografa número de telefone"""
        return self.encrypt(phone)

    def decrypt_phone(self, encrypted_phone: str) -> str:
        """Descriptografa número de telefone"""
        return self.decrypt(encrypted_phone)

    def encrypt_email(self, email: str) -> str:
        """Criptografa email"""
        return self.encrypt(email)

    def decrypt_email(self, encrypted_email: str) -> str:
        """Descriptografa email"""
        return self.decrypt(encrypted_email)


# Instância global do gerenciador de criptografia
encryption_manager = EncryptionManager()


def generate_fernet_key() -> str:
    """Gera uma nova chave Fernet para uso em produção"""
    key = Fernet.generate_key()
    return key.decode()


if __name__ == "__main__":
    # Utilitário para gerar chave
    print("Nova chave Fernet gerada:")
    print(generate_fernet_key())
    print("\nAdicione esta chave ao .env como ENCRYPTION_KEY=<chave>")

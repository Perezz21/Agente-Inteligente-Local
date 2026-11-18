"""Configurações da aplicação e do serviço local do Ollama."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def load_local_environment() -> None:
    """Carrega o .env da raiz sem substituir variáveis existentes."""
    raiz = Path(__file__).resolve().parents[2]
    load_dotenv(dotenv_path=raiz / ".env", override=False)


@dataclass(frozen=True)
class OllamaConfig:
    """Configurações para conexão com uma instância local do Ollama."""

    host: str = "http://localhost:11434"
    model: str = ""

    @classmethod
    def from_environment(cls) -> "OllamaConfig":
        """Carrega as configurações das variáveis de ambiente."""
        load_local_environment()
        return cls(
            host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            model=os.getenv("OLLAMA_MODEL", ""),
        )

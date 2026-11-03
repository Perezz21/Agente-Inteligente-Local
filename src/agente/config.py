"""Configurações da aplicação e do serviço local do Ollama."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class OllamaConfig:
    """Configurações para conexão com uma instância local do Ollama."""

    host: str = "http://localhost:11434"
    model: str = ""

    @classmethod
    def from_environment(cls) -> "OllamaConfig":
        """Carrega as configurações das variáveis de ambiente."""
        return cls(
            host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            model=os.getenv("OLLAMA_MODEL", ""),
        )

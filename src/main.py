"""Ponto de entrada para testar a integração local com o Ollama."""

from src.agente.config import OllamaConfig
from src.agente.ollama_client import OllamaModelClient, OllamaModelError


def main() -> None:
    config = OllamaConfig.from_environment()

    try:
        model_client = OllamaModelClient(config)
        available_models = model_client.check_connection()

        print("Conexão com o Ollama estabelecida.")
        print("Modelos disponíveis:")
        for model in available_models:
            print(f"- {model}")

        if config.model not in available_models:
            print(
                f"\nAviso: o modelo configurado ('{config.model}') "
                "não apareceu na lista de modelos instalados."
            )
            return

        answer = model_client.generate(
            prompt=(
                "Responda em português, em uma frase: "
                "qual é a sua função neste projeto?"
            )
        )
        print("\nResposta do modelo:")
        print(answer)

    except OllamaModelError as exc:
        print(f"Erro: {exc}")


if __name__ == "__main__":
    main()

"""Integração inicial com modelos executados localmente pelo Ollama."""

from ollama import Client

from src.agente.config import OllamaConfig


class OllamaModelError(RuntimeError):
    """Erro de configuração ou comunicação com o modelo local."""


class OllamaModelClient:
    """Cliente simples para trocar o modelo sem alterar o restante do código."""

    def __init__(self, config: OllamaConfig) -> None:
        if not config.model:
            raise OllamaModelError(
                "Modelo não definido. Configure a variável OLLAMA_MODEL."
            )

        self.model = config.model
        self.client = Client(host=config.host)

    def check_connection(self) -> list[str]:
        """Verifica a conexão e retorna os modelos disponíveis localmente."""
        try:
            response = self.client.list()
            models = response.models
            return [model.model for model in models]
        except Exception as exc:
            raise OllamaModelError(
                "Não foi possível conectar ao Ollama. "
                "Verifique se ele está instalado e em execução."
            ) from exc

    def generate(self, prompt: str, system: str | None = None) -> str:
        """Envia uma instrução ao modelo selecionado e retorna o texto gerado."""
        try:
            response = self.client.generate(
                model=self.model,
                prompt=prompt,
                system=system or (
                    "Você é um componente de um agente especializado em "
                    "processar requisições estruturadas e consultar bancos "
                    "de dados relacionais. Responda somente ao que for solicitado."
                ),
                options={"temperature": 0},
            )
            return response.response.strip()
        except Exception as exc:
            raise OllamaModelError(
                f"Falha ao executar o modelo local '{self.model}'. "
                "Confirme se o modelo foi baixado no Ollama."
            ) from exc

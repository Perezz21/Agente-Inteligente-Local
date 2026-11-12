"""Integração com modelos executados localmente pelo Ollama."""

from dataclasses import dataclass

from ollama import Client

from src.agente.config import OllamaConfig


class OllamaModelError(RuntimeError):
    """Erro de configuração ou comunicação com o modelo local."""


@dataclass(frozen=True)
class GenerationResult:
    """Resposta do modelo acompanhada das métricas retornadas pelo Ollama."""

    content: str
    load_seconds: float | None
    prompt_eval_seconds: float | None
    generation_seconds: float | None
    prompt_tokens: int | None
    generated_tokens: int | None


class OllamaModelClient:
    """Cliente para executar modelos locais sem acoplar o agente ao modelo."""

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
            return [model.model for model in response.models]
        except Exception as exc:
            raise OllamaModelError(
                "Não foi possível conectar ao Ollama. "
                "Verifique se ele está instalado e em execução."
            ) from exc

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 180,
    ) -> GenerationResult:
        """Gera uma resposta e registra as métricas de execução do Ollama."""
        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": system or (
                            "Você é um componente de um agente especializado em "
                            "interpretar requisições estruturadas para consultas "
                            "a bancos de dados relacionais. Seja direto e objetivo. "
                            "Não exponha raciocínio interno."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                think=False,
                options={
                    "temperature": 0,
                    "num_predict": max_tokens,
                },
                keep_alive="10m",
            )

            def to_seconds(value: int | None) -> float | None:
                return value / 1_000_000_000 if value is not None else None

            return GenerationResult(
                content=(response.message.content or "").strip(),
                load_seconds=to_seconds(response.load_duration),
                prompt_eval_seconds=to_seconds(response.prompt_eval_duration),
                generation_seconds=to_seconds(response.eval_duration),
                prompt_tokens=response.prompt_eval_count,
                generated_tokens=response.eval_count,
            )
        except Exception as exc:
            raise OllamaModelError(
                f"Falha ao executar o modelo local '{self.model}'. "
                "Confirme se o modelo está instalado e se a versão do Ollama "
                "é compatível com a opção de desativar o modo de pensamento."
            ) from exc

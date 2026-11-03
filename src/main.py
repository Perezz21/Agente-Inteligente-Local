"""Ponto de entrada do Agente Inteligente Local."""

import json
from time import perf_counter

from src.agente.config import OllamaConfig
from src.agente.entrada import receber_json
from src.agente.ollama_client import (
    OllamaModelClient,
    OllamaModelError,
)


def main() -> None:
    config = OllamaConfig.from_environment()

    try:
        model_client = OllamaModelClient(config)
        available_models = model_client.check_connection()

        print("Conexão com o Ollama estabelecida.")
        print(f"Modelo configurado: {config.model}")

        if config.model not in available_models:
            print("\nModelo não encontrado entre os modelos instalados.")
            return

        requisicao = receber_json()

        print("\nJSON recebido e validado:")
        print(json.dumps(requisicao, indent=4, ensure_ascii=False))

        prompt = f"""
Analise a seguinte requisição estruturada em JSON:

{json.dumps(requisicao, indent=2, ensure_ascii=False)}

Identifique objetivamente:
1. A entidade ou conjunto de dados solicitado.
2. Os campos que devem ser recuperados.
3. Os filtros informados e seus valores.
4. O objetivo da consulta em uma frase.

Não invente tabelas, colunas ou informações ausentes no JSON.
Ainda não gere SQL: o esquema do banco será fornecido em outra etapa.
Responda em português, de forma concisa e organizada.
"""

        print("\nInterpretando a requisição com o modelo local...")
        inicio = perf_counter()
        resposta = model_client.generate(prompt=prompt, max_tokens=180)
        duracao = perf_counter() - inicio

        print("\n" + "=" * 50)
        print("INTERPRETAÇÃO DO AGENTE")
        print("=" * 50)
        print(resposta)
        print(f"\nTempo de interpretação: {duracao:.2f} segundos.")

    except (OllamaModelError, ValueError) as exc:
        print(f"\nErro: {exc}")


if __name__ == "__main__":
    main()

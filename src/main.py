"""Ponto de entrada do Agente Inteligente Local (fluxo completo)."""

import json

from src.agente.config import OllamaConfig
from src.agente.database import DatabaseClient
from src.agente.entrada import receber_json
from src.agente.fluxo import executar_requisicao
from src.agente.ollama_client import OllamaModelClient, OllamaModelError


def main() -> None:
    banco = DatabaseClient()
    try:
        config = OllamaConfig.from_environment()
        modelo = OllamaModelClient(config)
        disponiveis = modelo.check_connection()
        if config.model not in disponiveis:
            raise OllamaModelError(
                f"Modelo não encontrado entre os modelos instalados: {config.model}"
            )

        print(f"Modelo local: {config.model}")
        banco.connect()
        print("Conexão com MySQL estabelecida.")
        estrutura = banco.get_database_structure()
        print(
            f"Estrutura carregada: {len(estrutura['tabelas'])} tabelas e "
            f"{len(estrutura['relacionamentos'])} relacionamentos."
        )

        requisicao = receber_json()
        print("\nInterpretando requisição e gerando consulta SQL...")
        resposta = executar_requisicao(
            requisicao=requisicao,
            estrutura=estrutura,
            modelo=modelo,
            banco=banco,
        )

        print("\n" + "=" * 50)
        print("INTERPRETAÇÃO DO AGENTE")
        print("=" * 50)
        print(json.dumps(resposta["interpretacao"], ensure_ascii=False, indent=4))

        print("\n" + "=" * 50)
        print("CONSULTA SQL GERADA")
        print("=" * 50)
        print(resposta["consulta_sql"])

        print("\nPARÂMETROS")
        print("=" * 50)
        print(json.dumps(resposta["parametros"], ensure_ascii=False, indent=4))

        print("\n" + "=" * 50)
        print("RESULTADOS DA CONSULTA")
        print("=" * 50)
        print(json.dumps(
            resposta["registros"], ensure_ascii=False, indent=4, default=str
        ))
        print(f"\nTotal de registros recuperados: {resposta['total_registros']}")

        print("\nMÉTRICAS DA EXECUÇÃO")
        print("=" * 50)
        metricas = resposta["metricas"]
        print(f"Tempo total da requisição: {metricas['tempo_total_segundos']:.2f} s")
        interpretacao = metricas["interpretacao"]
        for rotulo, chave in (
            ("Carregamento", "carregamento_segundos"),
            ("Processamento do prompt", "processamento_prompt_segundos"),
            ("Geração", "geracao_segundos"),
            ("Tokens de entrada", "tokens_entrada"),
            ("Tokens gerados", "tokens_gerados"),
        ):
            valor = interpretacao[chave]
            if valor is not None:
                print(f"{rotulo}: {valor}")

    except (OllamaModelError, ValueError, RuntimeError) as erro:
        print(f"\nErro: {erro}")
    finally:
        banco.close()


if __name__ == "__main__":
    main()

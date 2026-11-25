"""Ponto de entrada do Agente Inteligente Local (fluxo completo)."""

import argparse
import json
import os

from src.agente.config import OllamaConfig
from src.agente.database import DatabaseClient
from src.agente.entrada import receber_json, receber_arquivo_json
from src.agente.fluxo import _executar_requisicao_validada
from src.agente.ollama_client import OllamaModelClient, OllamaModelError
from src.agente.registro_metricas import registrar_execucao


def processar(requisicao, notificar):
    """Executa uma entrada já validada e registra as métricas da sessão."""
    banco = DatabaseClient()
    try:
        config = OllamaConfig.from_environment()
        notificar(f"Verificação do modelo Ollama · {config.model}")
        modelo = OllamaModelClient(config)
        disponiveis = modelo.check_connection()
        if config.model not in disponiveis:
            raise OllamaModelError(
                f"Modelo não encontrado entre os modelos instalados: {config.model}"
            )

        nome_banco = os.getenv("MYSQL_DATABASE", "agente_experimental")
        notificar(f"Conexão com o banco · {nome_banco}")
        banco.connect()
        notificar(f"Descoberta da estrutura · conectado a {nome_banco}")
        estrutura = banco.get_database_structure()
        notificar(f"Estrutura carregada · {len(estrutura['tabelas'])} tabelas e "
                  f"{len(estrutura['relacionamentos'])} relacionamentos")
        resposta = _executar_requisicao_validada(
            requisicao=requisicao,
            estrutura=estrutura,
            modelo=modelo,
            banco=banco, notificar=notificar,
        )

        try:
            destino = registrar_execucao(
                resposta,
                modelo=config.model,
                cenario=os.getenv("AGENTE_CENARIO_ID", "manual"),
            )
            aviso = f"Métricas registradas em: {destino}"
        except (OSError, ValueError, TypeError) as erro:
            aviso = f"Aviso: não foi possível registrar métricas: {erro}"

        return resposta, aviso
    finally:
        banco.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Agente inteligente local MySQL")
    parser.add_argument("--arquivo", help="Arquivo com uma requisição JSON")
    parser.add_argument("--cli", action="store_true", help="Usar a interface de terminal")
    args = parser.parse_args()
    if not args.cli and args.arquivo is None:
        try:
            from src.interface.janelas import abrir
        except ImportError as erro:
            if erro.name not in {"tkinter", "_tkinter"}:
                raise
            parser.exit(1, "Tkinter indisponível. Instale o suporte Tk do Python ou utilize --cli.\n")
        abrir(processar)
        return
    try:
        requisicao = (
            receber_arquivo_json(args.arquivo)
            if args.arquivo is not None else receber_json()
        )
        resposta, aviso = processar(requisicao, print)
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
        print(f"Tempo da interpretação: {metricas['tempo_interpretacao_segundos']:.2f} s")
        print(f"Tempo da geração/validação SQL: {metricas['tempo_geracao_sql_segundos']:.2f} s")
        print(f"Tempo da execução MySQL: {metricas['tempo_execucao_mysql_segundos']:.2f} s")
        if metricas["tentativas_sql"] is not None:
            print(f"Tentativas SQL: {metricas['tentativas_sql']}")
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

        print(aviso)
    except (OllamaModelError, ValueError, RuntimeError) as erro:
        print(f"\nErro: {erro}")


if __name__ == "__main__":
    main()

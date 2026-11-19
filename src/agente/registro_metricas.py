"""Registro local, mínimo e estruturado das execuções bem-sucedidas.

Não inclui requisição, SQL, parâmetros, credenciais ou registros do banco.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CAMINHO_PADRAO = Path(__file__).resolve().parents[2] / "experiments" / "results" / "execucoes.jsonl"


def construir_registro(
    resposta: dict[str, Any],
    modelo: str,
    cenario: str = "manual",
    repeticao: int | None = None,
    avaliacao: dict | None = None,
) -> dict[str, Any]:
    """Constrói um registro de métricas, sem dados da consulta."""
    if not isinstance(modelo, str) or not modelo.strip():
        raise ValueError("O identificador do modelo é obrigatório.")
    if not isinstance(cenario, str) or not cenario.strip():
        raise ValueError("O identificador do cenário é obrigatório.")

    if repeticao is not None and (not isinstance(repeticao, int) or repeticao < 1):
        raise ValueError("Repetição deve ser um inteiro positivo.")

    metricas = resposta["metricas"]
    interpretacao = metricas["interpretacao"]
    return {
        "data_hora_utc": datetime.now(timezone.utc).isoformat(),
        "modelo": modelo,
        "cenario": cenario,
        "repeticao": repeticao,
        "avaliacao": avaliacao,
        "status": "sucesso",
        "total_registros": resposta["total_registros"],
        "tentativas_sql": metricas.get("tentativas_sql"),
        "tempo_total_segundos": metricas["tempo_total_segundos"],
        "tempo_interpretacao_segundos": metricas["tempo_interpretacao_segundos"],
        "tempo_geracao_sql_segundos": metricas["tempo_geracao_sql_segundos"],
        "tempo_execucao_mysql_segundos": metricas["tempo_execucao_mysql_segundos"],
        "ollama_interpretacao": {
            "carregamento_segundos": interpretacao["carregamento_segundos"],
            "processamento_prompt_segundos": interpretacao["processamento_prompt_segundos"],
            "geracao_segundos": interpretacao["geracao_segundos"],
            "tokens_entrada": interpretacao["tokens_entrada"],
            "tokens_gerados": interpretacao["tokens_gerados"],
        },
    }


def registrar_execucao(
    resposta: dict[str, Any],
    modelo: str,
    cenario: str = "manual",
    caminho: Path | None = None,
    repeticao: int | None = None,
    avaliacao: dict | None = None,
) -> Path:
    """Acrescenta uma linha JSON à saída local, preservando execuções anteriores."""
    destino = Path(caminho) if caminho is not None else CAMINHO_PADRAO
    registro = construir_registro(
        resposta, modelo, cenario, repeticao=repeticao, avaliacao=avaliacao
    )
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("a", encoding="utf-8") as arquivo:
        arquivo.write(json.dumps(registro, ensure_ascii=False, allow_nan=False) + "\n")
    return destino

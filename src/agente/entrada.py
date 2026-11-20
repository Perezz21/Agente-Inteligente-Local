"""Recebimento e validação inicial das requisições JSON."""

import json
from pathlib import Path
from typing import Any

from src.agente.contrato_requisicao import normalizar_requisicao


def receber_json() -> dict[str, Any]:
    """Recebe um JSON digitado ou colado no terminal."""

    print("\n" + "=" * 50)
    print("       AGENTE INTELIGENTE LOCAL")
    print("=" * 50)
    print("\nCole a requisição JSON abaixo.")
    print("Quando terminar, pressione Enter em uma linha vazia.\n")

    linhas: list[str] = []

    while True:
        try:
            linha = input()
        except EOFError:
            break

        if not linha.strip():
            if linhas:
                break
            continue

        linhas.append(linha)

    if not linhas:
        raise ValueError("Nenhum JSON foi informado.")

    conteudo = "\n".join(linhas)

    try:
        requisicao = json.loads(conteudo)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"JSON inválido na linha {exc.lineno}, "
            f"coluna {exc.colno}: {exc.msg}"
        ) from exc

    if not isinstance(requisicao, dict):
        raise ValueError("A requisição deve ser um objeto JSON.")

    return normalizar_requisicao(requisicao)


def receber_arquivo_json(caminho: str | Path) -> dict[str, Any]:
    """Carrega uma requisição JSON de arquivo UTF-8."""
    try:
        conteudo = Path(caminho).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValueError("Não foi possível ler o arquivo JSON informado.") from exc
    try:
        requisicao = json.loads(conteudo)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"JSON inválido na linha {exc.lineno}, coluna {exc.colno}."
        ) from exc
    if not isinstance(requisicao, dict):
        raise ValueError("A requisição deve ser um objeto JSON.")
    return normalizar_requisicao(requisicao)

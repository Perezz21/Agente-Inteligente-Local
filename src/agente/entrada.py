"""Recebimento e validação inicial das requisições JSON."""

import json
from typing import Any


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

    return requisicao

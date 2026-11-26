"""Validação estrutural da entrada; nenhuma tabela de banco é codificada aqui.

A fonte do contrato é schemas/requisicao.schema.json.
"""

import json
import math
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


_CAMINHO_SCHEMA = (
    Path(__file__).resolve().parents[2] / "schemas" / "requisicao.schema.json"
)


def _carregar_esquema() -> dict[str, Any]:
    """Carrega o contrato, separado da lógica do agente."""
    esquema = json.loads(_CAMINHO_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(esquema)
    return esquema


ESQUEMA_REQUISICAO = _carregar_esquema()
_VALIDADOR = Draft202012Validator(ESQUEMA_REQUISICAO)


def validar_requisicao(requisicao: dict[str, Any]) -> dict[str, Any]:
    """Verifica o contrato público e preserva o pedido completo."""
    if not isinstance(requisicao, dict):
        raise ValueError("A requisição deve ser um objeto JSON.")

    erros = sorted(
        _VALIDADOR.iter_errors(requisicao),
        key=lambda e: (len(e.absolute_path), list(map(str, e.absolute_path))),
    )
    if erros:
        erro = erros[0]
        local = ".".join(str(parte) for parte in erro.absolute_path) or "raiz"
        raise ValueError(
            f"JSON fora do padrão no campo '{local}': {erro.message}"
        )

    # json.loads() de Python permite NaN/Infinity por padrão; não permitir
    # números não finitos nem por chamadas diretas desta função.
    for chave, valor in requisicao["filtros"].items():
        if isinstance(valor, float) and not math.isfinite(valor):
            raise ValueError(
                f"JSON fora do padrão: filtro {chave!r} contém número não finito."
            )

    return requisicao


def normalizar_requisicao(requisicao: dict[str, Any]) -> dict[str, Any]:
    """Prepara um pedido válido para a etapa de interpretação."""
    return compactar_requisicao_validada(validar_requisicao(requisicao))


def compactar_requisicao_validada(requisicao: dict[str, Any]) -> dict[str, Any]:
    """Extrai do pedido validado os dados usados na interpretação."""
    normalizada = {
        "entidade": requisicao["entidade"],
        "campos": list(requisicao["campos"]),
    }
    if requisicao["filtros"]:
        normalizada["filtros"] = dict(requisicao["filtros"])
    if requisicao["agrupamento"]:
        normalizada["agrupamento"] = list(requisicao["agrupamento"])
    if requisicao["agregacoes"]:
        normalizada["agregacoes"] = [
            dict(item) for item in requisicao["agregacoes"]
        ]
    return normalizada

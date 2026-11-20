"""Contrato versionado das requisições externas (independente do banco).

A versão 1.0 tem seis propriedades obrigatórias. Requisições antigas sem
"versao" continuam aceitas, sem modificação, para preservar os experimentos.
"""

import math
import re
from typing import Any


VERSAO_REQUISICAO_ATUAL = "1.0"

_REFERENCIA = re.compile(
    r"^[A-Za-z_][A-Za-z_0-9]*\.[A-Za-z_][A-Za-z_0-9]*$"
)
_FUNCOES = {"AVG", "SUM", "MIN", "MAX", "COUNT"}

ESQUEMA_REQUISICAO_V1 = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Requisição do Agente Inteligente Local v1.0",
    "type": "object",
    "properties": {
        "versao": {"const": VERSAO_REQUISICAO_ATUAL},
        "entidade": {"type": "string", "minLength": 1},
        "campos": {
            "type": "array", "minItems": 1,
            "items": {"type": "string", "minLength": 1},
        },
        "filtros": {
            "type": "object",
            "additionalProperties": {
                "type": ["string", "number", "boolean"]
            },
        },
        "agrupamento": {
            "type": "array",
            "items": {"type": "string", "pattern": _REFERENCIA.pattern},
        },
        "agregacoes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "funcao": {"type": "string", "enum": sorted(_FUNCOES)},
                    "campo": {"type": "string", "pattern": _REFERENCIA.pattern},
                },
                "required": ["funcao", "campo"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "versao", "entidade", "campos", "filtros",
        "agrupamento", "agregacoes",
    ],
    "additionalProperties": False,
}


def normalizar_requisicao(requisicao: dict[str, Any]) -> dict[str, Any]:
    """Valida o formato externo v1 e o converte para o formato interno.

    Entradas legadas sem "versao" mantêm o comportamento anterior.
    A função NÃO tenta adivinhar colunas do banco: isso cabe ao agente.
    """
    if not isinstance(requisicao, dict):
        raise ValueError("A requisição deve ser um objeto JSON.")

    if "versao" not in requisicao:
        return requisicao

    versao = requisicao["versao"]
    if versao != VERSAO_REQUISICAO_ATUAL:
        raise ValueError(
            f"Versão de requisição não suportada: {versao!r}. "
            f"Utilize {VERSAO_REQUISICAO_ATUAL}."
        )

    permitidos = set(ESQUEMA_REQUISICAO_V1["properties"])
    obrigatorios = set(ESQUEMA_REQUISICAO_V1["required"])
    ausentes = obrigatorios - requisicao.keys()
    desconhecidos = requisicao.keys() - permitidos
    if ausentes:
        raise ValueError(f"Campos obrigatórios ausentes no JSON v1: {sorted(ausentes)}.")
    if desconhecidos:
        raise ValueError(f"Propriedades desconhecidas no JSON v1: {sorted(desconhecidos)}.")

    entidade = requisicao["entidade"]
    campos = requisicao["campos"]
    filtros = requisicao["filtros"]
    agrupamento = requisicao["agrupamento"]
    agregacoes = requisicao["agregacoes"]

    if not isinstance(entidade, str) or not entidade.strip():
        raise ValueError("'entidade' deve ser um texto não vazio.")
    if (
        not isinstance(campos, list) or not campos
        or any(not isinstance(c, str) or not c.strip() for c in campos)
    ):
        raise ValueError("'campos' deve ser uma lista não vazia de textos.")

    if not isinstance(filtros, dict):
        raise ValueError("'filtros' deve ser um objeto JSON.")
    for chave, valor in filtros.items():
        if not isinstance(chave, str) or not chave.strip():
            raise ValueError("As chaves de 'filtros' devem ser textos não vazios.")
        if (
            valor is None or not isinstance(valor, (str, int, float, bool))
            or (isinstance(valor, float) and not math.isfinite(valor))
        ):
            raise ValueError(
                f"O filtro {chave!r} deve conter texto, número ou booleano."
            )

    if not isinstance(agrupamento, list) or any(
        not isinstance(c, str) or not _REFERENCIA.fullmatch(c)
        for c in agrupamento
    ):
        raise ValueError(
            "'agrupamento' deve conter referências no formato tabela.coluna."
        )

    if not isinstance(agregacoes, list):
        raise ValueError("'agregacoes' deve ser uma lista.")
    for item in agregacoes:
        if not isinstance(item, dict) or set(item) != {"funcao", "campo"}:
            raise ValueError(
                "Cada agregação deve conter exatamente 'funcao' e 'campo'."
            )
        if (
            not isinstance(item["funcao"], str)
            or item["funcao"] not in _FUNCOES
        ):
            raise ValueError(
                f"Função de agregação inválida: {item['funcao']!r}."
            )
        if (
            not isinstance(item["campo"], str)
            or not _REFERENCIA.fullmatch(item["campo"])
        ):
            raise ValueError(
                "O campo de agregação deve seguir o formato tabela.coluna."
            )

    # Mantém a estrutura interna já utilizada pelo agente. Campos opcionais
    # vazios não são encaminhados para não alterar o comportamento existente.
    normalizada = {"entidade": entidade, "campos": list(campos)}
    if filtros:
        normalizada["filtros"] = dict(filtros)
    if agrupamento:
        normalizada["agrupamento"] = list(agrupamento)
    if agregacoes:
        normalizada["agregacoes"] = [dict(item) for item in agregacoes]
    return normalizada

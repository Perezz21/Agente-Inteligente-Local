"""Complementa a interpretação com metadados explícitos da requisição.

O modelo interpreta campos e filtros. Se a entrada já trouxer agrupamento
e agregações estruturados, esses dados são verificados antes de serem
passados ao gerador SQL, sem depender de o modelo repeti-los.
"""

import re
from typing import Any


_FUNCOES = {"AVG", "SUM", "MIN", "MAX", "COUNT"}
_REFERENCIA = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*\.[A-Za-z_][A-Za-z_0-9]*$")


def completar_interpretacao(
    requisicao: dict[str, Any],
    interpretacao: dict[str, Any],
    estrutura: dict[str, Any],
) -> dict[str, Any]:
    """Preserva metadados estruturados, verificando esquema e projeções."""

    if interpretacao.get("status") != "sucesso":
        raise ValueError(
            "A interpretação não foi concluída com status sucesso."
        )

    tabelas = estrutura.get("tabelas", {})
    colunas = {
        f"{tabela}.{coluna['nome']}".casefold()
        for tabela, dados in tabelas.items()
        for coluna in dados.get("colunas", [])
    }

    def validar_campo(campo: Any) -> str:
        if (
            not isinstance(campo, str)
            or not _REFERENCIA.fullmatch(campo)
            or campo.casefold() not in colunas
        ):
            raise ValueError(
                f"Campo de agrupamento/agregação inválido: {campo!r}"
            )
        return campo

    campos_solicitados = interpretacao.get("campos_solicitados")
    if not isinstance(campos_solicitados, list) or not all(
        isinstance(c, str) for c in campos_solicitados
    ):
        raise ValueError("Campos solicitados inválidos na interpretação.")

    projecoes = {c.replace(" ", "").casefold() for c in campos_solicitados}
    resultado = dict(interpretacao)

    if "agrupamento" in requisicao:
        grupos = requisicao["agrupamento"]
        if not isinstance(grupos, list):
            raise ValueError("O agrupamento deve ser uma lista.")

        campos_grupo = [validar_campo(c) for c in grupos]
        if len({c.casefold() for c in campos_grupo}) != len(campos_grupo):
            raise ValueError("O agrupamento contém campos repetidos.")
        if any(c.casefold() not in projecoes for c in campos_grupo):
            raise ValueError(
                "Agrupamento não corresponde aos campos solicitados."
            )
        resultado["agrupamento"] = campos_grupo

    if "agregacoes" in requisicao:
        agregacoes = requisicao["agregacoes"]
        if not isinstance(agregacoes, list):
            raise ValueError("Agregações devem formar uma lista.")

        verificadas = []
        for item in agregacoes:
            if not isinstance(item, dict):
                raise ValueError("Agregação com estrutura inválida.")

            funcao = item.get("funcao")
            campo = validar_campo(item.get("campo"))
            if not isinstance(funcao, str) or funcao.upper() not in _FUNCOES:
                raise ValueError("Função de agregação não suportada.")
            funcao = funcao.upper()
            assinatura = f"{funcao}({campo})".casefold()
            if assinatura not in projecoes:
                raise ValueError(
                    "Agregação não corresponde aos campos solicitados."
                )
            verificadas.append({"funcao": funcao, "campo": campo})

        resultado["agregacoes"] = verificadas

    return resultado

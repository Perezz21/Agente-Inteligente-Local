"""Comparação determinística entre registros SQL e referência do cenário.

A ordem das linhas não altera a correção quando o cenário não exige ordenação.
Os nomes das colunas e a multiplicidade de linhas precisam coincidir.
"""
from collections import Counter
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import sqlglot
from sqlglot import exp


def _normalizar_valor(valor: Any) -> tuple:
    """Normaliza números sem perder precisão e preserva tipos distintos."""
    if valor is None:
        return ("nulo", None)
    if isinstance(valor, bool):
        return ("booleano", valor)
    if isinstance(valor, (int, float, Decimal)):
        return ("numero", str(Decimal(str(valor)).normalize()))
    if isinstance(valor, (date, datetime)):
        return ("texto", valor.isoformat())
    if isinstance(valor, str):
        # Conectores SQL frequentemente retornam DECIMAL como Decimal;
        # o JSON esperado só permite representar esse valor como texto/número.
        try:
            numero = Decimal(valor)
        except InvalidOperation:
            numero = None
        if numero is not None and numero.is_finite():
            return ("numero", str(numero.normalize()))
        return ("texto", valor)
    raise ValueError("Tipo de valor não suportado na comparação.")


def _assinatura_linha(linha: dict) -> tuple:
    if not isinstance(linha, dict):
        raise ValueError("Cada registro esperado deve ser um objeto JSON.")
    return tuple(sorted(
        (chave, _normalizar_valor(valor))
        for chave, valor in linha.items()
    ))



def _normalizar_aliases(
    registros: list[dict], consulta_sql: str, colunas_referencia: dict[str, str]
) -> list[dict] | None:
    """Renomeia colunas retornadas usando a origem real no SELECT.

    Uma expressão diferente da referência jamais é considerada equivalente.
    Retorna None quando a correspondência não pode ser demonstrada.
    """
    if not isinstance(consulta_sql, str) or not isinstance(colunas_referencia, dict):
        raise ValueError("Configuração de correspondência de colunas inválida.")
    if not colunas_referencia or not all(
        isinstance(k, str) and isinstance(v, str) and k and v
        for k, v in colunas_referencia.items()
    ):
        raise ValueError("Correspondência de colunas deve ser um objeto não vazio.")

    referencia = {k.casefold(): v for k, v in colunas_referencia.items()}
    if len(referencia) != len(colunas_referencia) or (
        len(set(referencia.values())) != len(referencia)
    ):
        raise ValueError("Referência contém colunas repetidas.")

    try:
        arvore = sqlglot.parse_one(consulta_sql.replace("%s", "NULL"), read="mysql")
    except Exception:
        return None
    if not isinstance(arvore, exp.Select):
        return None

    nomes_sql_para_referencia = {}
    encontrados = set()
    for projecao in arvore.expressions:
        expressao = projecao.this if isinstance(projecao, exp.Alias) else projecao
        if not isinstance(expressao, exp.Column) or not expressao.table:
            return None
        origem = f"{expressao.table}.{expressao.name}".casefold()
        coluna_referencia = referencia.get(origem)
        nome_saida = projecao.alias_or_name
        if (
            coluna_referencia is None or not nome_saida
            or nome_saida in nomes_sql_para_referencia
            or origem in encontrados
        ):
            return None
        nomes_sql_para_referencia[nome_saida] = coluna_referencia
        encontrados.add(origem)

    if encontrados != set(referencia):
        return None

    normalizados = []
    for linha in registros:
        if not isinstance(linha, dict) or set(linha) != set(nomes_sql_para_referencia):
            return None
        normalizados.append({
            nomes_sql_para_referencia[chave]: valor
            for chave, valor in linha.items()
        })
    return normalizados


def avaliar_resultados(
    registros: list[dict],
    esperados: list[dict],
    *,
    ordem_importa: bool = False,
    consulta_sql: str | None = None,
    colunas_referencia: dict[str, str] | None = None,
) -> dict:
    """Retorna avaliação sem incluir valores reais ou esperados no log."""
    if not isinstance(registros, list) or not isinstance(esperados, list):
        raise ValueError("Resultados reais e esperados devem ser listas.")
    if not isinstance(ordem_importa, bool):
        raise ValueError("ordem_importa deve ser booleano.")

    if colunas_referencia is not None:
        normalizados = _normalizar_aliases(
            registros, consulta_sql, colunas_referencia
        )
        if normalizados is None:
            return {
                "correto": False,
                "total_registros_esperados": len(esperados),
                "ordem_importa": ordem_importa,
            }
        registros = normalizados

    reais = [_assinatura_linha(item) for item in registros]
    referencia = [_assinatura_linha(item) for item in esperados]
    correto = (
        reais == referencia if ordem_importa
        else Counter(reais) == Counter(referencia)
    )
    return {
        "correto": correto,
        "total_registros_esperados": len(esperados),
        "ordem_importa": ordem_importa,
    }

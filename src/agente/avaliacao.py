"""Comparação determinística entre registros SQL e referência do cenário.

A ordem das linhas não altera a correção quando o cenário não exige ordenação.
Os nomes das colunas e a multiplicidade de linhas precisam coincidir.
"""
from collections import Counter
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


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


def avaliar_resultados(
    registros: list[dict],
    esperados: list[dict],
    *,
    ordem_importa: bool = False,
) -> dict:
    """Retorna avaliação sem incluir valores reais ou esperados no log."""
    if not isinstance(registros, list) or not isinstance(esperados, list):
        raise ValueError("Resultados reais e esperados devem ser listas.")
    if not isinstance(ordem_importa, bool):
        raise ValueError("ordem_importa deve ser booleano.")

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

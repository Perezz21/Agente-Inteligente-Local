"""Identifica a origem de uma projeção no subconjunto SQL do agente."""
from sqlglot import exp


def nome_de_saida(projecao: exp.Expression) -> str:
    return projecao.output_name or projecao.sql(dialect="mysql")


def coluna_e_funcao(expressao: exp.Expression):
    if isinstance(expressao, exp.Alias):
        expressao = expressao.this
    funcao = None
    if isinstance(expressao, exp.AggFunc):
        funcao = expressao.key.upper()
        if funcao not in {"AVG", "SUM", "MIN", "MAX", "COUNT"} or expressao.expressions:
            return None
        expressao = expressao.this
    if not isinstance(expressao, exp.Column) or not expressao.table or expressao.is_star:
        return None
    return expressao, funcao

"""Testes da equivalência segura de aliases SQL na avaliação."""

import unittest

from src.agente.avaliacao import avaliar_resultados


class TesteAliasesSemanticos(unittest.TestCase):
    def test_01_aceita_alias_diferente_para_mesma_coluna(self):
        resultado = avaliar_resultados(
            [{"nome_rio": "Rio Claro", "bacia_hidrografica": "Paranaíba"}],
            [{"nome": "Rio Claro", "bacia_hidrografica": "Paranaíba"}],
            consulta_sql=(
                "SELECT rios.nome AS nome_rio, "
                "rios.bacia_hidrografica AS bacia_hidrografica "
                "FROM rios WHERE rios.nome = %s"
            ),
            colunas_referencia={
                "rios.nome": "nome",
                "rios.bacia_hidrografica": "bacia_hidrografica",
            },
        )
        self.assertTrue(resultado["correto"])

    def test_02_aceita_aliases_do_cenario_04(self):
        resultado = avaliar_resultados(
            [{
                "nome_indicador": "Índice de qualidade da água",
                "valor_indicador": "82.500",
                "unidade_indicador": "pontos",
                "nome_municipio": "Jataí",
            }],
            [{
                "nome": "Índice de qualidade da água",
                "valor": "82.500",
                "unidade": "pontos",
                "municipio": "Jataí",
            }],
            consulta_sql=(
                "SELECT indicadores.nome AS nome_indicador, "
                "indicadores.valor AS valor_indicador, "
                "indicadores.unidade AS unidade_indicador, "
                "municipios.nome AS nome_municipio "
                "FROM indicadores JOIN municipios "
                "ON indicadores.municipio_id = municipios.id "
                "WHERE municipios.nome = %s"
            ),
            colunas_referencia={
                "indicadores.nome": "nome",
                "indicadores.valor": "valor",
                "indicadores.unidade": "unidade",
                "municipios.nome": "municipio",
            },
        )
        self.assertTrue(resultado["correto"])

    def test_03_rejeita_coluna_diferente_mesmo_com_alias_esperado(self):
        resultado = avaliar_resultados(
            [{"nome": "Rio Claro"}], [{"nome": "Rio Claro"}],
            consulta_sql="SELECT municipios.nome AS nome FROM municipios",
            colunas_referencia={"rios.nome": "nome"},
        )
        self.assertFalse(resultado["correto"])

    def test_04_rejeita_valor_diferente(self):
        resultado = avaliar_resultados(
            [{"nome_rio": "Outro rio"}], [{"nome": "Rio Claro"}],
            consulta_sql="SELECT rios.nome AS nome_rio FROM rios",
            colunas_referencia={"rios.nome": "nome"},
        )
        self.assertFalse(resultado["correto"])

    def test_05_rejeita_coluna_extra(self):
        resultado = avaliar_resultados(
            [{"nome_rio": "Rio Claro", "id": 1}],
            [{"nome": "Rio Claro"}],
            consulta_sql="SELECT rios.nome AS nome_rio, rios.id FROM rios",
            colunas_referencia={"rios.nome": "nome"},
        )
        self.assertFalse(resultado["correto"])

    def test_06_rejeita_expressao_nao_correspondente(self):
        resultado = avaliar_resultados(
            [{"nome_rio": "Rio Claro"}], [{"nome": "Rio Claro"}],
            consulta_sql="SELECT UPPER(rios.nome) AS nome_rio FROM rios",
            colunas_referencia={"rios.nome": "nome"},
        )
        self.assertFalse(resultado["correto"])


if __name__ == "__main__":
    unittest.main()

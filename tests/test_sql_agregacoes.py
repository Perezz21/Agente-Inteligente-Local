"""Testes de agregações e GROUP BY sem Ollama nem MySQL."""

import copy
import unittest

from src.agente.sql_generator import SQLGenerationError, SQLGenerator


ESTRUTURA = {
    "tabelas": {
        "medicoes": {"colunas": [
            {"nome": "rio_id"}, {"nome": "municipio_id"},
            {"nome": "data_medicao"}, {"nome": "vazao_m3_s"}, {"nome": "nivel_m"},
        ]},
        "rios": {"colunas": [{"nome": "id"}, {"nome": "nome"}]},
        "municipios": {"colunas": [{"nome": "id"}, {"nome": "nome"}]},
    },
    "relacionamentos": [
        {"origem": "medicoes.rio_id", "destino": "rios.id"},
        {"origem": "medicoes.municipio_id", "destino": "municipios.id"},
    ],
}

INTERPRETACAO = {
    "campos_solicitados": [
        "rios.nome", "municipios.nome", "AVG(medicoes.vazao_m3_s)",
    ],
    "filtros": [
        {"campo": "municipios.nome", "operador": "=", "valor": "Jataí"},
        {"campo": "rios.nome", "operador": "=", "valor": "Rio Claro"},
        {"campo": "medicoes.data_medicao", "operador": "ANO_IGUAL", "valor": 2025},
    ],
    "relacionamentos_necessarios": [
        {"origem": "medicoes.rio_id", "destino": "rios.id"},
        {"origem": "medicoes.municipio_id", "destino": "municipios.id"},
    ],
    "agrupamento": ["rios.nome", "municipios.nome"],
    "agregacoes": [{"funcao": "AVG", "campo": "medicoes.vazao_m3_s"}],
}

FROM_WHERE = (
    " FROM medicoes "
    "JOIN rios ON medicoes.rio_id = rios.id "
    "JOIN municipios ON medicoes.municipio_id = municipios.id "
    "WHERE municipios.nome = %s AND rios.nome = %s "
    "AND YEAR(medicoes.data_medicao) = %s"
)
PARAMETROS = ["Jataí", "Rio Claro", 2025]
CAMPOS = (
    "SELECT rios.nome AS rio, municipios.nome AS municipio, "
    "AVG(medicoes.vazao_m3_s)"
)
GROUP = " GROUP BY rios.nome, municipios.nome"


class TesteAgregacoes(unittest.TestCase):
    def validar(self, sql, interpretacao=None):
        SQLGenerator._validate_query(
            sql, PARAMETROS, ESTRUTURA,
            interpretacao if interpretacao is not None else INTERPRETACAO,
        )

    def rejeita(self, sql, mensagem, interpretacao=None):
        with self.assertRaisesRegex(SQLGenerationError, mensagem):
            self.validar(sql, interpretacao)

    def test_01_aceita_media_agrupada(self):
        self.validar(CAMPOS + FROM_WHERE + GROUP)

    def test_02_rejeita_sum_no_lugar_de_avg(self):
        sql = CAMPOS.replace("AVG(", "SUM(") + FROM_WHERE + GROUP
        self.rejeita(sql, "Campos solicitados ausentes")

    def test_03_rejeita_coluna_agregada_errada(self):
        sql = CAMPOS.replace("vazao_m3_s", "nivel_m") + FROM_WHERE + GROUP
        self.rejeita(sql, "Campos solicitados ausentes")

    def test_04_rejeita_group_by_ausente(self):
        self.rejeita(
            CAMPOS + FROM_WHERE,
            "não contém GROUP BY",
        )

    def test_05_rejeita_group_by_extra(self):
        self.rejeita(
            CAMPOS + FROM_WHERE + GROUP + ", medicoes.rio_id",
            "GROUP BY diferente",
        )

    def test_06_rejeita_group_by_duplicado(self):
        self.rejeita(
            CAMPOS + FROM_WHERE + GROUP + ", rios.nome",
            "colunas repetidas",
        )

    def test_07_rejeita_agrupamento_diferente_do_solicitado(self):
        interpretacao = copy.deepcopy(INTERPRETACAO)
        interpretacao["agrupamento"] = ["rios.nome"]
        self.rejeita(
            CAMPOS + FROM_WHERE + GROUP,
            "GROUP BY diferente",
            interpretacao,
        )

    def test_08_aceita_agregacao_global_sem_group_by(self):
        interpretacao = copy.deepcopy(INTERPRETACAO)
        interpretacao["campos_solicitados"] = [
            "AVG(medicoes.vazao_m3_s)"
        ]
        interpretacao["agrupamento"] = []
        self.validar(
            "SELECT AVG(medicoes.vazao_m3_s)" + FROM_WHERE,
            interpretacao,
        )

    def test_09_rejeita_group_by_nao_solicitado_sem_agregacao(self):
        interpretacao = copy.deepcopy(INTERPRETACAO)
        interpretacao["campos_solicitados"] = [
            "rios.nome", "municipios.nome"
        ]
        interpretacao["agregacoes"] = []
        interpretacao["agrupamento"] = []
        self.rejeita(
            "SELECT rios.nome AS rio, municipios.nome AS municipio" + FROM_WHERE + GROUP,
            "GROUP BY diferente",
            interpretacao,
        )

    def test_10_rejeita_agregacao_inconsistente_na_interpretacao(self):
        interpretacao = copy.deepcopy(INTERPRETACAO)
        interpretacao["agregacoes"] = [
            {"funcao": "SUM", "campo": "medicoes.vazao_m3_s"}
        ]
        self.rejeita(
            CAMPOS + FROM_WHERE + GROUP,
            "agregações SQL não correspondem",
            interpretacao,
        )

    def test_11_rejeita_group_by_expressao(self):
        self.rejeita(
            CAMPOS + FROM_WHERE +
            " GROUP BY YEAR(medicoes.data_medicao), rios.nome, municipios.nome",
            "GROUP BY deve utilizar apenas colunas",
        )


if __name__ == "__main__":
    unittest.main()

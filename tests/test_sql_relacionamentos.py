"""Testes unitários da validação semântica dos relacionamentos JOIN.

Executar da raiz do projeto:
    python -m unittest discover -s tests -p "test_*.py" -v

Estes testes não acessam o MySQL nem o Ollama.
"""

import unittest

from src.agente.sql_generator import SQLGenerationError, SQLGenerator


ESTRUTURA = {
    "banco": "agente_experimental",
    "tabelas": {
        "medicoes": {
            "colunas": [
                {"nome": "id"},
                {"nome": "rio_id"},
                {"nome": "municipio_id"},
                {"nome": "data_medicao"},
                {"nome": "vazao_m3_s"},
            ]
        },
        "rios": {
            "colunas": [
                {"nome": "id"},
                {"nome": "nome"},
                {"nome": "municipio_referencia_id"},
            ]
        },
        "municipios": {
            "colunas": [
                {"nome": "id"},
                {"nome": "nome"},
            ]
        },
    },
    "relacionamentos": [
        {"origem": "medicoes.rio_id", "destino": "rios.id"},
        {"origem": "medicoes.municipio_id", "destino": "municipios.id"},
        {
            "origem": "rios.municipio_referencia_id",
            "destino": "municipios.id",
        },
    ],
}

INTERPRETACAO = {
    "tabelas_identificadas": ["medicoes", "rios", "municipios"],
    "campos_solicitados": [
        "rios.nome",
        "municipios.nome",
        "AVG(medicoes.vazao_m3_s)",
    ],
    "filtros": [
        {"campo": "municipios.nome", "operador": "=", "valor": "Jataí"},
        {"campo": "rios.nome", "operador": "=", "valor": "Rio Claro"},
        {
            "campo": "medicoes.data_medicao",
            "operador": "ANO_IGUAL",
            "valor": 2025,
        },
    ],
    "relacionamentos_necessarios": [
        {"origem": "medicoes.rio_id", "destino": "rios.id"},
        {"origem": "medicoes.municipio_id", "destino": "municipios.id"},
    ],
}

SELECT = (
    "SELECT rios.nome AS rio, municipios.nome AS municipio, "
    "AVG(medicoes.vazao_m3_s) AS vazao_media "
    "FROM medicoes "
)

WHERE = (
    " WHERE municipios.nome = %s "
    "AND rios.nome = %s "
    "AND YEAR(medicoes.data_medicao) = %s "
    "GROUP BY rios.nome, municipios.nome"
)

PARAMETROS = ["Jataí", "Rio Claro", 2025]

JOIN_RIO = "JOIN rios ON medicoes.rio_id = rios.id "
JOIN_MUNICIPIO = (
    "JOIN municipios ON medicoes.municipio_id = municipios.id"
)


class TesteRelacionamentosJoin(unittest.TestCase):
    def validar(self, consulta):
        SQLGenerator._validate_query(
            consulta,
            PARAMETROS,
            ESTRUTURA,
            INTERPRETACAO,
        )

    def rejeita(self, consulta, mensagem):
        with self.assertRaisesRegex(SQLGenerationError, mensagem):
            self.validar(consulta)

    def test_chave_composta_exige_os_dois_pares_no_mesmo_join(self):
        pares = [
            {"origem": "a.id", "destino": "b.id", "restricao": "fk_ab"},
            {"origem": "a.loja", "destino": "b.loja", "restricao": "fk_ab"},
        ]
        estrutura = {"tabelas": {t: {"colunas": [{"nome": "id"}, {"nome": "loja"}]}
                                 for t in ("a", "b")}, "relacionamentos": pares}
        pedido = {"campos_solicitados": ["a.id"], "relacionamentos_necessarios": pares}
        sql = "SELECT a.id FROM a JOIN b ON a.id = b.id"
        SQLGenerator._validate_query(sql + " AND a.loja = b.loja", [], estrutura, pedido)
        with self.assertRaisesRegex(SQLGenerationError, "composta incompleta"):
            SQLGenerator._validate_query(sql, [], estrutura, {
                **pedido, "relacionamentos_necessarios": pares[:1]})

    def test_01_aceita_relacionamentos_corretos(self):
        self.validar(SELECT + JOIN_RIO + JOIN_MUNICIPIO + WHERE)

    def test_02_rejeita_relacionamento_incorreto(self):
        sql = (
            SELECT
            + JOIN_RIO
            + "JOIN municipios ON rios.municipio_referencia_id = municipios.id"
            + WHERE
        )
        self.rejeita(sql, "Relacionamentos JOIN divergem|relacionamentos JOIN divergem")

    def test_03_rejeita_relacionamento_ausente(self):
        # Remove campos/filtros de municipios para isolar o JOIN ausente:
        # a consulta permanece válida até a checagem dos relacionamentos.
        interpretacao = {
            **INTERPRETACAO,
            "campos_solicitados": [
                "rios.nome",
                "AVG(medicoes.vazao_m3_s)",
            ],
            "filtros": [
                INTERPRETACAO["filtros"][1],
                INTERPRETACAO["filtros"][2],
            ],
        }
        sql = (
            "SELECT rios.nome, AVG(medicoes.vazao_m3_s) "
            "FROM medicoes JOIN rios ON medicoes.rio_id = rios.id "
            "WHERE rios.nome = %s AND YEAR(medicoes.data_medicao) = %s "
            "GROUP BY rios.nome"
        )
        with self.assertRaisesRegex(
            SQLGenerationError, "relacionamentos JOIN divergem"
        ):
            SQLGenerator._validate_query(
                sql, ["Rio Claro", 2025], ESTRUTURA, interpretacao
            )

    def test_04_rejeita_relacionamento_adicional(self):
        sql = (
            SELECT
            + JOIN_RIO
            + JOIN_MUNICIPIO
            + " AND rios.municipio_referencia_id = municipios.id"
            + WHERE
        )
        self.rejeita(sql, "Relacionamentos JOIN divergem|relacionamentos JOIN divergem")

    def test_05_rejeita_join_sem_on(self):
        sql = SELECT + JOIN_RIO + "CROSS JOIN municipios" + WHERE
        self.rejeita(sql, "JOIN sem condição ON")

    def test_06_aceita_igualdade_invertida(self):
        sql = (
            SELECT
            + "JOIN rios ON rios.id = medicoes.rio_id "
            + "JOIN municipios ON municipios.id = medicoes.municipio_id"
            + WHERE
        )
        self.validar(sql)

    def test_07_rejeita_relacionamento_inventado_na_interpretacao(self):
        interpretacao = {
            **INTERPRETACAO,
            "relacionamentos_necessarios": [
                {"origem": "medicoes.rio_id", "destino": "municipios.id"}
            ],
        }
        sql = SELECT + JOIN_RIO + JOIN_MUNICIPIO + WHERE
        with self.assertRaisesRegex(
            SQLGenerationError, "relacionamentos inexistentes"
        ):
            SQLGenerator._validate_query(
                sql, PARAMETROS, ESTRUTURA, interpretacao
            )


if __name__ == "__main__":
    unittest.main()

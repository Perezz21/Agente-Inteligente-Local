"""Testes de segurança do DatabaseClient, sem acesso real ao MySQL.

Executar na raiz:
    python -m unittest discover -s tests -p "test_*.py" -v
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from src.agente.database import DatabaseClient


class TesteConfiguracaoMySQL(unittest.TestCase):
    @patch.dict(os.environ, {"MYSQL_USER": "", "MYSQL_PASSWORD": ""})
    def test_rejeita_credenciais_ausentes(self):
        banco = DatabaseClient()
        with self.assertRaisesRegex(RuntimeError, "MYSQL_USER"):
            banco.connect()

    @patch.dict(os.environ, {
        "MYSQL_HOST": "localhost",
        "MYSQL_PORT": "3306",
        "MYSQL_USER": "agente_leitura",
        "MYSQL_PASSWORD": "senha_de_teste_nao_real",
        "MYSQL_DATABASE": "agente_experimental",
    })
    @patch("src.agente.database.mysql.connector.connect")
    def test_conexao_usa_variaveis_de_ambiente(self, conectar):
        banco = DatabaseClient()
        banco.connect()
        conectar.assert_called_once_with(
            host="localhost",
            port=3306,
            user="agente_leitura",
            password="senha_de_teste_nao_real",
            database="agente_experimental",
        )

    @patch.dict(os.environ, {
        "MYSQL_USER": "agente_leitura",
        "MYSQL_PASSWORD": "senha_de_teste_nao_real",
        "MYSQL_PORT": "invalida",
    })
    def test_rejeita_porta_invalida(self):
        with self.assertRaisesRegex(RuntimeError, "MYSQL_PORT"):
            DatabaseClient().connect()


class TesteExecucaoSomenteLeitura(unittest.TestCase):
    def setUp(self):
        self.banco = DatabaseClient()
        self.cursor = MagicMock()
        self.cursor.fetchall.return_value = [{"nome": "Rio Claro"}]
        self.conexao = MagicMock()
        self.conexao.is_connected.return_value = True
        self.conexao.cursor.return_value = self.cursor
        self.banco.connection = self.conexao

    def test_aceita_select_parametrizado(self):
        sql = "SELECT rios.nome FROM rios WHERE rios.nome = %s"
        resultado = self.banco.execute_select(sql, ["Rio Claro"])
        self.assertEqual(resultado, [{"nome": "Rio Claro"}])
        self.cursor.execute.assert_called_once_with(sql, ("Rio Claro",))
        self.cursor.close.assert_called_once()

    def test_rejeita_delete(self):
        with self.assertRaises(ValueError):
            self.banco.execute_select("DELETE FROM rios")
        self.conexao.cursor.assert_not_called()

    def test_rejeita_update(self):
        with self.assertRaises(ValueError):
            self.banco.execute_select(
                "UPDATE rios SET nome = %s", ["Outro"]
            )
        self.conexao.cursor.assert_not_called()

    def test_rejeita_duas_instrucoes(self):
        with self.assertRaises(ValueError):
            self.banco.execute_select(
                "SELECT rios.nome FROM rios; DELETE FROM rios"
            )
        self.conexao.cursor.assert_not_called()

    def test_rejeita_union(self):
        with self.assertRaises(ValueError):
            self.banco.execute_select(
                "SELECT rios.nome FROM rios "
                "UNION SELECT municipios.nome FROM municipios"
            )
        self.conexao.cursor.assert_not_called()

    def test_rejeita_subconsulta(self):
        with self.assertRaises(ValueError):
            self.banco.execute_select(
                "SELECT rios.nome FROM rios "
                "WHERE rios.id IN (SELECT medicoes.rio_id FROM medicoes)"
            )
        self.conexao.cursor.assert_not_called()

    def test_rejeita_comentarios(self):
        with self.assertRaises(ValueError):
            self.banco.execute_select("SELECT rios.nome FROM rios -- comentário")
        self.conexao.cursor.assert_not_called()


if __name__ == "__main__":
    unittest.main()

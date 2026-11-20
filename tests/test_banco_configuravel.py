"""Verifica descoberta de relacionamentos em bancos diferentes."""

import os
import unittest
from unittest.mock import Mock, patch

from src.agente.database import DatabaseClient


class TesteBancoConfiguravel(unittest.TestCase):
    @patch.dict(os.environ, {"MYSQL_DATABASE": "sakila"})
    def test_relacionamentos_usam_banco_configurado(self):
        cliente = DatabaseClient()
        cursor = Mock()
        cursor.fetchall.return_value = []
        cliente.connection = Mock()
        cliente.connection.is_connected.return_value = True
        cliente.connection.cursor.return_value = cursor

        self.assertEqual(cliente.get_relationships(), [])
        parametros = cursor.execute.call_args.args[1]
        self.assertEqual(parametros, ("sakila",))
        cursor.close.assert_called_once()

    @patch.dict(os.environ, {"MYSQL_DATABASE": "agente_experimental"})
    def test_relacionamentos_mantem_banco_original(self):
        cliente = DatabaseClient()
        cursor = Mock()
        cursor.fetchall.return_value = []
        cliente.connection = Mock()
        cliente.connection.is_connected.return_value = True
        cliente.connection.cursor.return_value = cursor

        cliente.get_relationships()
        self.assertEqual(
            cursor.execute.call_args.args[1],
            ("agente_experimental",),
        )


if __name__ == "__main__":
    unittest.main()

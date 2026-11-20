"""Testes do formato JSON exigido na geração SQL."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.agente.esquema_geracao_sql import ESQUEMA_GERACAO_SQL
from src.agente.sql_generator import SQLGenerator, SQLGenerationError


ESTRUTURA = {
    "banco": "qualquer",
    "tabelas": {"filme": {"colunas": [{"nome": "titulo", "tipo": "varchar(100)"}]}},
    "relacionamentos": [],
}
INTERPRETACAO = {
    "tabelas_identificadas": ["filme"],
    "campos_solicitados": ["filme.titulo"],
    "filtros": [],
    "relacionamentos_necessarios": [],
    "status": "sucesso",
    "observacoes": "",
}


def resposta(texto):
    return SimpleNamespace(content=texto)


class TesteFormatoGeracaoSQL(unittest.TestCase):
    @patch.object(SQLGenerator, "_validate_query")
    def test_01_envia_json_schema_e_aceita_resposta(self, validar):
        modelo = Mock()
        modelo.generate.return_value = resposta(json.dumps({
            "consulta_sql": "SELECT filme.titulo FROM filme",
            "parametros": [],
        }))
        gerador = SQLGenerator(modelo)
        resultado = gerador.generate(INTERPRETACAO, ESTRUTURA)
        self.assertEqual(resultado["tentativas_sql"], 1)
        self.assertEqual(
            modelo.generate.call_args.kwargs["json_schema"], ESQUEMA_GERACAO_SQL
        )
        self.assertEqual(modelo.generate.call_args.kwargs["max_tokens"], 700)
        validar.assert_called_once()

    @patch.object(SQLGenerator, "_validate_query")
    def test_02_recupera_texto_na_segunda_tentativa(self, validar):
        modelo = Mock()
        modelo.generate.side_effect = [
            resposta("explicação longa sem JSON"),
            resposta('{"consulta_sql":"SELECT filme.titulo FROM filme","parametros":[]}'),
        ]
        gerador = SQLGenerator(modelo)
        resultado = gerador.generate(INTERPRETACAO, ESTRUTURA)
        self.assertEqual(resultado["tentativas_sql"], 2)
        self.assertEqual(modelo.generate.call_count, 2)
        self.assertNotIn(
            "explicação longa sem JSON",
            modelo.generate.call_args.kwargs["prompt"],
        )

    def test_03_falha_com_respostas_invalidas(self):
        modelo = Mock()
        modelo.generate.return_value = resposta("texto sem JSON")
        with self.assertRaisesRegex(SQLGenerationError, "3 tentativas"):
            SQLGenerator(modelo).generate(INTERPRETACAO, ESTRUTURA)
        self.assertEqual(modelo.generate.call_count, 3)

    def test_04_esquema_exige_sql_e_parametros(self):
        self.assertEqual(
            set(ESQUEMA_GERACAO_SQL["required"]),
            {"consulta_sql", "parametros"},
        )
        self.assertFalse(ESQUEMA_GERACAO_SQL["additionalProperties"])


if __name__ == "__main__":
    unittest.main()

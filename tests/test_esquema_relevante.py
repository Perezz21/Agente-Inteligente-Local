"""Testes da seleção genérica do esquema para geração SQL."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from src.agente.sql_generator import SQLGenerator, _estrutura_relevante


ESTRUTURA = {
    "banco": "exemplo",
    "tabelas": {
        "filme": {"colunas": [{"nome": "titulo", "tipo": "varchar"}]},
        "categoria": {"colunas": [{"nome": "nome", "tipo": "varchar"}]},
        "filmecategoria": {"colunas": [
            {"nome": "filme_id", "tipo": "int"},
            {"nome": "categoria_id", "tipo": "int"},
        ]},
        "locadora": {"colunas": [{"nome": "nome", "tipo": "varchar"}]},
    },
    "relacionamentos": [
        {"origem": "filmecategoria.filme_id", "destino": "filme.id"},
        {"origem": "filmecategoria.categoria_id", "destino": "categoria.id"},
    ],
}


class TesteEsquemaRelevante(unittest.TestCase):
    def test_01_seleciona_apenas_tabela_relevante(self):
        interpretacao = {
            "tabelas_identificadas": ["filme"],
            "campos_solicitados": ["filme.titulo"],
            "filtros": [],
            "relacionamentos_necessarios": [],
        }
        reduzida = _estrutura_relevante(interpretacao, ESTRUTURA)
        self.assertEqual(list(reduzida["tabelas"]), ["filme"])
        self.assertEqual(reduzida["relacionamentos"], [])
        self.assertEqual(len(ESTRUTURA["tabelas"]), 4)

    def test_02_inclui_tabelas_dos_joins(self):
        interpretacao = {
            "tabelas_identificadas": ["filme"],
            "campos_solicitados": ["filme.titulo", "categoria.nome"],
            "relacionamentos_necessarios": [
                {"origem": "filmecategoria.filme_id", "destino": "filme.id"},
                {"origem": "filmecategoria.categoria_id", "destino": "categoria.id"},
            ],
        }
        reduzida = _estrutura_relevante(interpretacao, ESTRUTURA)
        self.assertEqual(set(reduzida["tabelas"]), {
            "filme", "categoria", "filmecategoria",
        })
        self.assertEqual(len(reduzida["relacionamentos"]), 2)

    def test_03_filtro_contribui_tabela_relevante(self):
        interpretacao = {
            "campos_solicitados": ["filme.titulo"],
            "filtros": [{"campo": "categoria.nome", "operador": "=", "valor": "Comédia"}],
        }
        reduzida = _estrutura_relevante(interpretacao, ESTRUTURA)
        self.assertEqual(set(reduzida["tabelas"]), {"filme", "categoria"})

    def test_04_gerador_recebe_reduzido_e_valida_com_esquema_completo(self):
        interpretacao = {
            "tabelas_identificadas": ["filme"],
            "campos_solicitados": ["filme.titulo"],
            "filtros": [],
            "relacionamentos_necessarios": [],
            "status": "sucesso",
            "observacoes": "",
        }
        modelo = Mock()
        modelo.generate.return_value = SimpleNamespace(
            content=json.dumps({
                "consulta_sql": "SELECT filme.titulo FROM filme",
                "parametros": [],
            })
        )
        gerador = SQLGenerator(modelo)
        resultado = gerador.generate(interpretacao, ESTRUTURA)
        self.assertEqual(resultado["tentativas_sql"], 1)
        prompt = modelo.generate.call_args.kwargs["prompt"]
        self.assertIn('"filme"', prompt)
        self.assertNotIn('"locadora"', prompt)


if __name__ == "__main__":
    unittest.main()

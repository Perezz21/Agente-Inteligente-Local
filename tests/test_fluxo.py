"""Testes do fluxo desacoplado de Ollama, MySQL e terminal."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.agente.fluxo import executar_requisicao


REQUISICAO = {"entidade": "medições", "campos": ["vazão"]}
ESTRUTURA = {"tabelas": {}, "relacionamentos": []}
INTERPRETACAO = {
    "tabelas_identificadas": ["medicoes"],
    "campos_solicitados": ["medicoes.vazao_m3_s"],
    "filtros": [],
    "relacionamentos_necessarios": [],
    "status": "sucesso",
    "observacoes": "",
}


def criar_modelo(conteudo):
    modelo = Mock()
    modelo.generate.return_value = SimpleNamespace(
        content=conteudo,
        load_seconds=0.1,
        prompt_eval_seconds=0.2,
        generation_seconds=0.3,
        prompt_tokens=20,
        generated_tokens=10,
    )
    return modelo


class TesteFluxoPrincipal(unittest.TestCase):
    @patch("src.agente.fluxo.SQLGenerator")
    @patch("src.agente.fluxo.completar_interpretacao")
    def test_01_executa_pipeline_completo(self, completar, classe_sql):
        modelo = criar_modelo(json.dumps(INTERPRETACAO))
        completar.return_value = INTERPRETACAO
        classe_sql.return_value.generate.return_value = {
            "consulta_sql": "SELECT medicoes.vazao_m3_s FROM medicoes",
            "parametros": [],
        }
        banco = Mock()
        banco.execute_select.return_value = [{"vazao_m3_s": "21.10"}]

        saida = executar_requisicao(
            REQUISICAO, ESTRUTURA, modelo, banco
        )

        self.assertEqual(saida["total_registros"], 1)
        self.assertEqual(saida["registros"][0]["vazao_m3_s"], "21.10")
        self.assertEqual(saida["metricas"]["interpretacao"]["tokens_entrada"], 20)
        self.assertGreaterEqual(saida["metricas"]["tempo_total_segundos"], 0)
        modelo.generate.assert_called_once()
        completar.assert_called_once_with(
            REQUISICAO, INTERPRETACAO, ESTRUTURA
        )
        banco.execute_select.assert_called_once_with(
            consulta="SELECT medicoes.vazao_m3_s FROM medicoes",
            parametros=[],
        )

    def test_02_rejeita_json_invalido(self):
        with self.assertRaisesRegex(ValueError, "JSON válido"):
            executar_requisicao(
                REQUISICAO, ESTRUTURA, criar_modelo("não é JSON"), Mock()
            )

    def test_03_rejeita_resposta_que_nao_e_objeto(self):
        with self.assertRaisesRegex(ValueError, "objeto JSON"):
            executar_requisicao(
                REQUISICAO, ESTRUTURA, criar_modelo("[]"), Mock()
            )

    def test_04_rejeita_campos_obrigatorios_ausentes(self):
        with self.assertRaisesRegex(ValueError, "obrigatórios ausentes"):
            executar_requisicao(
                REQUISICAO, ESTRUTURA, criar_modelo("{}"), Mock()
            )

    @patch("src.agente.fluxo.SQLGenerator")
    @patch("src.agente.fluxo.completar_interpretacao")
    def test_05_nao_executa_sql_se_geracao_falhar(
        self, completar, classe_sql
    ):
        completar.return_value = INTERPRETACAO
        classe_sql.return_value.generate.side_effect = RuntimeError(
            "Consulta rejeitada"
        )
        banco = Mock()
        with self.assertRaisesRegex(RuntimeError, "Consulta rejeitada"):
            executar_requisicao(
                REQUISICAO, ESTRUTURA,
                criar_modelo(json.dumps(INTERPRETACAO)), banco,
            )
        banco.execute_select.assert_not_called()


if __name__ == "__main__":
    unittest.main()

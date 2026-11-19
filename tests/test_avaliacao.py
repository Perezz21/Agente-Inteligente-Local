"""Testes de comparação dos resultados SQL com referências."""
import json
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch

from src.agente.avaliacao import avaliar_resultados
from src.executar_experimentos import carregar_cenarios, executar_cenarios


class TesteAvaliacao(unittest.TestCase):
    def test_01_aceita_valores_decimais_equivalentes(self):
        resultado = avaliar_resultados(
            [{"valor": Decimal("21.100000")}],
            [{"valor": "21.10"}],
        )
        self.assertTrue(resultado["correto"])

    def test_02_ignora_ordem_de_linhas_por_padrao(self):
        reais = [{"id": 2}, {"id": 1}]
        referencia = [{"id": 1}, {"id": 2}]
        self.assertTrue(avaliar_resultados(reais, referencia)["correto"])

    def test_03_respeita_ordem_quando_solicitada(self):
        reais = [{"id": 2}, {"id": 1}]
        referencia = [{"id": 1}, {"id": 2}]
        self.assertFalse(avaliar_resultados(
            reais, referencia, ordem_importa=True
        )["correto"])

    def test_04_rejeita_valor_incorreto(self):
        self.assertFalse(avaliar_resultados(
            [{"valor": "25.60"}], [{"valor": "25.61"}]
        )["correto"])

    def test_05_rejeita_colunas_diferentes(self):
        self.assertFalse(avaliar_resultados(
            [{"codigo": 1}], [{"id": 1}]
        )["correto"])

    def test_06_respeita_quantidade_de_linhas_duplicadas(self):
        self.assertFalse(avaliar_resultados(
            [{"id": 1}, {"id": 1}], [{"id": 1}]
        )["correto"])

    def test_07_compara_datas_retornadas_pelo_conector(self):
        self.assertTrue(avaliar_resultados(
            [{"dia": date(2025, 1, 15)}],
            [{"dia": "2025-01-15"}],
        )["correto"] )
        self.assertTrue(avaliar_resultados(
            [{"dia": date(2025, 1, 15)}],
            [{"dia": date(2025, 1, 15)}],
        )["correto"])

    def test_08_rejeita_referencia_com_formato_invalido(self):
        with self.assertRaisesRegex(ValueError, "listas"):
            avaliar_resultados({}, [])

    def test_09_carrega_referencia_e_ordenacao(self):
        dados = [{"id": "cenario_01", "requisicao": {"entidade": "teste"},
                  "resultado_esperado": [{"id": 1}], "ordem_importa": True}]
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "casos.json"
            caminho.write_text(json.dumps(dados), encoding="utf-8")
            cenarios = carregar_cenarios(caminho)
        self.assertEqual(cenarios[0]["resultado_esperado"], [{"id": 1}])
        self.assertTrue(cenarios[0]["ordem_importa"])

    @patch("src.executar_experimentos.registrar_execucao")
    @patch("src.executar_experimentos.executar_requisicao")
    def test_10_registra_consulta_incorreta_sem_falha_tecnica(
        self, executar, registrar
    ):
        modelo = Mock()
        modelo.model = "modelo:teste"
        executar.return_value = {"registros": [{"id": 2}],
                                 "total_registros": 1, "metricas": {}}
        cenarios = [{"id": "cenario_01", "requisicao": {"entidade": "teste"},
                    "resultado_esperado": [{"id": 1}]}]
        with tempfile.TemporaryDirectory() as pasta:
            resumo = executar_cenarios(
                cenarios, 1, modelo, Mock(), {}, Path(pasta) / "log.jsonl"
            )
        self.assertEqual(resumo["sucessos"], 1)
        self.assertEqual(resumo["incorretos"], 1)
        self.assertEqual(resumo["falhas"], 0)
        self.assertFalse(registrar.call_args.kwargs["avaliacao"]["correto"])


if __name__ == "__main__":
    unittest.main()

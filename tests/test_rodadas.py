"""Testes de identificação de rodadas e validação do catálogo piloto."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.agente.registro_metricas import construir_registro
from src.executar_experimentos import carregar_cenarios, executar_cenarios


class TesteRodadasExperimentais(unittest.TestCase):
    @patch("src.executar_experimentos.registrar_execucao")
    @patch("src.executar_experimentos.executar_requisicao")
    def test_01_rodada_comum_a_todas_repeticoes(self, executar, registrar):
        modelo = Mock()
        modelo.model = "modelo:teste"
        executar.return_value = {"registros": [], "total_registros": 0, "metricas": {}}
        cenarios = [{"id": "teste", "requisicao": {"entidade": "rios"}}]
        with tempfile.TemporaryDirectory() as pasta:
            resumo = executar_cenarios(
                cenarios, 2, modelo, Mock(), {},
                Path(pasta) / "saida.jsonl", rodada_id="rodada_teste_01"
            )
        self.assertEqual(resumo["sucessos"], 2)
        self.assertEqual(
            [call.kwargs["rodada_id"] for call in registrar.call_args_list],
            ["rodada_teste_01", "rodada_teste_01"],
        )

    @patch("src.executar_experimentos.executar_requisicao")
    def test_02_falha_registra_rodada_e_repeticao(self, executar):
        executar.side_effect = RuntimeError("segredo_de_teste")
        modelo = Mock()
        modelo.model = "modelo:teste"
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "saida.jsonl"
            executar_cenarios(
                [{"id": "teste", "requisicao": {"entidade": "rios"}}],
                2, modelo, Mock(), {}, caminho, rodada_id="rodada_teste_02"
            )
            registros = [
                json.loads(linha) for linha in caminho.read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
        self.assertEqual([r["repeticao"] for r in registros], [1, 2])
        self.assertTrue(all(
            r["rodada_id"] == "rodada_teste_02" for r in registros
        ))
        self.assertNotIn("segredo_de_teste", json.dumps(registros))

    def test_03_valida_catalogo_piloto(self):
        caminho = Path(__file__).resolve().parents[1] / "experiments" / "cenarios_piloto.json"
        cenarios = carregar_cenarios(caminho)
        self.assertEqual(len(cenarios), 4)
        self.assertEqual(
            sum(c["resultado_esperado"] is not None for c in cenarios), 2
        )

    def test_04_rejeita_rodada_vazia(self):
        with self.assertRaisesRegex(ValueError, "rodada inválido"):
            executar_cenarios([], 1, Mock(), Mock(), {}, rodada_id="")

    def test_05_gera_id_automaticamente_nas_rodadas(self):
        with patch("src.executar_experimentos.registrar_execucao") as registrar:
            with patch("src.executar_experimentos.executar_requisicao") as executar:
                executar.return_value = {"registros": [], "total_registros": 0, "metricas": {}}
                modelo = Mock()
                modelo.model = "modelo:teste"
                executar_cenarios(
                    [{"id": "teste", "requisicao": {"entidade": "rios"}}],
                    1, modelo, Mock(), {},
                )
                self.assertEqual(len(registrar.call_args.kwargs["rodada_id"]), 32)


if __name__ == "__main__":
    unittest.main()

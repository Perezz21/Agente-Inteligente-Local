"""Testes do executor experimental sem abrir MySQL ou Ollama."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.executar_experimentos import carregar_cenarios, executar_cenarios


class TesteCenariosExperimentais(unittest.TestCase):
    def criar_arquivo(self, pasta, dados):
        arquivo = Path(pasta) / "cenarios.json"
        arquivo.write_text(json.dumps(dados), encoding="utf-8")
        return arquivo

    def test_01_carrega_lista_valida(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = self.criar_arquivo(
                pasta, [{"id": "cenario_01", "requisicao": {"entidade": "medicoes"}}]
            )
            self.assertEqual(carregar_cenarios(caminho)[0]["id"], "cenario_01")

    def test_02_rejeita_identificadores_repetidos(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = self.criar_arquivo(pasta, [
                {"id": "mesmo", "requisicao": {"a": 1}},
                {"id": "mesmo", "requisicao": {"a": 2}},
            ])
            with self.assertRaisesRegex(ValueError, "repetidos"):
                carregar_cenarios(caminho)

    def test_03_rejeita_requisicao_vazia(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = self.criar_arquivo(
                pasta, [{"id": "cenario_01", "requisicao": {}}]
            )
            with self.assertRaisesRegex(ValueError, "não vazia"):
                carregar_cenarios(caminho)

    @patch("src.executar_experimentos.registrar_execucao")
    @patch("src.executar_experimentos.executar_requisicao")
    def test_04_repeticoes_e_sucessos(self, executar, registrar):
        modelo = Mock()
        modelo.model = "modelo:teste"
        executar.return_value = {"total_registros": 3, "metricas": {}}
        cenario = [{"id": "cenario_01", "requisicao": {"a": 1}}]
        with tempfile.TemporaryDirectory() as pasta:
            destino = Path(pasta) / "execucoes.jsonl"
            resultado = executar_cenarios(
                cenario, 3, modelo, Mock(), {}, destino
            )
        self.assertEqual(resultado, {"sucessos": 3, "falhas": 0})
        self.assertEqual(executar.call_count, 3)
        self.assertEqual(registrar.call_count, 3)

    @patch("src.executar_experimentos.executar_requisicao")
    def test_05_registra_falhas_sem_dados_da_consulta(self, executar):
        executar.side_effect = ValueError("senha_de_teste_e_filtro_privado")
        modelo = Mock()
        modelo.model = "modelo:teste"
        cenario = [{"id": "cenario_01", "requisicao": {"a": 1}}]
        with tempfile.TemporaryDirectory() as pasta:
            destino = Path(pasta) / "execucoes.jsonl"
            resumo = executar_cenarios(
                cenario, 2, modelo, Mock(), {}, destino
            )
            texto = destino.read_text(encoding="utf-8")
        self.assertEqual(resumo, {"sucessos": 0, "falhas": 2})
        self.assertEqual(len(texto.splitlines()), 2)
        self.assertNotIn("senha_de_teste_e_filtro_privado", texto)
        self.assertEqual(json.loads(texto.splitlines()[0])["tipo_erro"], "ValueError")

    def test_06_rejeita_repeticoes_fora_do_limite(self):
        with self.assertRaisesRegex(ValueError, "entre 1 e 100"):
            executar_cenarios([], 0, Mock(), Mock(), {})
        with self.assertRaisesRegex(ValueError, "entre 1 e 100"):
            executar_cenarios([], 101, Mock(), Mock(), {})


if __name__ == "__main__":
    unittest.main()

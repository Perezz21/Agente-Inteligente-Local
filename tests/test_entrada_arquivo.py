"""Testes de entrada JSON por arquivo sem Ollama nem MySQL."""

import json
import tempfile
import unittest
from pathlib import Path

from src.agente.entrada import receber_arquivo_json


class TesteEntradaPorArquivo(unittest.TestCase):
    def test_01_carrega_requisicao_valida(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "requisicao.json"
            dados = {
                "versao": "1.0",
                "entidade": "filmes", "campos": ["título do filme"],
                "filtros": {}, "agrupamento": [], "agregacoes": [],
            }
            arquivo.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(
                receber_arquivo_json(arquivo), dados,
            )

    def test_05_rejeita_json_antigo_sem_versao(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "legado.json"
            arquivo.write_text(
                json.dumps({"entidade": "filmes", "campos": ["título"]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "versao"):
                receber_arquivo_json(arquivo)

    def test_02_rejeita_json_malformado(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "requisicao.json"
            arquivo.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "JSON inválido"):
                receber_arquivo_json(arquivo)

    def test_03_rejeita_lista_em_vez_de_objeto(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "requisicao.json"
            arquivo.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "objeto JSON"):
                receber_arquivo_json(arquivo)

    def test_04_informa_erro_se_arquivo_nao_existe(self):
        with tempfile.TemporaryDirectory() as pasta:
            with self.assertRaisesRegex(ValueError, "Não foi possível ler"):
                receber_arquivo_json(Path(pasta) / "inexistente.json")


if __name__ == "__main__":
    unittest.main()

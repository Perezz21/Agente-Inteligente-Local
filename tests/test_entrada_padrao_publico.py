"""O JSON externo deve ser validado antes de acessar LLM ou banco de dados."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.agente.entrada import receber_json, receber_arquivo_json
from src.executar_experimentos import carregar_cenarios


def requi():
    return {
        "entidade": "registros",
        "campos": ["nome"],
        "filtros": {},
        "agrupamento": [],
        "agregacoes": [],
    }


class TesteEntradaPublicaEstrita(unittest.TestCase):
    def test_01_recusa_legado_antes_de_abrir_banco_ou_modelo(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "legado.json"
            arquivo.write_text(
                json.dumps(dict(requi(), versao="1.0")),
                encoding="utf-8",
            )
            with (
                patch("src.main.DatabaseClient") as banco,
                patch("src.main.OllamaModelClient") as modelo,
                patch("src.main.OllamaConfig") as config,
                patch("sys.argv", ["src.main", "--arquivo", str(arquivo)]),
                patch("builtins.print") as saida,
            ):
                from src.main import main
                main()
                banco.return_value.connect.assert_not_called()
                modelo.assert_not_called()
                config.from_environment.assert_not_called()
                self.assertIn("fora do padrão", str(saida.call_args))
                self.assertIn("versao", str(saida.call_args))

    def test_02_entrada_interativa_aceita_json_valido(self):
        linhas = json.dumps(requi(), ensure_ascii=False, indent=2).splitlines()
        with patch("builtins.input", side_effect=linhas + [""]):
            recebida = receber_json()
        self.assertEqual(recebida, requi())

    def test_03_entrada_interativa_recusa_legado(self):
        with patch("builtins.input", side_effect=[
            json.dumps(dict(requi(), versao="1.0")), ""
        ]):
            with self.assertRaisesRegex(ValueError, "versao"):
                receber_json()

    def test_04_cenario_externo_recusa_requisicao_com_versao(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "cenarios.json"
            arquivo.write_text(
                json.dumps([{
                    "id": "teste",
                    "requisicao": dict(requi(), versao="1.0"),
                }]),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "versao"):
                carregar_cenarios(arquivo)

    def test_05_cenario_externo_aceita_pedido_valido(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "cenarios.json"
            arquivo.write_text(
                json.dumps([{"id": "teste", "requisicao": requi()}]),
                encoding="utf-8",
            )
            cenarios = carregar_cenarios(arquivo)
            self.assertEqual(
                cenarios[0]["requisicao"], requi(),
            )

    def test_06_rejeita_propriedade_nao_definida(self):
        dados = requi()
        dados["schema"] = {"tabela": "pessoa"}
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "nao_padrao.json"
            arquivo.write_text(json.dumps(dados), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "fora do padrão"):
                receber_arquivo_json(arquivo)


if __name__ == "__main__":
    unittest.main()

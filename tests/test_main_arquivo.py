"""Garante que o programa principal aceita --arquivo sem entrada manual."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src import main as modulo_main


class TestePrincipalPorArquivo(unittest.TestCase):
    @patch("src.main.registrar_execucao")
    @patch("src.main._executar_requisicao_validada")
    @patch("src.main.receber_json")
    @patch("src.main.OllamaModelClient")
    @patch("src.main.OllamaConfig")
    @patch("src.main.DatabaseClient")
    def test_01_utiliza_arquivo_sem_solicitar_colagem(
        self, banco_cls, config_cls, modelo_cls, receber_json,
        executar, registrar
    ):
        banco = banco_cls.return_value
        banco.get_database_structure.return_value = {
            "tabelas": {"filme": {"colunas": []}},
            "relacionamentos": [],
        }
        config_cls.from_environment.return_value.model = "modelo:teste"
        modelo_cls.return_value.check_connection.return_value = ["modelo:teste"]
        executar.return_value = {
            "interpretacao": {"status": "sucesso"},
            "consulta_sql": "SELECT filme.titulo FROM filme",
            "parametros": [],
            "registros": [{"titulo": "Filme A"}],
            "total_registros": 1,
            "metricas": {
                "tempo_total_segundos": 0,
                "tempo_interpretacao_segundos": 0,
                "tempo_geracao_sql_segundos": 0,
                "tempo_execucao_mysql_segundos": 0,
                "tentativas_sql": 1,
                "interpretacao": {
                    "carregamento_segundos": 0.0,
                    "processamento_prompt_segundos": 0.0,
                    "geracao_segundos": 0.0,
                    "tokens_entrada": 10,
                    "tokens_gerados": 10,
                },
            },
        }
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "consulta.json"
            arquivo.write_text(
                '{"entidade":"filmes","campos":["título do filme"],'
                '"filtros":{},"agrupamento":[],"agregacoes":[]}' ,
                encoding="utf-8",
            )
            with patch("sys.argv", ["main", "--arquivo", str(arquivo)]):
                with patch("builtins.print"):
                    modulo_main.main()

        receber_json.assert_not_called()
        self.assertEqual(
            executar.call_args.kwargs["requisicao"],
            {"filtros": {}, "agrupamento": [], "agregacoes": [],
             "entidade": "filmes", "campos": ["título do filme"]},
        )
        banco.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()

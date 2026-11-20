"""Testes isolados de configuracao e prioridade das variaveis de ambiente."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dotenv import load_dotenv

from src.agente.config import OllamaConfig, load_local_environment


class TesteConfiguracaoEnv(unittest.TestCase):
    def test_variavel_do_sistema_tem_prioridade(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / ".env"
            arquivo.write_text(
                "OLLAMA_MODEL=modelo_do_arquivo\n", encoding="utf-8"
            )
            with patch.dict(
                os.environ, {"OLLAMA_MODEL": "modelo_do_sistema"}
            ):
                load_dotenv(arquivo, override=False)
                self.assertEqual(
                    os.environ["OLLAMA_MODEL"], "modelo_do_sistema"
                )

    def test_carrega_valor_quando_variavel_nao_existe(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / ".env"
            arquivo.write_text(
                "OLLAMA_MODEL=modelo_de_teste\n", encoding="utf-8"
            )
            with patch.dict(os.environ, {}, clear=True):
                load_dotenv(arquivo, override=False)
                self.assertEqual(
                    os.environ["OLLAMA_MODEL"], "modelo_de_teste"
                )

    @patch("src.agente.config.load_local_environment")
    def test_config_modelo_carrega_ambiente(self, carregar):
        with patch.dict(
            os.environ,
            {
                "OLLAMA_HOST": "http://localhost:11434",
                "OLLAMA_MODEL": "qwen3.5:4b",
            },
        ):
            config = OllamaConfig.from_environment()
        carregar.assert_called_once()
        self.assertEqual(config.model, "qwen3.5:4b")

    @patch("src.agente.config.load_dotenv")
    def test_caminho_env_independente_do_diretorio_atual(self, carregar):
        load_local_environment()
        arquivo = carregar.call_args.kwargs["dotenv_path"]
        self.assertEqual(arquivo.name, ".env")
        self.assertEqual(arquivo.parent, Path(__file__).resolve().parents[1])
        self.assertFalse(carregar.call_args.kwargs["override"])


if __name__ == "__main__":
    unittest.main()

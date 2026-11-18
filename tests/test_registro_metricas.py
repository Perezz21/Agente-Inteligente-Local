"""Testes do armazenamento mínimo de métricas, sem dados sensíveis."""

import json
import tempfile
import unittest
from pathlib import Path

from src.agente.registro_metricas import construir_registro, registrar_execucao


RESPOSTA = {
    "consulta_sql": "SELECT * FROM tabela WHERE senha = %s",
    "parametros": ["SENHA_DE_TESTE_NAO_REAL"],
    "registros": [{"segredo": "VALOR_DE_TESTE_NAO_REAL"}],
    "total_registros": 3,
    "metricas": {
        "tempo_total_segundos": 31.49,
        "tempo_interpretacao_segundos": 21.55,
        "tempo_geracao_sql_segundos": 9.93,
        "tempo_execucao_mysql_segundos": 0.01,
        "tentativas_sql": 1,
        "interpretacao": {
            "carregamento_segundos": 0.001,
            "processamento_prompt_segundos": 0.22,
            "geracao_segundos": 21.09,
            "tokens_entrada": 1863,
            "tokens_gerados": 232,
        },
    },
}


class TesteRegistroMetricas(unittest.TestCase):
    def test_01_preserva_tempos_modelo_cenario_e_contagem(self):
        registro = construir_registro(RESPOSTA, "modelo:teste", "cenario_01")
        self.assertEqual(registro["modelo"], "modelo:teste")
        self.assertEqual(registro["cenario"], "cenario_01")
        self.assertEqual(registro["tentativas_sql"], 1)
        self.assertEqual(registro["tempo_total_segundos"], 31.49)
        self.assertEqual(registro["ollama_interpretacao"]["tokens_entrada"], 1863)
        self.assertEqual(registro["status"], "sucesso")
        self.assertIn("+00:00", registro["data_hora_utc"])

    def test_02_nao_grava_sql_parametros_ou_resultados(self):
        texto = json.dumps(construir_registro(RESPOSTA, "modelo:teste"))
        self.assertNotIn("SELECT", texto)
        self.assertNotIn("SENHA_DE_TESTE_NAO_REAL", texto)
        self.assertNotIn("VALOR_DE_TESTE_NAO_REAL", texto)
        self.assertNotIn("registros\": [", texto)

    def test_03_cria_arquivo_em_diretorio_novo(self):
        with tempfile.TemporaryDirectory() as pasta:
            destino = Path(pasta) / "subpasta" / "execucoes.jsonl"
            retorno = registrar_execucao(
                RESPOSTA, "modelo:teste", "cenario_01", destino
            )
            self.assertEqual(retorno, destino)
            linha = destino.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(linha), 1)
            self.assertEqual(json.loads(linha[0])["cenario"], "cenario_01")

    def test_04_acrescenta_sem_apagar_registros_anteriores(self):
        with tempfile.TemporaryDirectory() as pasta:
            destino = Path(pasta) / "execucoes.jsonl"
            registrar_execucao(RESPOSTA, "modelo:teste", "cenario_01", destino)
            registrar_execucao(RESPOSTA, "modelo:teste", "cenario_02", destino)
            linhas = destino.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(linhas), 2)
            self.assertEqual(json.loads(linhas[0])["cenario"], "cenario_01")
            self.assertEqual(json.loads(linhas[1])["cenario"], "cenario_02")

    def test_05_rejeita_identificadores_vazios(self):
        with self.assertRaises(ValueError):
            construir_registro(RESPOSTA, "", "cenario_01")
        with self.assertRaises(ValueError):
            construir_registro(RESPOSTA, "modelo:teste", "")


if __name__ == "__main__":
    unittest.main()

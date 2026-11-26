"""Testes do modo JSON estruturado e da recuperação da interpretação."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.agente.fluxo import executar_requisicao
from src.agente.ollama_client import OllamaModelClient
from src.agente.config import OllamaConfig
from src.agente.esquema_interpretacao import ESQUEMA_INTERPRETACAO


INTERPRETACAO = {
    "tabelas_identificadas": ["filme"],
    "campos_solicitados": ["filme.titulo"],
    "filtros": [],
    "relacionamentos_necessarios": [],
    "status": "sucesso",
    "observacoes": "",
}


def retorno(conteudo):
    return SimpleNamespace(
        content=conteudo, load_seconds=0, prompt_eval_seconds=0,
        generation_seconds=0, prompt_tokens=10, generated_tokens=50,
    )


class TesteInterpretacaoEstruturada(unittest.TestCase):
    @patch("src.agente.fluxo.completar_interpretacao")
    @patch("src.agente.fluxo.SQLGenerator")
    def test_01_recupera_json_invalido_na_segunda_tentativa(
        self, sql_generator, completar
    ):
        completar.return_value = INTERPRETACAO
        sql_generator.return_value.generate.return_value = {
            "consulta_sql": "SELECT filme.titulo FROM filme",
            "parametros": [],
        }
        modelo = Mock()
        modelo.generate.side_effect = [
            retorno("explicação em texto"), retorno(json.dumps(INTERPRETACAO))
        ]
        banco = Mock()
        banco.execute_select.return_value = [{"titulo": "Filme A"}]
        resultado = executar_requisicao(
            {"filtros": {}, "agrupamento": [], "agregacoes": [],
                 "entidade": "filmes", "campos": ["título"]},
            {"tabelas": {"filme": {"colunas": [{"nome": "titulo"}]}}, "relacionamentos": []},
            modelo, banco
        )
        self.assertEqual(resultado["metricas"]["tentativas_interpretacao"], 2)
        self.assertEqual(modelo.generate.call_count, 2)
        self.assertEqual(modelo.generate.call_args.kwargs["max_tokens"], 1200)
        self.assertTrue(modelo.generate.call_args.kwargs["json_mode"])
        self.assertEqual(
            modelo.generate.call_args.kwargs["json_schema"],
            ESQUEMA_INTERPRETACAO,
        )
        banco.execute_select.assert_called_once()

    def test_02_nao_executa_sql_se_interpretacao_invalida(self):
        modelo = Mock()
        modelo.generate.return_value = retorno("resposta não JSON")
        banco = Mock()
        with self.assertRaisesRegex(ValueError, "JSON válido"):
            executar_requisicao(
                {"filtros": {}, "agrupamento": [], "agregacoes": [],
                 "entidade": "filmes", "campos": ["título"]},
                {"tabelas": {"filme": {"colunas": [{"nome": "titulo"}]}}, "relacionamentos": []},
                modelo, banco,
            )
        self.assertEqual(modelo.generate.call_count, 2)
        banco.execute_select.assert_not_called()

    def test_03_recusa_formato_invalido_das_listas(self):
        modelo = Mock()
        modelo.generate.return_value = retorno(json.dumps({
            **INTERPRETACAO, "campos_solicitados": "filme.titulo"
        }))
        with self.assertRaisesRegex(ValueError, "Tipos inválidos"):
            executar_requisicao(
                {"filtros": {}, "agrupamento": [], "agregacoes": [],
                 "entidade": "filmes", "campos": ["título"]},
                {"tabelas": {"filme": {"colunas": [{"nome": "titulo"}]}}, "relacionamentos": []},
                modelo, Mock(),
            )

    @patch("src.agente.ollama_client.Client")
    def test_04_solicita_json_no_ollama(self, cliente):
        resposta = Mock()
        resposta.message.content = '{"status":"sucesso"}'
        resposta.load_duration = 0
        resposta.prompt_eval_duration = 0
        resposta.eval_duration = 0
        resposta.prompt_eval_count = 1
        resposta.eval_count = 1
        cliente.return_value.chat.return_value = resposta

        modelo = OllamaModelClient(OllamaConfig(model="modelo:teste"))
        resultado = modelo.generate("teste", json_mode=True)
        self.assertEqual(resultado.content, '{"status":"sucesso"}')
        self.assertEqual(cliente.return_value.chat.call_args.kwargs["format"], "json")

    @patch("src.agente.ollama_client.Client")
    def test_06_envia_json_schema_ao_ollama(self, cliente):
        resposta = Mock()
        resposta.message.content = json.dumps(INTERPRETACAO)
        resposta.load_duration = None
        resposta.prompt_eval_duration = None
        resposta.eval_duration = None
        resposta.prompt_eval_count = None
        resposta.eval_count = None
        cliente.return_value.chat.return_value = resposta
        modelo = OllamaModelClient(OllamaConfig(model="modelo:teste"))
        modelo.generate("teste", json_schema=ESQUEMA_INTERPRETACAO)
        self.assertEqual(
            cliente.return_value.chat.call_args.kwargs["format"],
            ESQUEMA_INTERPRETACAO,
        )

    def test_07_esquema_exige_todas_as_chaves(self):
        self.assertEqual(
            set(ESQUEMA_INTERPRETACAO["required"]),
            set(INTERPRETACAO),
        )
        self.assertFalse(ESQUEMA_INTERPRETACAO["additionalProperties"])

    @patch("src.agente.ollama_client.Client")
    def test_05_modo_json_nao_afeta_geracao_sql(self, cliente):
        resposta = Mock()
        resposta.message.content = "texto"
        resposta.load_duration = None
        resposta.prompt_eval_duration = None
        resposta.eval_duration = None
        resposta.prompt_eval_count = None
        resposta.eval_count = None
        cliente.return_value.chat.return_value = resposta

        modelo = OllamaModelClient(OllamaConfig(model="modelo:teste"))
        modelo.generate("teste")
        self.assertNotIn("format", cliente.return_value.chat.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()

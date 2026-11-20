"""Testes do contrato JSON v1, incluindo compatibilidade e fluxo real mockado."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.agente.contrato_requisicao import (
    ESQUEMA_REQUISICAO_V1, normalizar_requisicao,
)
from src.agente.entrada import receber_arquivo_json
from src.agente.fluxo import executar_requisicao
from src.executar_experimentos import carregar_cenarios


def requisicao_v1():
    return {
        "versao": "1.0",
        "entidade": "filmes",
        "campos": ["título do filme"],
        "filtros": {},
        "agrupamento": [],
        "agregacoes": [],
    }


class TesteContratoRequisicaoV1(unittest.TestCase):
    def test_01_normaliza_v1_sem_modificar_entrada(self):
        original = requisicao_v1()
        normalizada = normalizar_requisicao(original)
        self.assertEqual(normalizada, {
            "entidade": "filmes", "campos": ["título do filme"]
        })
        self.assertEqual(original, requisicao_v1())

    def test_02_preserva_requisicao_legada(self):
        antiga = {"entidade": "filmes", "campos": ["título do filme"]}
        self.assertIs(normalizar_requisicao(antiga), antiga)

    def test_03_valida_filtros_agrupamento_e_agregacoes(self):
        dados = requisicao_v1()
        dados["filtros"] = {"municipio": "Jataí", "ano": 2025}
        dados["campos"] = ["nome do município", "média da vazão"]
        dados["agrupamento"] = ["municipios.nome"]
        dados["agregacoes"] = [
            {"funcao": "AVG", "campo": "medicoes.vazao_m3_s"}
        ]
        recebido = normalizar_requisicao(dados)
        self.assertEqual(recebido["filtros"]["ano"], 2025)
        self.assertEqual(recebido["agrupamento"], ["municipios.nome"])
        self.assertEqual(recebido["agregacoes"][0]["funcao"], "AVG")
        self.assertNotIn("versao", recebido)

    def test_04_rejeita_versao_nao_suportada(self):
        dados = requisicao_v1()
        dados["versao"] = "2.0"
        with self.assertRaisesRegex(ValueError, "Versão"):
            normalizar_requisicao(dados)

    def test_05_rejeita_campos_obrigatorios_faltantes(self):
        dados = requisicao_v1()
        del dados["agrupamento"]
        with self.assertRaisesRegex(ValueError, "obrigatórios ausentes"):
            normalizar_requisicao(dados)

    def test_06_rejeita_propriedades_extras(self):
        dados = requisicao_v1()
        dados["consulta_sql"] = "SELECT * FROM filme"
        with self.assertRaisesRegex(ValueError, "desconhecidas"):
            normalizar_requisicao(dados)

    def test_07_rejeita_entidade_e_campos_invalidos(self):
        for entidade, campos in [
            ("", ["título"]), (4, ["título"]), ("filmes", []),
            ("filmes", [""]), ("filmes", ["título", 10]),
        ]:
            with self.subTest(entidade=entidade, campos=campos):
                dados = requisicao_v1()
                dados["entidade"] = entidade
                dados["campos"] = campos
                with self.assertRaises(ValueError):
                    normalizar_requisicao(dados)

    def test_08_rejeita_filtros_invalidos(self):
        for filtros in [
            [], {"ano": [2025]}, {"cidade": {"nome": "Jataí"}},
            {"municipio": None}, {"": "valor"}, {"ano": float("nan")},
        ]:
            with self.subTest(filtros=filtros):
                dados = requisicao_v1()
                dados["filtros"] = filtros
                with self.assertRaises(ValueError):
                    normalizar_requisicao(dados)

    def test_09_rejeita_agrupamento_sem_referencia_fisica(self):
        dados = requisicao_v1()
        dados["agrupamento"] = ["nome do município"]
        with self.assertRaisesRegex(ValueError, "agrupamento"):
            normalizar_requisicao(dados)

    def test_10_rejeita_agregacao_nao_suportada(self):
        dados = requisicao_v1()
        dados["agregacoes"] = [{"funcao": "MEDIAN", "campo": "medicoes.vazao_m3_s"}]
        with self.assertRaisesRegex(ValueError, "Função"):
            normalizar_requisicao(dados)

    def test_11_rejeita_agregacao_malformada(self):
        dados = requisicao_v1()
        dados["agregacoes"] = [{"funcao": "AVG", "campo": "vazao"}]
        with self.assertRaisesRegex(ValueError, "campo de agregação"):
            normalizar_requisicao(dados)
        dados["agregacoes"] = [{"funcao": "AVG"}]
        with self.assertRaisesRegex(ValueError, "exatamente"):
            normalizar_requisicao(dados)

    def test_12_schema_declara_seis_propriedades_obrigatorias(self):
        self.assertEqual(
            set(ESQUEMA_REQUISICAO_V1["required"]),
            set(requisicao_v1()),
        )
        self.assertFalse(ESQUEMA_REQUISICAO_V1["additionalProperties"])

    def test_13_leitura_de_arquivo_json_v1(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "requisicao.json"
            arquivo.write_text(
                json.dumps(requisicao_v1(), ensure_ascii=False),
                encoding="utf-8",
            )
            self.assertEqual(
                receber_arquivo_json(arquivo),
                {"entidade": "filmes", "campos": ["título do filme"]},
            )

    def test_14_exemplo_versionado_do_repositorio(self):
        raiz = Path(__file__).resolve().parents[1]
        exemplo = raiz / "experiments" / "requisicao_sakila_filmes_v1.json"
        dados = json.loads(exemplo.read_text(encoding="utf-8"))
        self.assertEqual(dados, requisicao_v1())
        self.assertEqual(
            normalizar_requisicao(dados)["campos"], ["título do filme"]
        )

    def test_15_cenario_experimental_versionado(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "cenarios.json"
            arquivo.write_text(
                json.dumps([{"id": "v1", "requisicao": requisicao_v1()}]),
                encoding="utf-8",
            )
            cenarios = carregar_cenarios(arquivo)
        self.assertEqual(
            cenarios[0]["requisicao"],
            {"entidade": "filmes", "campos": ["título do filme"]},
        )

    @patch("src.agente.fluxo.SQLGenerator")
    @patch("src.agente.fluxo.completar_interpretacao")
    def test_16_fluxo_direto_normaliza_v1_antes_do_ollama(
        self, completar, gerador_cls
    ):
        interpretacao = {
            "tabelas_identificadas": ["filme"],
            "campos_solicitados": ["filme.titulo"],
            "filtros": [],
            "relacionamentos_necessarios": [],
            "status": "sucesso",
            "observacoes": "",
        }
        completar.return_value = interpretacao
        gerador_cls.return_value.generate.return_value = {
            "consulta_sql": "SELECT filme.titulo FROM filme",
            "parametros": [],
        }
        modelo = Mock()
        modelo.generate.return_value = SimpleNamespace(
            content=json.dumps(interpretacao),
            load_seconds=0.0, prompt_eval_seconds=0.0,
            generation_seconds=0.0, prompt_tokens=1,
            generated_tokens=1,
        )
        banco = Mock()
        banco.execute_select.return_value = [{"titulo": "Filme A"}]
        estrutura = {"tabelas": {}, "relacionamentos": []}
        resposta = executar_requisicao(
            requisicao_v1(), estrutura, modelo, banco
        )
        self.assertEqual(resposta["total_registros"], 1)
        completar.assert_called_once_with(
            {"entidade": "filmes", "campos": ["título do filme"]},
            interpretacao, estrutura,
        )

    def test_17_rejeita_requisicao_nao_json_objeto(self):
        with self.assertRaisesRegex(ValueError, "objeto JSON"):
            normalizar_requisicao(["filmes"])


if __name__ == "__main__":
    unittest.main()

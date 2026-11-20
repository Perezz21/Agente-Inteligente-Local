"""Regressões: o modelo não pode copiar metadados do catálogo."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.agente.fluxo import executar_requisicao, montar_prompt
from src.agente.validacao_mapeamento import validar_mapeamento


ESTRUTURA = {
    "banco": "exemplo",
    "tabelas": {
        "filme": {"colunas": [
            {"nome": "titulo", "tipo": "varchar", "permite_nulo": "NO", "chave": ""},
            {"nome": "id", "tipo": "int", "permite_nulo": "NO", "chave": "PRI"},
        ]},
        "pessoa": {"colunas": [
            {"nome": "nome", "tipo": "varchar", "permite_nulo": "NO", "chave": ""},
        ]},
    },
    "relacionamentos": [],
}
REQUISICAO = {"entidade": "filmes", "campos": ["título do filme"]}


def interpretacao(campos=None, filtros=None, tabelas=None):
    return {
        "tabelas_identificadas": ["filme"] if tabelas is None else tabelas,
        "campos_solicitados": ["filme.titulo"] if campos is None else campos,
        "filtros": [] if filtros is None else filtros,
        "relacionamentos_necessarios": [],
        "status": "sucesso",
        "observacoes": "",
    }


def retorno(dados):
    return SimpleNamespace(
        content=json.dumps(dados), load_seconds=0,
        prompt_eval_seconds=0, generation_seconds=0,
        prompt_tokens=1, generated_tokens=1,
    )


class TesteValidacaoMapeamento(unittest.TestCase):
    def test_01_aceita_coluna_real(self):
        self.assertIsNone(validar_mapeamento(
            interpretacao(), REQUISICAO, ESTRUTURA
        ))

    def test_filtros_preservam_chave_valor_tipo_e_coluna_explicita(self):
        pedido = {**REQUISICAO, "filtros": {"filme.id": 1}}
        filtro = {"chave_pedida": "filme.id", "campo": "filme.id",
                  "operador": "=", "valor": 1}
        self.assertIsNone(validar_mapeamento(
            interpretacao(filtros=[filtro]), pedido, ESTRUTURA))
        for filtros in ([], [filtro, filtro], [{**filtro, "valor": True}],
                        [{**filtro, "valor": 2}], [{**filtro, "campo": "pessoa.nome"}],
                        [{**filtro, "chave_pedida": "outro"}]):
            with self.subTest(filtros=filtros):
                self.assertIsNotNone(validar_mapeamento(
                    interpretacao(filtros=filtros), pedido, ESTRUTURA))

    def test_campo_explicito_nao_pode_ser_substituido(self):
        for nome in ("filme.titulo", "titulo"):
            pedido = {**REQUISICAO, "campos": [nome]}
            self.assertIsNotNone(validar_mapeamento(
                interpretacao(campos=["filme.id"]), pedido, ESTRUTURA))

    def test_filtro_omitido_impede_execucao(self):
        pedido = {**REQUISICAO, "filtros": {"ano": 2020}}
        modelo, banco = Mock(), Mock()
        modelo.generate.return_value = retorno(interpretacao())
        with self.assertRaisesRegex(ValueError, "Filtros solicitados ausentes"):
            executar_requisicao(pedido, ESTRUTURA, modelo, banco)
        banco.execute_select.assert_not_called()

    def test_02_rejeita_metadados_sem_tabela(self):
        erro = validar_mapeamento(
            interpretacao(campos=["tipo", "permite_nulo", "chave"]),
            REQUISICAO, ESTRUTURA,
        )
        self.assertIn("Campo solicitado", erro)

    def test_03_rejeita_filtros_inventados(self):
        erro = validar_mapeamento(
            interpretacao(filtros=[
                {"campo": "pessoa.nome", "operador": "=", "valor": "X"}
            ]),
            REQUISICAO, ESTRUTURA,
        )
        self.assertIn("filtros", erro)

    def test_04_rejeita_mapeamento_de_todas_as_colunas(self):
        erro = validar_mapeamento(
            interpretacao(campos=["filme.titulo", "filme.id"]),
            REQUISICAO, ESTRUTURA,
        )
        self.assertIn("Quantidade", erro)

    def test_05_prompt_compacta_metadados(self):
        prompt = montar_prompt(REQUISICAO, ESTRUTURA)
        self.assertIn("filme", prompt)
        self.assertIn("titulo", prompt)
        self.assertNotIn("permite_nulo", prompt)
        self.assertIn("título do filme", prompt)

    @patch("src.agente.fluxo.SQLGenerator")
    @patch("src.agente.fluxo.completar_interpretacao")
    def test_06_tenta_novamente_apos_mapeamento_ruim(
        self, completar, sql_generator
    ):
        completar.return_value = interpretacao()
        sql_generator.return_value.generate.return_value = {
            "consulta_sql": "SELECT filme.titulo FROM filme",
            "parametros": [],
        }
        modelo = Mock()
        modelo.generate.side_effect = [
            retorno(interpretacao(campos=["tipo", "chave"])),
            retorno(interpretacao()),
        ]
        banco = Mock()
        banco.execute_select.return_value = [{"titulo": "Filme A"}]
        resposta = executar_requisicao(
            REQUISICAO, ESTRUTURA, modelo, banco
        )
        self.assertEqual(resposta["metricas"]["tentativas_interpretacao"], 2)
        self.assertEqual(resposta["total_registros"], 1)

    @patch("src.agente.fluxo.SQLGenerator")
    @patch("src.agente.fluxo.completar_interpretacao")
    def test_08_status_ambiguo_recupera_na_segunda_tentativa(
        self, completar, sql_generator
    ):
        completar.return_value = interpretacao()
        sql_generator.return_value.generate.return_value = {
            "consulta_sql": "SELECT filme.titulo FROM filme", "parametros": [],
        }
        primeiro = interpretacao()
        primeiro["status"] = "ambiguo"
        primeiro["observacoes"] = "Não encontrei a coluna."
        modelo = Mock()
        modelo.generate.side_effect = [retorno(primeiro), retorno(interpretacao())]
        banco = Mock()
        banco.execute_select.return_value = [{"titulo": "Filme A"}]
        resposta = executar_requisicao(REQUISICAO, ESTRUTURA, modelo, banco)
        self.assertEqual(resposta["metricas"]["tentativas_interpretacao"], 2)
        self.assertIn("Não encontrei a coluna", modelo.generate.call_args.kwargs["prompt"])

    def test_09_status_ambiguo_exibe_motivo_sem_gerar_sql(self):
        primeiro = interpretacao()
        primeiro["status"] = "ambiguo"
        primeiro["observacoes"] = "Há mais de uma coluna possível."
        modelo = Mock()
        modelo.generate.return_value = retorno(primeiro)
        banco = Mock()
        with self.assertRaisesRegex(ValueError, "Há mais de uma coluna possível"):
            executar_requisicao(REQUISICAO, ESTRUTURA, modelo, banco)
        banco.execute_select.assert_not_called()

    def test_10_prompt_contem_quebras_reais_de_linha(self):
        prompt = montar_prompt(REQUISICAO, ESTRUTURA)
        self.assertIn("\nREQUISICAO DO USUARIO", prompt)
        self.assertNotIn(r"\\nREQUISICAO DO USUARIO", prompt)

    def test_11_prompt_nao_exige_filtro_para_consulta_simples(self):
        prompt = montar_prompt(REQUISICAO, ESTRUTURA)
        self.assertIn("FILTROS SÃO OPCIONAIS", prompt)
        self.assertIn("filtros: []", prompt)
        self.assertIn("status sucesso mesmo sem", prompt)

    def test_07_rejeita_apos_duas_interpretacoes_sem_colunas_validas(self):
        modelo = Mock()
        modelo.generate.return_value = retorno(
            interpretacao(campos=["chave"])
        )
        banco = Mock()
        with self.assertRaisesRegex(ValueError, "Campo solicitado"):
            executar_requisicao(REQUISICAO, ESTRUTURA, modelo, banco)
        banco.execute_select.assert_not_called()


if __name__ == "__main__":
    unittest.main()

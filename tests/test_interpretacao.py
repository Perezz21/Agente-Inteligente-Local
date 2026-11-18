"""Testa preservação de metadados estruturados entre interpretação e SQL."""

import copy
import unittest

from src.agente.interpretacao import completar_interpretacao


ESTRUTURA = {
    "tabelas": {
        "medicoes": {"colunas": [{"nome": "vazao_m3_s"}]},
        "rios": {"colunas": [{"nome": "nome"}]},
        "municipios": {"colunas": [{"nome": "nome"}]},
    }
}

INTERPRETACAO = {
    "status": "sucesso",
    "campos_solicitados": [
        "rios.nome",
        "municipios.nome",
        "AVG(medicoes.vazao_m3_s)",
    ],
}

REQUISICAO = {
    "entidade": "medições",
    "agrupamento": ["rios.nome", "municipios.nome"],
    "agregacoes": [
        {"funcao": "AVG", "campo": "medicoes.vazao_m3_s"}
    ],
}


class TesteMetadadosInterpretacao(unittest.TestCase):
    def test_preserva_agrupamento_e_agregacoes(self):
        resultado = completar_interpretacao(
            REQUISICAO, INTERPRETACAO, ESTRUTURA
        )
        self.assertEqual(
            resultado["agrupamento"],
            ["rios.nome", "municipios.nome"],
        )
        self.assertEqual(
            resultado["agregacoes"],
            [{"funcao": "AVG", "campo": "medicoes.vazao_m3_s"}],
        )
        self.assertNotIn("agrupamento", INTERPRETACAO)

    def test_nao_cria_campos_quando_ausentes(self):
        resultado = completar_interpretacao(
            {}, INTERPRETACAO, ESTRUTURA
        )
        self.assertNotIn("agrupamento", resultado)
        self.assertNotIn("agregacoes", resultado)

    def test_rejeita_agrupamento_inexistente(self):
        entrada = copy.deepcopy(REQUISICAO)
        entrada["agrupamento"] = ["rios.inexistente"]
        with self.assertRaisesRegex(ValueError, "inválido"):
            completar_interpretacao(entrada, INTERPRETACAO, ESTRUTURA)

    def test_rejeita_agrupamento_nao_projetado(self):
        entrada = copy.deepcopy(REQUISICAO)
        entrada["agrupamento"] = ["medicoes.vazao_m3_s"]
        with self.assertRaisesRegex(ValueError, "não corresponde"):
            completar_interpretacao(entrada, INTERPRETACAO, ESTRUTURA)

    def test_rejeita_agregacao_divergente_da_interpretacao(self):
        entrada = copy.deepcopy(REQUISICAO)
        entrada["agregacoes"][0]["funcao"] = "SUM"
        with self.assertRaisesRegex(ValueError, "não corresponde"):
            completar_interpretacao(entrada, INTERPRETACAO, ESTRUTURA)

    def test_rejeita_funcao_nao_suportada(self):
        entrada = copy.deepcopy(REQUISICAO)
        entrada["agregacoes"][0]["funcao"] = "INVENTADA"
        with self.assertRaisesRegex(ValueError, "não suportada"):
            completar_interpretacao(entrada, INTERPRETACAO, ESTRUTURA)

    def test_rejeita_interpretacao_ambigua(self):
        interpretacao = {**INTERPRETACAO, "status": "ambiguo"}
        with self.assertRaisesRegex(ValueError, "status sucesso"):
            completar_interpretacao(REQUISICAO, interpretacao, ESTRUTURA)

    def test_rejeita_agrupamento_duplicado(self):
        entrada = copy.deepcopy(REQUISICAO)
        entrada["agrupamento"] = ["rios.nome", "rios.nome"]
        with self.assertRaisesRegex(ValueError, "repetidos"):
            completar_interpretacao(entrada, INTERPRETACAO, ESTRUTURA)


if __name__ == "__main__":
    unittest.main()

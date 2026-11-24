"""Conferências de projeções, valores e etapas do executor sem serviços externos."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from sqlglot import exp

from src.agente.avaliacao import avaliar_resultados
from src.agente.sql_generator import SQLGenerationError, SQLGenerator
from src.executar_experimentos import executar_cenarios

CATALOGO = {"tabelas": {"amostra": {"colunas": [{"nome": "id"}, {"nome": "grupo_id"}, {"nome": "valor"}]},
                         "grupo": {"colunas": [{"nome": "id"}, {"nome": "rotulo"}]}},
            "relacionamentos": [{"origem": "amostra.grupo_id", "destino": "grupo.id"}]}


class AgregacaoEAvaliacao(unittest.TestCase):
    def test_cinco_funcoes_com_e_sem_agrupamento(self):
        for funcao in ("AVG", "SUM", "MIN", "MAX", "COUNT"):
            for agrupar in (False, True):
                with self.subTest(funcao=funcao, agrupar=agrupar):
                    agregado = f"{funcao}(amostra.valor)"
                    i = {"campos_solicitados": [agregado],
                         "agregacoes": [{"funcao": funcao, "campo": "amostra.valor"}]}
                    sql = f"SELECT {funcao}(x.valor) AS resultado FROM amostra x"
                    if agrupar:
                        i["campos_solicitados"].append("grupo.rotulo")
                        i["agrupamento"] = ["grupo.rotulo"]
                        i["relacionamentos_necessarios"] = CATALOGO["relacionamentos"]
                        sql = (f"SELECT {funcao}(x.valor) AS resultado, g.rotulo AS grupo "
                               "FROM amostra x JOIN grupo g ON x.grupo_id=g.id GROUP BY g.rotulo")
                    SQLGenerator._validate_query(sql, [], CATALOGO, i)

    def test_recusa_funcao_ou_expressao_fora_do_subconjunto(self):
        for expr in ("STDDEV(amostra.valor)", "AVG(DISTINCT amostra.valor)", "AVG(amostra.valor + 1)"):
            with self.subTest(expr=expr), self.assertRaisesRegex(SQLGenerationError, "não suportada"):
                SQLGenerator._validate_query(f"SELECT {expr} FROM amostra", [], CATALOGO,
                                             {"campos_solicitados": ["AVG(amostra.valor)"]})

    def test_saida_com_chaves_repetidas_e_projecao_a_mais(self):
        i = {"campos_solicitados": ["amostra.id", "grupo.id"],
             "relacionamentos_necessarios": CATALOGO["relacionamentos"]}
        consulta = " FROM amostra a JOIN grupo g ON a.grupo_id=g.id"
        for projecoes, erro in [("a.id, g.id", "mesmo nome"),
                                ("a.id AS amostra, g.id AS grupo, g.id AS outro", "não solicitados")]:
            with self.subTest(projecoes=projecoes), self.assertRaisesRegex(SQLGenerationError, erro):
                SQLGenerator._validate_query("SELECT " + projecoes + consulta, [], CATALOGO, i)
        SQLGenerator._validate_query("SELECT a.id AS amostra, g.id AS grupo" + consulta, [], CATALOGO, i)

    def test_subtotais_nao_solicitados(self):
        i = {"campos_solicitados": ["amostra.grupo_id", "SUM(amostra.valor)"],
             "agrupamento": ["amostra.grupo_id"]}
        sql = "SELECT amostra.grupo_id, SUM(amostra.valor) FROM amostra GROUP BY amostra.grupo_id WITH ROLLUP"
        with self.assertRaisesRegex(SQLGenerationError, "sem subtotais"):
            SQLGenerator._validate_query(sql, [], CATALOGO, i)

    def test_exige_raiz_select_antes_de_avaliar_colunas(self):
        for comando in (exp.Insert(), exp.Update(), exp.Delete(), exp.Drop()):
            with self.subTest(comando=comando.key), self.assertRaisesRegex(SQLGenerationError, "SELECT"):
                SQLGenerator._validar_select(comando, [], CATALOGO, {})

    def test_parametro_booleano_nao_substitui_numero(self):
        i = {"campos_solicitados": ["amostra.valor"],
             "filtros": [{"campo": "amostra.id", "operador": "=", "valor": 1}]}
        with self.assertRaisesRegex(SQLGenerationError, "Filtros solicitados"):
            SQLGenerator._validate_query("SELECT amostra.valor FROM amostra WHERE amostra.id=%s",
                                         [True], CATALOGO, i)

    def test_compara_aliases_de_tabela_coluna_e_agregacao(self):
        kwargs = {"consulta_sql": "SELECT g.rotulo AS grupo, AVG(a.valor) AS media FROM amostra a "
                                  "JOIN grupo g ON a.grupo_id=g.id GROUP BY g.rotulo",
                  "colunas_referencia": {"grupo.rotulo": "nome", "AVG(amostra.valor)": "esperada"}}
        esperado = [{"nome": "A", "esperada": "2.50"}, {"nome": "B", "esperada": None}]
        reais = [{"grupo": "B", "media": None}, {"grupo": "A", "media": Decimal("2.500")}]
        self.assertTrue(avaliar_resultados(reais, esperado, **kwargs)["correto"])
        self.assertFalse(avaliar_resultados(reais, esperado, ordem_importa=True, **kwargs)["correto"])
        kwargs["consulta_sql"] = kwargs["consulta_sql"].replace("AVG(", "MIN(")
        self.assertFalse(avaliar_resultados(reais, esperado, **kwargs)["correto"])

    def test_codigos_textuais_nulos_e_multiplicidade(self):
        for a, b in [(["001"], ["1"]), ([None], [""]), ([True], [1]),
                     ([None, None, "X"], [None, "X", "X"])]:
            with self.subTest(a=a, b=b):
                self.assertFalse(avaliar_resultados([{"v": x} for x in a],
                                                    [{"v": x} for x in b])["correto"])

    def test_decimal_longo_conserva_todos_os_algarismos(self):
        d = "12345678901234567890123456789012345678901234567890"
        self.assertTrue(avaliar_resultados([{"v": Decimal(d)}], [{"v": d}])["correto"])
        self.assertFalse(avaliar_resultados([{"v": Decimal(d)}], [{"v": d[:-1] + "1"}])["correto"])


class RegistroPorEtapa(unittest.TestCase):
    @staticmethod
    def rodar(etapa, referenciado=True):
        segredo = "VALOR_PRIVADO_DA_RODADA"
        r = {"versao": "1.0", "entidade": "amostra", "campos": ["amostra.valor"],
             "filtros": {"amostra.id": segredo}, "agrupamento": [], "agregacoes": []}
        i = {"status": "sucesso", "observacoes": "", "tabelas_identificadas": ["amostra"],
             "campos_solicitados": ["amostra.valor"], "relacionamentos_necessarios": [],
             "filtros": [{"campo": "id", "chave_pedida": "amostra.id", "operador": "=", "valor": segredo}]}
        sql = "SELECT amostra.valor FROM amostra WHERE amostra.id=%s"
        c = {"id": "etapas", "requisicao": r}
        if referenciado:
            c["resultado_esperado"] = [{"valor": 3}]
        modelo, banco = Mock(), Mock()
        modelo.model = "simulado"
        def resposta(msg):
            return SimpleNamespace(content=msg, load_seconds=0, prompt_eval_seconds=0,
                                   generation_seconds=0, prompt_tokens=0, generated_tokens=0)
        consultas = {
            "sintaxe": "SELECT (%s", "validacao_sql": sql.replace("amostra.valor", "amostra.id"),
        }
        consulta = {"consulta_sql": consultas.get(etapa, sql), "parametros": [segredo]}
        texto = "formato inválido" if etapa == "geracao_sql" else json.dumps(consulta)
        modelo.generate.side_effect = ([resposta("formato inválido")] * 2 if etapa == "interpretacao"
                                       else [resposta(json.dumps(i))] + [resposta(texto)] * 3)
        if etapa == "execucao_mysql":
            banco.execute_select.side_effect = RuntimeError(segredo)
        else:
            banco.execute_select.return_value = [{"valor": 4 if etapa == "divergente" else 3}]
        with tempfile.TemporaryDirectory() as td, redirect_stdout(io.StringIO()):
            log = Path(td) / "log.jsonl"
            resumo = executar_cenarios([c], 1, modelo, banco, CATALOGO, log)
            bruto = log.read_text(encoding="utf-8")
        return json.loads(bruto), resumo, bruto

    def test_falhas_tecnicas_tem_etapa_tentativas_e_privacidade(self):
        for etapa, sintaxe in [("interpretacao", None), ("geracao_sql", None),
                               ("sintaxe", False), ("validacao_sql", True), ("execucao_mysql", True)]:
            with self.subTest(etapa=etapa):
                linha, resumo, bruto = self.rodar(etapa)
                self.assertEqual(linha["etapa_falha"], "validacao_sql" if etapa == "sintaxe" else etapa)
                self.assertIs(linha["sql_sintaticamente_valida"], sintaxe)
                self.assertEqual(linha["sql_aprovada"], etapa == "execucao_mysql")
                self.assertFalse(linha["consulta_executada"])
                self.assertEqual(linha["tentativas_interpretacao"], 2 if etapa == "interpretacao" else 1)
                if etapa != "interpretacao":
                    self.assertEqual(linha["tentativas_sql"], 1 if etapa == "execucao_mysql" else 3)
                self.assertGreaterEqual(linha["tempo_total_segundos"], 0)
                self.assertEqual(resumo["falhas"], 1)
                self.assertNotIn("VALOR_PRIVADO", bruto)
                self.assertNotIn("amostra", bruto)

    def test_execucao_distingue_correto_divergente_e_sem_referencia(self):
        for etapa in ("correto", "divergente", "sem_referencia"):
            with self.subTest(etapa=etapa):
                linha, resumo, bruto = self.rodar(etapa, etapa != "sem_referencia")
                self.assertEqual((linha["resultado"], linha["status"]), (etapa, "sucesso"))
                self.assertTrue(linha["consulta_executada"] and linha["sql_aprovada"])
                self.assertEqual(linha["tentativas_sql"], 1)
                self.assertEqual(resumo["falhas"], 0)
                self.assertNotIn("VALOR_PRIVADO", bruto)


if __name__ == "__main__":
    unittest.main()

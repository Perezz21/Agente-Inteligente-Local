"""Regressões de interpretação e caminhos usando um catálogo sintético."""
import copy
import json
import sqlite3
import unittest
from contextlib import closing
from types import SimpleNamespace
from unittest.mock import Mock

from src.agente.fluxo import executar_requisicao
from src.agente.sql_generator import SQLGenerationError, SQLGenerator
from src.agente.validacao_mapeamento import resolver_mapeamento


def tabela(*colunas):
    return {"colunas": [{"nome": c} for c in colunas]}


def fk(origem, destino, nome=None):
    par = {"origem": origem, "destino": destino}
    if nome:
        par["restricao"] = nome
    return par


CATALOGO = {
    "tabelas": {"evento": tabela("id", "data", "unidade_id"),
                "unidade": tabela("id", "setor_id", "nome"),
                "setor": tabela("id", "regiao_id", "nome"),
                "regiao": tabela("id", "nome"),
                "isolada": tabela("id")},
    "relacionamentos": [fk("evento.unidade_id", "unidade.id"),
                        fk("unidade.setor_id", "setor.id"),
                        fk("setor.regiao_id", "regiao.id")],
}


def pedido(*campos, entidade="evento", filtros=None):
    return {"versao": "1.0", "entidade": entidade, "campos": list(campos),
            "filtros": filtros or {}, "agrupamento": [], "agregacoes": []}


def plano(*campos, filtros=(), relacoes=()):
    return {"tabelas_identificadas": ["evento"], "campos_solicitados": list(campos),
            "filtros": list(filtros), "relacionamentos_necessarios": list(relacoes),
            "status": "sucesso", "observacoes": ""}


def filtro(chave, campo="id", valor=101, operador="="):
    return {"chave_pedida": chave, "campo": campo, "valor": valor, "operador": operador}


def resposta(dados):
    return SimpleNamespace(content=json.dumps(dados), load_seconds=0, prompt_eval_seconds=0,
                           generation_seconds=0, prompt_tokens=0, generated_tokens=0)


class Identificadores(unittest.TestCase):
    def test_id_fisico_passa_por_interpretacao_geracao_validacao_e_execucao(self):
        for chave in ("evento.id", "número do evento"):
            with self.subTest(chave=chave):
                r = pedido("data do evento", filtros={chave: 101})
                i = plano("evento.data", filtros=[filtro(chave)])
                sql = "SELECT evento.data FROM evento WHERE evento.id = %s"
                modelo, banco = Mock(), Mock()
                modelo.generate.side_effect = [resposta(i), resposta({"consulta_sql": sql, "parametros": [101]})]
                banco.execute_select.return_value = [{"data": "2026-01-01"}]
                saida = executar_requisicao(r, CATALOGO, modelo, banco)
                self.assertEqual(saida["interpretacao"]["filtros"], [filtro(chave, "evento.id")])
                self.assertEqual(saida["metricas"]["tentativas_interpretacao"], 1)
                self.assertEqual(saida["metricas"]["tentativas_sql"], 1)
                banco.execute_select.assert_called_once_with(consulta=sql, parametros=[101])

    def test_nome_canonico_valor_tipo_operador_e_copia(self):
        r = pedido("evento.data", filtros={"UNIDADE.NOME": "Azul"})
        i = plano("data", filtros=[filtro("UNIDADE.NOME", "nome", "Azul", "!=")])
        original = copy.deepcopy(i)
        obtido = resolver_mapeamento(i, r, CATALOGO)
        self.assertEqual(obtido["filtros"], [filtro("UNIDADE.NOME", "unidade.nome", "Azul", "!=")])
        self.assertEqual(obtido["campos_solicitados"], ["evento.data"])
        self.assertEqual(obtido["relacionamentos_necessarios"], CATALOGO["relacionamentos"][:1])
        self.assertEqual(i, original)

    def test_nao_substitui_coluna_inventada_ou_qualificada_conflitante(self):
        for chave, campo in [("ausente.id", "id"), ("evento.id", "unidade.id"),
                             ("evento.id", "data"), ("rótulo", "inexistente")]:
            with self.subTest(chave=chave, campo=campo), self.assertRaises(ValueError):
                resolver_mapeamento(plano("evento.data", filtros=[filtro(chave, campo)]),
                                    pedido("evento.data", filtros={chave: 101}), CATALOGO)

    def test_id_ambiguo_sem_entidade_nao_pode_ser_escolhido_pelo_modelo(self):
        r = pedido("evento.data", entidade="registros", filtros={"id": 101})
        modelo, banco = Mock(), Mock()
        modelo.generate.side_effect = [
            resposta(plano("evento.data", filtros=[filtro("id", c)])) for c in ("id", "evento.id")]
        with self.assertRaisesRegex(ValueError, "ambíguo.*Após 2 tentativas"):
            executar_requisicao(r, CATALOGO, modelo, banco)
        orientacao = modelo.generate.call_args.kwargs["prompt"].split("anterior foi rejeitada:")[1]
        self.assertIn("evento.id", orientacao)
        self.assertIn("unidade.id", orientacao)
        self.assertIn("ambiguo", orientacao)
        banco.execute_select.assert_not_called()

    def test_recuperacao_escolhe_numero_comercial_quando_essa_coluna_existe(self):
        catalogo = copy.deepcopy(CATALOGO)
        catalogo["tabelas"]["evento"]["colunas"].append({"nome": "numero"})
        chave = "número do evento"
        r = pedido("evento.data", filtros={chave: 101})
        modelo, banco = Mock(), Mock()
        sql = "SELECT evento.data FROM evento WHERE evento.numero = %s"
        modelo.generate.side_effect = [
            resposta(plano("evento.data", filtros=[filtro(chave, "id")])),
            resposta(plano("evento.data", filtros=[filtro(chave, "evento.numero")])),
            resposta({"consulta_sql": sql, "parametros": [101]}),
        ]
        banco.execute_select.return_value = []
        saida = executar_requisicao(r, catalogo, modelo, banco)
        self.assertEqual(saida["metricas"]["tentativas_interpretacao"], 2)
        self.assertIn("evento.numero", modelo.generate.call_args_list[1].kwargs["prompt"])
        banco.execute_select.assert_called_once_with(consulta=sql, parametros=[101])

    def test_id_explicito_com_duas_tabelas_relacionadas_tambem_com_id(self):
        c = copy.deepcopy(CATALOGO)
        c["tabelas"]["evento"]["colunas"].append({"nome": "local"})
        segunda = fk("evento.local", "isolada.id")
        c["relacionamentos"].append(segunda)
        r = pedido("unidade.nome", "isolada.id", filtros={"evento.id": 101})
        i = plano("unidade.nome", "isolada.id", filtros=[filtro("evento.id")])
        canonico = resolver_mapeamento(i, r, c)
        self.assertCountEqual(canonico["relacionamentos_necessarios"], [c["relacionamentos"][0], segunda])
        self.assertEqual(canonico["filtros"][0]["campo"], "evento.id")

    def test_numero_comercial_composto_e_opcoes_ambiguas(self):
        c = copy.deepcopy(CATALOGO)
        chave = "número do evento"
        r = pedido("evento.data", filtros={chave: 101})
        c["tabelas"]["evento"]["colunas"].append({"nome": "numero_evento"})
        with self.assertRaisesRegex(ValueError, "evento.numero_evento"):
            resolver_mapeamento(plano("evento.data", filtros=[filtro(chave)]), r, c)
        c["tabelas"]["evento"]["colunas"][-1:] = [{"nome": "numero_interno"}, {"nome": "numero_externo"}]
        for escolha in ("id", "evento.numero_externo"):
            with self.subTest(escolha=escolha), self.assertRaisesRegex(ValueError, "numero_interno.*numero_externo"):
                resolver_mapeamento(plano("evento.data", filtros=[filtro(chave, escolha)]), r, c)
        chave = "número externo do evento"
        resolvida = resolver_mapeamento(plano("evento.data", filtros=[filtro(chave, "evento.numero_externo")]),
                                        pedido("evento.data", filtros={chave: 101}), c)
        self.assertEqual(resolvida["filtros"][0]["campo"], "evento.numero_externo")

    def test_texto_sem_pista_de_identificador_nao_vira_id(self):
        chave = "cor do evento"
        with self.assertRaisesRegex(ValueError, "não identifica"):
            resolver_mapeamento(plano("evento.data", filtros=[filtro(chave, "evento.id", "azul")]),
                                pedido("evento.data", filtros={chave: "azul"}), CATALOGO)

    def test_termo_do_dominio_pode_ser_um_atributo_da_tabela_de_medicao(self):
        c = copy.deepcopy(CATALOGO)
        c["tabelas"]["evento"]["colunas"].append({"nome": "altura_m"})
        r = pedido("altura da unidade")
        self.assertEqual(resolver_mapeamento(plano("evento.altura_m"), r, c)["campos_solicitados"],
                         ["evento.altura_m"])

    def test_coluna_fisica_explicita_nao_vira_agregacao_global(self):
        with self.assertRaisesRegex(ValueError, "Agregação não solicitada"):
            resolver_mapeamento(plano("COUNT(evento.id)"), pedido("evento.id"), CATALOGO)

    def test_contagem_usa_coluna_do_contrato_mesmo_com_varios_ids(self):
        r = pedido("quantidade de eventos")
        r["agregacoes"] = [{"funcao": "COUNT", "campo": "evento.id"}]
        for campo in ("COUNT(evento.id)", "COUNT(id)"):
            with self.subTest(campo=campo):
                self.assertEqual(resolver_mapeamento(plano(campo), r, CATALOGO)["campos_solicitados"],
                                 ["COUNT(evento.id)"])
        with self.assertRaises(ValueError):
            resolver_mapeamento(plano("COUNT(unidade.id)"), r, CATALOGO)

    def test_esquema_vazio_e_recusado_antes_da_consulta(self):
        modelo, banco = Mock(), Mock()
        modelo.generate.return_value = resposta(plano("evento.data"))
        with self.assertRaisesRegex(ValueError, "sem tabelas visíveis"):
            executar_requisicao(pedido("evento.data"), {}, modelo, banco)
        banco.execute_select.assert_not_called()

    def test_formato_interno_inesperado_nao_altera_a_consulta(self):
        modelo, banco = Mock(), Mock()
        modelo.generate.return_value = resposta({**plano("evento.data"), "agregacoes": []})
        with self.assertRaisesRegex(ValueError, "Formato inesperado"):
            executar_requisicao(pedido("evento.data"), CATALOGO, modelo, banco)
        banco.execute_select.assert_not_called()


class CaminhosDeFK(unittest.TestCase):
    def resolver(self, destino, catalogo=CATALOGO, relacoes=()):
        return resolver_mapeamento(plano("evento.data", destino, relacoes=relacoes),
                                   pedido("evento.data", destino), catalogo)

    def test_uma_tabela_sem_join(self):
        obtido = resolver_mapeamento(plano("evento.data"), pedido("evento.data"), CATALOGO)
        self.assertEqual(obtido["tabelas_identificadas"], ["evento"])
        self.assertEqual(obtido["relacionamentos_necessarios"], [])

    def test_duas_tabelas_uma_fk(self):
        self.assertEqual(self.resolver("unidade.nome")["relacionamentos_necessarios"],
                         CATALOGO["relacionamentos"][:1])

    def test_tres_tabelas_intermediaria_ausente_no_modelo(self):
        obtido = self.resolver("setor.nome")
        self.assertEqual(obtido["tabelas_identificadas"], ["evento", "unidade", "setor"])
        self.assertEqual(obtido["relacionamentos_necessarios"], CATALOGO["relacionamentos"][:2])

    def test_quatro_tabelas_tres_joins_com_aliases(self):
        i = self.resolver("regiao.nome")
        self.assertEqual(i["relacionamentos_necessarios"], CATALOGO["relacionamentos"])
        SQLGenerator._validate_query(
            "SELECT e.data, r.nome FROM evento e JOIN unidade u ON e.unidade_id=u.id "
            "JOIN setor s ON u.setor_id=s.id JOIN regiao r ON s.regiao_id=r.id", [], CATALOGO, i)

    def test_linhas_de_tres_joins_conferidas_em_base_efemera(self):
        # Gabarito calculável a partir das linhas abaixo. LLM simulado,
        # SELECT executado em SQLite; este caso não mede o modelo ou o MySQL.
        with closing(sqlite3.connect(":memory:")) as conexao:
            conexao.row_factory = sqlite3.Row
            conexao.executescript("""
                CREATE TABLE evento (id, data, unidade_id);
                CREATE TABLE unidade (id, setor_id, nome);
                CREATE TABLE setor (id, regiao_id, nome);
                CREATE TABLE regiao (id, nome);
                INSERT INTO evento VALUES (1,'X',10), (2,'X',10), (3,'Y',20);
                INSERT INTO unidade VALUES (10,100,'U'), (20,200,'V');
                INSERT INTO setor VALUES (100,1000,'A'), (200,2000,'B');
                INSERT INTO regiao VALUES (1000,'N'), (2000,'S');
            """)
            modelo, banco = Mock(), Mock()
            sql = ("SELECT e.data, r.nome FROM evento e JOIN unidade u ON u.id=e.unidade_id "
                   "JOIN setor s ON s.id=u.setor_id JOIN regiao r ON r.id=s.regiao_id")
            modelo.generate.side_effect = [resposta(plano("evento.data", "regiao.nome")),
                                          resposta({"consulta_sql": sql, "parametros": []})]
            def consultar(consulta, parametros):
                return [dict(linha) for linha in conexao.execute(consulta, parametros)]
            banco.execute_select.side_effect = consultar
            resultado = executar_requisicao(pedido("evento.data", "regiao.nome"), CATALOGO, modelo, banco)
            self.assertCountEqual(resultado["registros"], [{"data": "X", "nome": "N"},
                                                          {"data": "X", "nome": "N"},
                                                          {"data": "Y", "nome": "S"}])

    def test_nao_liga_tabela_isolada(self):
        with self.assertRaisesRegex(ValueError, "Sem caminho"):
            self.resolver("isolada.id")

    def test_nao_escolhe_atalho_em_ciclo_sem_evidencia(self):
        c = copy.deepcopy(CATALOGO)
        c["tabelas"]["evento"]["colunas"].append({"nome": "area"})
        atalho = fk("evento.area", "regiao.id")
        c["relacionamentos"].append(atalho)
        for sugestao in ([], [atalho], CATALOGO["relacionamentos"]):
            with self.subTest(sugestao=sugestao), self.assertRaisesRegex(ValueError, "ambíguo"):
                self.resolver("regiao.nome", c, sugestao)
        # O JSON pode distinguir o papel mencionando a FK física.
        r = pedido("evento.area", "regiao.nome")
        i = plano("evento.area", "regiao.nome")
        self.assertEqual(resolver_mapeamento(i, r, c)["relacionamentos_necessarios"], [atalho])

    def test_duas_fks_para_a_mesma_tabela_conservam_o_papel(self):
        c = copy.deepcopy(CATALOGO)
        c["tabelas"]["evento"]["colunas"].append({"nome": "unidadeoriginal_id"})
        original = fk("evento.unidadeoriginal_id", "unidade.id")
        c["relacionamentos"].append(original)
        with self.assertRaisesRegex(ValueError, "ambíguo"):
            self.resolver("unidade.nome", c, [original])
        for termo, esperado in [("nome da unidade", c["relacionamentos"][0]),
                                ("nome da unidade original", original)]:
            r = pedido("evento.data", termo)
            i = plano("evento.data", "unidade.nome")
            self.assertEqual(resolver_mapeamento(i, r, c)["relacionamentos_necessarios"], [esperado])

    def test_dois_papeis_distintos_nao_se_resolvem_pelo_comprimento_do_nome(self):
        c = copy.deepcopy(CATALOGO)
        c["tabelas"]["isolada"]["colunas"].append({"nome": "apelido"})
        c["tabelas"]["evento"]["colunas"].extend([{"nome": "autor_id"}, {"nome": "revisor_id"}])
        c["relacionamentos"].extend([fk("evento.autor_id", "isolada.id"),
                                    fk("evento.revisor_id", "isolada.id")])
        with self.assertRaisesRegex(ValueError, "Caminho ambíguo"):
            resolver_mapeamento(plano("evento.data", "isolada.apelido"),
                                pedido("evento.data", "apelido do autor ou revisor"), c)

    def test_ignora_ramo_irrelevante_e_recusa_join_adicional(self):
        with self.assertRaisesRegex(ValueError, "adicional"):
            self.resolver("unidade.nome", relacoes=CATALOGO["relacionamentos"])

    def test_composta_indivisivel_em_toda_a_cadeia(self):
        c = copy.deepcopy(CATALOGO)
        for t in ("evento", "unidade"):
            c["tabelas"][t]["colunas"].append({"nome": "origem"})
        primeiro = c["relacionamentos"][0]
        primeiro["restricao"] = "fk_unidade"
        segundo = fk("evento.origem", "unidade.origem", "fk_unidade")
        c["relacionamentos"].append(segundo)
        with self.assertRaisesRegex(ValueError, "composta incompleta"):
            self.resolver("regiao.nome", c, [primeiro])
        i = self.resolver("regiao.nome", c)
        self.assertCountEqual(i["relacionamentos_necessarios"],
                              [{k: r[k] for k in ("origem", "destino")} for r in c["relacionamentos"]])

    def test_on_que_nao_conecta_a_nova_tabela_e_rejeitado(self):
        i = self.resolver("regiao.nome")
        with self.assertRaisesRegex(SQLGenerationError, "nova tabela"):
            SQLGenerator._validate_query(
                "SELECT e.data, r.nome FROM evento e JOIN unidade u ON e.unidade_id=u.id "
                "JOIN setor s ON e.unidade_id=u.id JOIN regiao r "
                "ON u.setor_id=s.id AND s.regiao_id=r.id", [], CATALOGO, i)


if __name__ == "__main__":
    unittest.main()

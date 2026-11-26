"""Planejamento de consultas agregadas com intermediárias fora da requisição."""
import json
import sqlite3
import unittest
from contextlib import closing
from types import SimpleNamespace
from unittest.mock import Mock

from src.agente.fluxo import executar_requisicao
from src.agente.relacionamentos import planejar_relacoes


def fk(origem, destino):
    return {"origem": origem, "destino": destino}


def tabela(*nomes):
    return {"colunas": [{"nome": n, "chave": "PRI" if n == "id" else ""} for n in nomes]}


def resposta(documento):
    return SimpleNamespace(content=json.dumps(documento), load_seconds=0, prompt_eval_seconds=0,
                           generation_seconds=0, prompt_tokens=0, generated_tokens=0)


class IntermediariasEmCiclos(unittest.TestCase):
    def setUp(self):
        self.caminho = [fk("item_pedido.pedido_id", "pedido.id"),
                        fk("pedido.cliente_id", "cliente.id"),
                        fk("item_pedido.produto_id", "produto.id")]
        self.desvio = [fk("estoque.produto_id", "produto.id"), fk("estoque.loja_id", "loja.id"),
                       fk("pedido.loja_id", "loja.id")]
        self.catalogo = {
            "tabelas": {"item_pedido": tabela("id", "pedido_id", "produto_id", "quantidade"),
                        "pedido": tabela("id", "cliente_id", "loja_id"),
                        "cliente": tabela("id", "nome"), "produto": tabela("id", "nome"),
                        "estoque": tabela("id", "produto_id", "loja_id"), "loja": tabela("id")},
            "relacionamentos": self.caminho + self.desvio,
        }
        self.r = {"entidade": "itens de pedido",
                  "campos": ["nome do produto", "quantidade total comprada"],
                  "filtros": {"nome do cliente": "Ana"}, "agrupamento": ["produto.nome"],
                  "agregacoes": [{"funcao": "SUM", "campo": "item_pedido.quantidade"}]}
        self.ancoras = {"item_pedido", "produto", "cliente"}

    def planejar(self, sugestao=()):
        return planejar_relacoes(self.ancoras, sugestao, self.catalogo, self.r)

    def test_descobre_intermediaria_sem_proposta_e_independe_da_ordem(self):
        for _ in range(2):
            tabelas, pares = self.planejar()
            self.assertEqual(set(tabelas), self.ancoras | {"pedido"})
            self.assertCountEqual(pares, self.caminho)
            self.catalogo["relacionamentos"].reverse()

    def test_consulta_filtra_cliente_e_soma_na_granularidade_do_item(self):
        sql = ("SELECT p.nome AS produto, SUM(i.quantidade) AS total FROM item_pedido i "
               "JOIN produto p ON i.produto_id=p.id JOIN pedido v ON i.pedido_id=v.id "
               "JOIN cliente c ON v.cliente_id=c.id WHERE c.nome=%s GROUP BY p.nome")
        interpretacao = {"tabelas_identificadas": sorted(self.ancoras),
                         "campos_solicitados": ["produto.nome", "SUM(item_pedido.quantidade)"],
                         "filtros": [{"chave_pedida": "nome do cliente", "campo": "cliente.nome",
                                      "operador": "=", "valor": "Ana"}],
                         "relacionamentos_necessarios": [], "status": "sucesso", "observacoes": ""}
        modelo, banco = Mock(), Mock()
        modelo.generate.side_effect = [resposta(interpretacao), resposta({"consulta_sql": sql, "parametros": ["Ana"]})]
        with closing(sqlite3.connect(":memory:")) as db:
            db.executescript("""
                CREATE TABLE cliente(id PRIMARY KEY,nome); INSERT INTO cliente VALUES(1,'Ana'),(2,'Bia');
                CREATE TABLE produto(id PRIMARY KEY,nome); INSERT INTO produto VALUES(7,'P');
                CREATE TABLE loja(id PRIMARY KEY); INSERT INTO loja VALUES(4);
                CREATE TABLE pedido(id PRIMARY KEY,cliente_id,loja_id); INSERT INTO pedido VALUES(10,1,4),(11,2,4);
                CREATE TABLE item_pedido(id PRIMARY KEY,pedido_id,produto_id,quantidade);
                INSERT INTO item_pedido VALUES(21,10,7,2),(22,10,7,3),(23,11,7,8);
                CREATE TABLE estoque(id PRIMARY KEY,produto_id,loja_id); INSERT INTO estoque VALUES(31,7,4),(32,7,4);
            """)
            desvio = sql.replace("JOIN pedido v ON i.pedido_id=v.id",
                                 "JOIN estoque e ON e.produto_id=p.id JOIN loja l ON e.loja_id=l.id "
                                 "JOIN pedido v ON v.loja_id=l.id")
            self.assertEqual(db.execute(desvio.replace("%s", "?"), ["Ana"]).fetchone(), ("P", 26))
            db.row_factory = sqlite3.Row

            def consultar(consulta, parametros):
                return [dict(linha) for linha in db.execute(consulta.replace("%s", "?"), parametros)]

            banco.execute_select.side_effect = consultar
            obtido = executar_requisicao(self.r, self.catalogo, modelo, banco)
        self.assertEqual(obtido["registros"], [{"produto": "P", "total": 5}])
        self.assertCountEqual(obtido["interpretacao"]["relacionamentos_necessarios"], self.caminho)

    def test_cadeia_longa_supera_atalho_inverso(self):
        self.catalogo["tabelas"]["cliente"]["colunas"].append({"nome": "item_id"})
        self.catalogo["relacionamentos"].append(fk("cliente.item_id", "item_pedido.id"))
        self.assertCountEqual(self.planejar()[1], self.caminho)

    def test_duas_rotas_para_pais_nao_sao_desempatadas_pela_sugestao(self):
        self.catalogo["tabelas"]["produto"]["colunas"].append({"nome": "cliente_id"})
        self.catalogo["relacionamentos"].append(fk("produto.cliente_id", "cliente.id"))
        # A origem física no filtro identifica o cliente, mas não o vínculo.
        self.r["filtros"] = {"cliente.nome": "Ana"}
        with self.assertRaisesRegex(ValueError, "ambíguo"):
            self.planejar(self.caminho)

    def test_sugestao_do_desvio_nao_e_aceita(self):
        with self.assertRaises(ValueError):
            self.planejar(self.desvio)

    def test_duas_intermediarias_ocultas_e_fk_composta_completa(self):
        self.catalogo["tabelas"]["origem"] = tabela("id", "cliente_id")
        self.catalogo["tabelas"]["pedido"]["colunas"].extend(
            [{"nome": "origem_id"}, {"nome": "particao", "chave": "PRI"}])
        self.catalogo["tabelas"]["item_pedido"]["colunas"].append({"nome": "particao"})
        fks = self.catalogo["relacionamentos"]
        fks.remove(self.caminho[1])
        fks[0]["restricao"] = "fk_composta"
        composta = dict(fk("item_pedido.particao", "pedido.particao"), restricao="fk_composta")
        adicionais = [fk("pedido.origem_id", "origem.id"), fk("origem.cliente_id", "cliente.id")]
        fks.extend([composta, *adicionais])
        tabelas, pares = self.planejar()
        self.assertEqual(set(tabelas), self.ancoras | {"pedido", "origem"})
        esperadas = [fks[0], self.caminho[2], composta, *adicionais]
        self.assertCountEqual(pares, [{k: p[k] for k in ("origem", "destino")} for p in esperadas])

    def test_duas_intermediarias_concorrentes_independem_da_ordem(self):
        self.catalogo["tabelas"]["registro"] = tabela("id", "cliente_id")
        self.catalogo["tabelas"]["item_pedido"]["colunas"].append({"nome": "registro_id"})
        self.catalogo["relacionamentos"].extend(
            [fk("item_pedido.registro_id", "registro.id"), fk("registro.cliente_id", "cliente.id")])
        for _ in range(2):
            with self.assertRaisesRegex(ValueError, "ambíguo"):
                self.planejar(self.caminho)
            self.catalogo["relacionamentos"].reverse()

    def test_granularidade_incerta_ou_medida_em_outra_tabela(self):
        self.catalogo["tabelas"]["pedido"]["colunas"].append({"nome": "particao", "chave": "PRI"})
        with self.assertRaisesRegex(ValueError, "ambíguo"):
            self.planejar()
        self.catalogo["tabelas"]["pedido"]["colunas"].pop()
        self.r["agregacoes"][0]["campo"] = "produto.id"
        with self.assertRaisesRegex(ValueError, "ambíguo"):
            self.planejar()

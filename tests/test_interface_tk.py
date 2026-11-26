"""Integração do modo gráfico com o contrato, o fluxo compartilhado e o Tk real."""
import json
import threading
import time
import unittest
from contextlib import ExitStack
from tempfile import TemporaryDirectory
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src import main
from src.agente.registro_metricas import registrar_execucao


PEDIDO = {"versao": "1.0", "entidade": "amostra", "campos": ["amostra.nome"],
          "filtros": {"amostra.id": 1}, "agrupamento": [], "agregacoes": []}
PLANO = {"status": "sucesso", "observacoes": "", "tabelas_identificadas": ["amostra"],
         "campos_solicitados": ["amostra.nome"], "relacionamentos_necessarios": [],
         "filtros": [{"chave_pedida": "amostra.id", "campo": "amostra.id", "operador": "=", "valor": 1}]}
SQL = "SELECT amostra.nome FROM amostra WHERE amostra.id = %s"
RESULTADO = {"consulta_sql": SQL, "interpretacao": PLANO, "parametros": [1], "registros": [{"nome": "A"}],
             "total_registros": 1, "metricas": {"tempo_total_segundos": 0.1}}


def mensagem(dados):
    return SimpleNamespace(content=json.dumps(dados), load_seconds=0, prompt_eval_seconds=0,
                           generation_seconds=0, prompt_tokens=1, generated_tokens=1)


class SessaoCompartilhada(unittest.TestCase):
    def test_etapas_acompanham_execucao_e_metricas_sao_gravadas_uma_vez(self):
        eventos = []
        with ExitStack() as stack:
            banco = stack.enter_context(patch("src.main.DatabaseClient")).return_value
            modelo = stack.enter_context(patch("src.main.OllamaModelClient")).return_value
            stack.enter_context(patch("src.main.OllamaConfig.from_environment", return_value=SimpleNamespace(model="local")))
            destino = Path(stack.enter_context(TemporaryDirectory())) / "execucoes.jsonl"
            stack.enter_context(patch("src.main.registrar_execucao",
                                      side_effect=lambda *a, **kw: registrar_execucao(*a, **kw, caminho=destino)))
            modelo.check_connection.return_value = ["local"]
            modelo.generate.side_effect = [
                mensagem(PLANO), mensagem({"consulta_sql": SQL, "parametros": [1]})]
            banco.get_database_structure.return_value = {"tabelas": {"amostra": {"colunas": [
                {"nome": "id"}, {"nome": "nome"}]}}, "relacionamentos": []}
            banco.execute_select.return_value = [{"nome": "A"}]
            resultado, aviso = main.processar(PEDIDO, eventos.append)
            self.assertEqual(resultado["registros"], [{"nome": "A"}])
            self.assertIn(str(destino), aviso)
            linhas = destino.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(linhas), 1)
            self.assertEqual(json.loads(linhas[0])["total_registros"], 1)
        self.assertEqual([e.split(" · ")[0] for e in eventos], [
            "Verificação do modelo Ollama", "Conexão com o banco", "Descoberta da estrutura",
            "Estrutura carregada", "Interpretação da requisição", "Planejamento dos relacionamentos",
            "Geração e validação SQL", "Execução da consulta"])
        banco.execute_select.assert_called_once_with(consulta=SQL, parametros=[1])
        banco.close.assert_called_once()

    def test_falha_de_conexao_nao_anuncia_etapas_posteriores(self):
        with patch("src.main.DatabaseClient") as db, patch("src.main.OllamaModelClient") as modelo, \
                patch("src.main.OllamaConfig.from_environment", return_value=SimpleNamespace(model="local")):
            modelo.return_value.check_connection.return_value = ["local"]
            db.return_value.connect.side_effect = RuntimeError("Conexão recusada")
            etapas = []
            with self.assertRaisesRegex(RuntimeError, "Conexão recusada"):
                main.processar(PEDIDO, etapas.append)
            self.assertEqual(len(etapas), 2)
            db.return_value.close.assert_called_once()

    def test_cli_interativo_continua_disponivel(self):
        with patch("sys.argv", ["main", "--cli"]), patch("src.main.receber_json", side_effect=ValueError("fim")) as ler, \
                patch("builtins.print"):
            main.main()
        ler.assert_called_once()


def fechar_tk(raiz):
    # Cada teste cria um interpretador. Cancele seus temporizadores antes de destruí-lo.
    for tarefa in raiz.tk.call("after", "info"):
        raiz.after_cancel(tarefa)
    raiz.destroy()


class JanelasTk(unittest.TestCase):
    def setUp(self):
        try:
            import tkinter as tk
            from src.interface import janelas
        except ImportError as exc:
            self.skipTest(str(exc))
        try:
            self.raiz = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(str(exc))
        self.ui = janelas
        self.addCleanup(fechar_tk, self.raiz)
        self.servico = Mock(return_value=(RESULTADO, "Métricas registradas"))
        self.app = janelas.Aplicacao(self.raiz, self.servico)
        self.raiz.update()
        self.app.limpar()

    def widgets(self, pai, tipo):
        achados = []
        for filho in pai.winfo_children():
            if isinstance(filho, tipo):
                achados.append(filho)
            achados.extend(self.widgets(filho, tipo))
        return achados

    def aguardar(self, condicao):
        limite = time.monotonic() + 3
        while not condicao() and time.monotonic() < limite:
            self.raiz.update()
            time.sleep(.005)
        self.assertTrue(condicao())

    def test_modo_padrao_abre_interface(self):
        with patch("sys.argv", ["main"]), patch.object(self.ui, "abrir") as abrir:
            main.main()
        abrir.assert_called_once_with(main.processar)

    def test_validacao_formatacao_numeracao_e_limpeza(self):
        for invalido in ("{", '{"entidade":"legado"}'):
            self.app.limpar()
            self.app.editor.insert("1.0", invalido)
            self.app.executar()
            self.assertIsNotNone(self.app.erro)
            self.servico.assert_not_called()
        self.app.limpar()
        self.app.editor.insert("1.0", json.dumps(PEDIDO))
        self.assertEqual(self.app.validar(), PEDIDO)
        self.raiz.update()
        self.assertIn('\n  "versao"', self.app.editor.get("1.0", "end-1c"))
        margem = next(c for c in self.widgets(self.app.editor.master, self.ui.tk.Canvas)
                      if c.master is self.app.editor.master)
        self.assertGreater(len(margem.find_all()), 1)
        self.app.limpar()
        self.assertEqual(self.app.editor.get("1.0", "end-1c"), "")

    def test_thread_abas_copia_e_nova_consulta(self):
        liberar = threading.Event()
        threads = []
        def executar(pedido, sinal):
            threads.append(threading.get_ident())
            sinal("Interpretação da requisição")
            liberar.wait(3)
            return RESULTADO, "Métricas registradas"

        self.servico.side_effect = executar
        self.app.editor.insert("1.0", json.dumps(PEDIDO))
        self.app.executar()
        try:
            self.aguardar(lambda: self.app.estado.get() == "Interpretação da requisição")
            self.app.executar()
            self.assertEqual(self.app.progresso.acao.cget("state"), "disabled")
            self.assertEqual(self.app.acao.cget("text"), "Processando...")
            self.assertNotEqual(threads, [threading.get_ident()])
            self.servico.assert_called_once()
        finally:
            liberar.set()
        self.aguardar(lambda: not self.app.ocupada)
        janela = self.widgets(self.raiz, self.ui.tk.Toplevel)[0]
        abas = self.widgets(janela, self.ui.Abas)[0]
        self.assertEqual(list(abas.paginas),
                         ["Consulta SQL", "Resultados", "Interpretação"])
        grade = self.widgets(janela, self.ui.ttk.Treeview)[0]
        self.assertEqual(grade.item(grade.get_children()[0], "values"), ("A",))
        botoes = {b.cget("text"): b for b in self.widgets(janela, self.ui.Botao)}
        botoes["Copiar SQL"].invoke()
        self.assertEqual(janela.clipboard_get(), "SELECT amostra.nome\nFROM amostra\nWHERE amostra.id = %s")
        botoes["Voltar à requisição"].invoke()
        self.assertFalse(self.widgets(self.raiz, self.ui.tk.Toplevel))
        self.assertEqual(json.loads(self.app.editor.get("1.0", "end-1c")), PEDIDO)

    def test_falha_preserva_editor_e_permite_reexecucao(self):
        self.servico.side_effect = [ValueError("Campo desconhecido"), (RESULTADO, "OK")]
        self.app.editor.insert("1.0", json.dumps(PEDIDO))
        self.app.executar()
        self.aguardar(lambda: not self.app.ocupada)
        self.assertIsNotNone(self.app.erro)
        self.assertEqual(str(self.app.editor.cget("state")), "normal")
        self.app.executar()
        self.aguardar(lambda: not self.app.ocupada)
        self.assertEqual(len(self.widgets(self.raiz, self.ui.tk.Toplevel)), 1)

    def test_tabela_paginada_e_sql_preserva_literais(self):
        sql = "SELECT 'FROM x WHERE y', t.`GROUP BY` FROM t WHERE t.id = %s"
        self.assertEqual(self.ui.formatar_sql(sql),
                         "SELECT 'FROM x WHERE y',\n    t.`GROUP BY`\nFROM t\nWHERE t.id = %s")
        self.ui._tabela(self.raiz, [{"id": i} for i in range(101)])
        grade = self.widgets(self.raiz, self.ui.ttk.Treeview)[0]
        botoes = {b.cget("text"): b for b in self.widgets(self.raiz, self.ui.Botao)}
        self.assertEqual(len(grade.get_children()), 100)
        botoes["Próxima"].invoke()
        self.assertEqual(grade.item(grade.get_children()[0], "values"), ("100",))
        botoes["Anterior"].invoke()
        self.assertEqual(grade.item(grade.get_children()[0], "values"), ("0",))

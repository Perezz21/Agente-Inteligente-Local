"""Comportamento de apresentação e exportação, usando Tk real quando disponível."""
import csv
import json
import threading
import time
import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from test_interface_tk import PEDIDO, RESULTADO


class RefinamentoVisual(unittest.TestCase):
    def setUp(self):
        try:
            from src.interface import janelas
            from src.interface import registros
        except ImportError as exc:
            self.skipTest(str(exc))
        self.ui, self.registros = janelas, registros
        try:
            self.r = janelas.tk.Tk()
        except janelas.tk.TclError as exc:
            self.skipTest(str(exc))
        self.addCleanup(self.r.destroy)
        self.servico = Mock(return_value=(RESULTADO, "OK"))
        self.app = janelas.Aplicacao(self.r, self.servico)
        self.r.update()

    def esperar(self, condicao):
        fim = time.monotonic()+3
        while not condicao() and time.monotonic() < fim:
            self.r.update()
            time.sleep(.005)
        self.assertTrue(condicao())

    def test_modelo_generico_importacao_sintaxe_e_indentacao(self):
        self.assertEqual(self.app.validar(), self.ui.MODELO)
        with TemporaryDirectory() as pasta:
            caminho = Path(pasta)/"entrada.json"
            caminho.write_text(json.dumps(PEDIDO), encoding="utf-8-sig")
            with patch.object(self.ui.filedialog, "askopenfilename", return_value=str(caminho)):
                self.app.importar()
        self.app.formatar()
        self.r.update()
        self.assertTrue(self.app.editor.tag_ranges("chave"))
        self.assertEqual(self.app.validar(), PEDIDO)
        self.app.trocar_texto("{")
        self.app.editor.mark_set("insert", "end-1c")
        self.ui.indentar(Mock(widget=self.app.editor))
        self.assertEqual(self.app.editor.get("1.0", "end-1c"), "{\n  ")
        self.app.validar()
        self.assertTrue(self.app.editor.tag_ranges("falha"))
        self.servico.assert_not_called()

    def test_progresso_retentativa_conexao_e_falha_sem_segredos(self):
        sair = threading.Event()
        def servico(_, notificar):
            for e in ("Verificação do modelo Ollama", "Conexão com o banco", "Descoberta da estrutura",
                      "Estrutura carregada", "Interpretação da requisição", "Planejamento dos relacionamentos",
                      "Interpretação da requisição · tentativa 2"):
                notificar(e)
            sair.wait(3)
            raise RuntimeError("password=NAO_MOSTRAR")
        self.servico.side_effect = servico
        self.app.executar()
        try:
            self.esperar(lambda: self.app.progresso.atual == 4)
            est = self.app.progresso.estados
            self.assertEqual(est[4]["text"], "Em processamento")
            self.assertEqual(est[5]["text"], "Pendente")
            self.assertEqual(self.app.conexao.get(), "Conectada")
            self.esperar(lambda: self.app.progresso.tempo["text"] != "00:00")
        finally:
            sair.set()
        self.esperar(lambda: not self.app.ocupada)
        self.assertEqual(est[4]["text"], "Falha")
        self.assertEqual(self.app.conexao.get(), "Sessão encerrada")
        labels = [c.cget("text") for c in self.app.erro.winfo_children() if isinstance(c, self.ui.ttk.Label)]
        self.assertNotIn("NAO_MOSTRAR", " ".join(labels))

    def test_pesquisa_e_ordenacao_local_paginada(self):
        linhas = [{"id": i, "grupo": "A" if i%2 else "B"} for i in range(3500)]
        janela = self.ui.tk.Toplevel(self.r)
        tabela = self.registros.Tabela(janela, linhas)
        tabela.busca.set("b")
        tabela.ordenar("id")
        tabela.ordenar("id")
        self.esperar(lambda: len(tabela.linhas) == 1750)
        self.assertEqual(tabela.linhas[0]["id"], 3498)
        self.assertEqual(len(tabela.grade.get_children()), 100)
        self.assertEqual(linhas[0]["id"], 0)
        tabela.busca.set("inexistente")
        self.esperar(lambda: not tabela.linhas)
        self.assertIn("Nenhum", tabela.info["text"])
        self.servico.assert_not_called()

    def test_exportacao_preserva_registros_e_parametros(self):
        dados = [{"nome": 'A,"á"\nB', "valor": Decimal("3.14"), "opcional": None}]
        with TemporaryDirectory() as pasta:
            for ext in ("csv", "json"):
                arquivo = Path(pasta)/("resultado."+ext)
                self.registros.gravar(arquivo, dados, ext)
                with arquivo.open(encoding="utf-8-sig", newline="") as f:
                    linhas = list(csv.DictReader(f)) if ext == "csv" else json.load(f)
                self.assertEqual(linhas[0]["nome"], dados[0]["nome"])
                self.assertEqual(linhas[0]["valor"], "3.14")
            self.registros.gravar(arquivo, [], "json")
            self.assertEqual(json.loads(arquivo.read_text()), [])

    def test_redimensionar_inicio_e_resultado_vazio(self):
        for geometria in ("1366x768", "1920x1080", "820x580", "1152x700"):
            self.r.geometry(geometria)
            self.r.update()
            self.assertGreater(self.app.editor.winfo_width(), 300)
            self.assertGreater(self.app.editor.winfo_height(), 80)
            self.assertTrue(self.app.acao.winfo_ismapped())
        self.app.anterior = PEDIDO
        self.app.resultados(dict(RESULTADO, registros=[], total_registros=0), "OK")
        janela = next(c for c in self.r.winfo_children() if isinstance(c, self.ui.tk.Toplevel))
        for g in ("1366x768", "1920x1080", "820x580"):
            janela.geometry(g)
            self.r.update()
            self.assertEqual(janela.state(), "normal")

    def test_acoes_das_abas_e_nova_requisicao(self):
        def descendentes(pai):
            for filho in pai.winfo_children():
                yield filho
                yield from descendentes(filho)

        def botao(pai, nome):
            return next(b for b in descendentes(pai) if isinstance(b, self.ui.ttk.Button) and b["text"] == nome)

        self.app.trocar_texto(json.dumps(PEDIDO))
        self.app.executar()
        self.esperar(lambda: not self.app.ocupada)
        janela = next(w for w in self.r.winfo_children() if isinstance(w, self.ui.tk.Toplevel))
        abas = next(w for w in descendentes(janela) if isinstance(w, self.ui.ttk.Notebook))
        botao(janela, "Copiar parâmetros").invoke()
        self.assertEqual(json.loads(janela.clipboard_get()), [1])
        with TemporaryDirectory() as pasta:
            caminho = Path(pasta)/"consulta.sql"
            with patch.object(self.ui.filedialog, "asksaveasfilename", return_value=str(caminho)):
                botao(janela, "Salvar SQL").invoke()
            self.assertEqual(caminho.read_text(), RESULTADO["consulta_sql"])
            saida = Path(pasta)/"resultado.json"
            with patch.object(self.ui, "escolher_exportacao", return_value=str(saida)):
                botao(janela, "Exportar resultados").invoke()
            self.esperar(lambda: str(botao(janela, "Exportar resultados")["state"]) == "normal")
            self.assertEqual(json.loads(saida.read_text()), RESULTADO["registros"])
        abas.select(2)
        botao(janela, "Relacionamentos").invoke()
        secao = janela.nametowidget(abas.select())
        self.assertTrue(any(isinstance(w, self.ui.tk.Canvas) for w in descendentes(secao)))
        botao(janela, "JSON completo").invoke()
        texto = next(w for w in descendentes(secao) if isinstance(w, self.ui.tk.Text))
        self.assertEqual(json.loads(texto.get("1.0", "end-1c")), RESULTADO["interpretacao"])
        botao(janela, "Nova consulta").invoke()
        self.assertEqual(json.loads(self.app.editor.get("1.0","end-1c")), self.ui.MODELO)
        self.servico.assert_called_once()

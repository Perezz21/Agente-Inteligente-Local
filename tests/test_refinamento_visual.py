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

from test_interface_tk import PEDIDO, RESULTADO, fechar_tk


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
        self.addCleanup(fechar_tk, self.r)
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
        self.assertFalse(tabela.prox.winfo_manager())
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
            return next(b for b in descendentes(pai) if isinstance(b, self.ui.Botao) and b.cget("text") == nome)

        self.app.trocar_texto(json.dumps(PEDIDO))
        self.app.executar()
        self.esperar(lambda: not self.app.ocupada)
        janela = next(w for w in self.r.winfo_children() if isinstance(w, self.ui.tk.Toplevel))
        abas = next(w for w in descendentes(janela) if isinstance(w, self.ui.Abas))
        botao(janela, "Copiar parâmetros").invoke()
        self.assertEqual(json.loads(janela.clipboard_get()), [1])
        with TemporaryDirectory() as pasta:
            caminho = Path(pasta)/"consulta.sql"
            with patch.object(self.ui.filedialog, "asksaveasfilename", return_value=str(caminho)):
                botao(janela, "Salvar SQL").invoke()
            self.assertEqual(caminho.read_text(), RESULTADO["consulta_sql"])
            abas.selecionar("Resultados")
            saida = Path(pasta)/"resultado.json"
            with patch.object(self.ui, "escolher_exportacao", return_value=str(saida)):
                botao(janela, "Exportar resultados").invoke()
            self.esperar(lambda: str(botao(janela, "Exportar resultados").cget("state")) == "normal")
            self.assertEqual(json.loads(saida.read_text()), RESULTADO["registros"])
        abas.selecionar("Interpretação")
        secao = abas.paginas["Interpretação"]
        self.assertTrue(any(isinstance(w, self.ui.ttk.Label) and "não precisou" in w.cget("text")
                            for w in descendentes(secao)))
        botao(janela, "Ver interpretação completa").invoke()
        auxiliar = next(w for w in descendentes(janela) if isinstance(w, self.ui.tk.Toplevel))
        texto = next(w for w in descendentes(auxiliar) if isinstance(w, self.ui.tk.Text))
        self.assertEqual(json.loads(texto.get("1.0", "end-1c")), RESULTADO["interpretacao"])
        auxiliar.destroy()
        botao(janela, "Detalhes técnicos").invoke()
        tecnico = next(w for w in descendentes(janela) if isinstance(w, self.ui.tk.Toplevel))
        self.assertTrue(any(isinstance(w, self.ui.ttk.Label) and w.cget("text") == "Tentativas SQL"
                            for w in descendentes(tecnico)))
        tecnico.destroy()
        botao(janela, "Nova consulta").invoke()
        self.assertEqual(json.loads(self.app.editor.get("1.0","end-1c")), self.ui.MODELO)
        self.servico.assert_called_once()

    def test_grafo_com_varias_chaves_e_autorrelacao(self):
        from src.interface.analise import desenhar_grafo
        canvas = self.ui.tk.Canvas(self.r, width=700, height=320)
        canvas.pack()
        relacoes = [{"origem": "amostra.origem_id", "destino": "ponto.id"},
                    {"origem": "amostra.destino_id", "destino": "ponto.id"},
                    {"origem": "ponto.grupo_id", "destino": "grupo.id"},
                    {"origem": "grupo.pai_id", "destino": "grupo.id"}]
        desenhar_grafo(canvas, relacoes, ["ponto", "amostra", "grupo"], "amostras")
        self.r.update_idletasks()
        nos = canvas.find_withtag("no")
        self.assertEqual(len(nos), 3)
        self.assertEqual(sum(canvas.itemcget(n, "outline") == self.ui.DESTAQUE for n in nos), 1)
        self.assertEqual(len(canvas.find_withtag("aresta")), len(relacoes))
        self.assertCountEqual([canvas.itemcget(item, "text") for item in canvas.find_withtag("rotulo_fk")],
                              ["origem_id", "id", "destino_id", "id", "grupo_id", "id", "pai_id", "id"])

    def test_escalas_paginacao_condicional_e_estabilidade_das_abas(self):
        import customtkinter as ctk
        self.app.resultados(dict(RESULTADO, parametros=[], registros=[], total_registros=0), "OK")
        janela = next(w for w in self.r.winfo_children() if isinstance(w, self.ui.tk.Toplevel))
        def filhos(pai):
            for w in pai.winfo_children():
                yield w
                yield from filhos(w)
        abas = next(w for w in filhos(janela) if isinstance(w, self.ui.Abas))
        self.assertEqual(abas.atual, "Consulta SQL")
        sql = list(filhos(abas.paginas[abas.atual]))
        self.assertTrue(any(isinstance(w, self.ui.ttk.Label) and w.cget("text") == "Nenhum parâmetro utilizado." for w in sql))
        self.assertFalse(any(isinstance(w, self.ui.Botao) and w.cget("text") == "Copiar parâmetros" for w in sql))
        escala_tk = self.r.tk.call("tk", "scaling")
        self.addCleanup(self.r.tk.call, "tk", "scaling", escala_tk)
        self.addCleanup(ctk.set_widget_scaling, 1)
        for escala in (1, 1.25, 1.5):
            self.r.tk.call("tk", "scaling", escala*96/72)
            ctk.set_widget_scaling(escala)
            for tamanho in ("1366x768", "1920x1080"):
                janela.geometry(tamanho)
                self.r.update()
                posicoes = [b.winfo_geometry() for b in abas.botoes.values()]
                for nome in abas.paginas:
                    abas.selecionar(nome)
                    self.r.update()
                    self.assertEqual([b.winfo_geometry() for b in abas.botoes.values()], posicoes)
                    self.assertGreater(abas.paginas[nome].winfo_height(), 100)
                    if nome == "Resultados":
                        botoes = {b.cget("text"): b for b in filhos(abas.paginas[nome]) if isinstance(b, self.ui.Botao)}
                        self.assertTrue(botoes["Exportar resultados"].winfo_ismapped())
                        self.assertFalse(botoes["Próxima"].winfo_ismapped())

    def test_interacao_mouse_teclado_e_estado_desabilitado(self):
        from src.interface.visual import DESTAQUE_ATIVO, SINTAXE
        comando = Mock()
        b = self.ui.Botao(self.r, "Ação", comando)
        b.pack(side="bottom", before=self.app.quadro)
        self.r.update()
        self.r.focus_force()
        self.ui.tk.Misc.focus_set(b)
        self.r.update()
        self.assertEqual(b.cget("border_color"), SINTAXE)
        b.event_generate("<Return>")
        comando.assert_called_once()
        alvo = next(w for w in b.winfo_children() if isinstance(w, self.ui.tk.Canvas))
        alvo.event_generate("<Enter>")
        alvo.event_generate("<ButtonPress-1>", x=10, y=10)
        self.assertEqual(b.cget("fg_color"), DESTAQUE_ATIVO)
        alvo.event_generate("<ButtonRelease-1>", x=10, y=10)
        self.assertEqual(comando.call_count, 2)
        self.assertEqual(b.cget("fg_color"), b.normal)
        b.configure(state="disabled")
        b.invoke()
        self.assertEqual(comando.call_count, 2)

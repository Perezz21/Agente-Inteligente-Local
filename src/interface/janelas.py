"""Interface Tk do agente. Somente a thread do mainloop acessa os widgets."""
import json
import os
import queue
import threading
import tkinter as tk
from tkinter import font, messagebox, ttk

from sqlglot import Dialect
from sqlglot.errors import TokenError

from src.agente.config import OllamaConfig
from src.agente.entrada import interpretar_json


FUNDO, PAINEL, BORDA = "#101923", "#192532", "#334557"
TEXTO, SUAVE, DESTAQUE = "#e6eef5", "#a5b8c9", "#78dfcf"
CLAUSULAS = {"FROM", "WHERE", "GROUP_BY", "ORDER_BY", "LIMIT", "HAVING",
             "JOIN", "LEFT", "RIGHT", "INNER", "CROSS", "AND"}
PALAVRAS_SQL = CLAUSULAS | {"SELECT", "ON", "AS", "OR", "DISTINCT", "OUTER"}


def formatar_sql(sql):
    """Insere quebras entre tokens, preservando identificadores, literais e %s."""
    try:
        tokens = Dialect.get_or_raise("mysql").tokenize(sql)
    except TokenError:
        return sql
    partes = []
    anterior = 0
    tipo_anterior = ""
    for token in tokens:
        separador = sql[anterior:token.start]
        tipo = token.token_type.name
        if tipo in CLAUSULAS and separador.isspace():
            if tipo != "JOIN" or tipo_anterior not in {"INNER", "LEFT", "RIGHT", "CROSS", "OUTER"}:
                separador = "\n"
        partes.extend((separador, sql[token.start:token.end + 1]))
        anterior = token.end + 1
        tipo_anterior = tipo
    return "".join(partes) + sql[anterior:]


def _estilo(raiz):
    font.nametofont("TkFixedFont", root=raiz).configure(size=11)
    estilo = ttk.Style(raiz)
    estilo.theme_use("clam")
    raiz.configure(bg=FUNDO)
    estilo.configure(".", background=FUNDO, foreground=TEXTO, fieldbackground=PAINEL,
                     bordercolor=BORDA, lightcolor=BORDA, darkcolor=BORDA)
    familia = font.nametofont("TkDefaultFont", root=raiz).actual("family")
    estilo.configure("Titulo.TLabel", font=(familia, 21, "bold"))
    estilo.configure("Suave.TLabel", foreground=SUAVE)
    estilo.configure("TButton", padding=(14, 8), background=PAINEL)
    estilo.map("TButton", background=[("active", BORDA)], foreground=[("disabled", SUAVE)])
    estilo.configure("Executar.TButton", background=DESTAQUE, foreground=FUNDO)
    estilo.map("Executar.TButton", background=[("disabled", PAINEL), ("active", "#a3ecdf")],
               foreground=[("disabled", SUAVE)])
    estilo.configure("TNotebook.Tab", padding=(12, 8), background=PAINEL)
    estilo.map("TNotebook.Tab", foreground=[("selected", DESTAQUE)], background=[("selected", FUNDO)])
    estilo.configure("Treeview", rowheight=28)
    estilo.configure("Treeview.Heading", background=BORDA, padding=5)
    estilo.configure("TScrollbar", background=BORDA, troughcolor=PAINEL)
    estilo.map("TScrollbar", background=[("disabled", PAINEL), ("active", "#506579")])


def _area(pai, numerar=False):
    quadro = ttk.Frame(pai)
    quadro.pack(fill="both", expand=True)
    quadro.rowconfigure(0, weight=1)
    quadro.columnconfigure(1, weight=1)
    texto = tk.Text(quadro, bg=PAINEL, fg=TEXTO, insertbackground=DESTAQUE, selectbackground="#315569",
                    font="TkFixedFont", wrap="none", borderwidth=0, padx=12, pady=10,
                    width=1, height=2, undo=numerar)
    texto.grid(row=0, column=1, sticky="nsew")
    vertical = ttk.Scrollbar(quadro, command=texto.yview)
    horizontal = ttk.Scrollbar(quadro, orient="horizontal", command=texto.xview)
    vertical.grid(row=0, column=2, sticky="ns")
    horizontal.grid(row=1, column=1, sticky="ew")
    texto.configure(xscrollcommand=horizontal.set, yscrollcommand=vertical.set)
    if numerar:
        margem = tk.Canvas(quadro, width=54, bg=FUNDO, highlightthickness=0)
        margem.grid(row=0, column=0, sticky="ns")

        def desenhar(*_):
            margem.delete("all")
            linha = int(texto.index("@0,0").split(".")[0])
            while (info := texto.dlineinfo(f"{linha}.0")) is not None:
                margem.create_text(48, info[1], text=str(linha), anchor="ne", fill=SUAVE, font="TkFixedFont")
                linha += 1
                if linha > int(texto.index("end-1c").split(".")[0]):
                    break

        def rolagem(inicio, fim):
            vertical.set(inicio, fim)
            desenhar()

        texto.configure(yscrollcommand=rolagem)
        texto.bind("<Configure>", desenhar)
        def modificado(_):
            if texto.edit_modified():
                texto.edit_modified(False)
                desenhar()

        texto.bind("<<Modified>>", modificado)
    return texto


def _leitura(pai, conteudo, sql=False):
    texto = _area(pai)
    texto.insert("1.0", conteudo)
    if sql:
        texto.tag_configure("sql", foreground=DESTAQUE)
        try:
            tokens = Dialect.get_or_raise("mysql").tokenize(conteudo)
        except TokenError:
            tokens = []
        for token in tokens:
            if token.token_type.name in PALAVRAS_SQL:
                texto.tag_add("sql", f"1.0+{token.start}c", f"1.0+{token.end + 1}c")
    texto.configure(state="disabled")
    return texto


def _json(valor):
    return json.dumps(valor, ensure_ascii=False, indent=2, default=str)


def _tabela(pai, registros):
    if not registros:
        ttk.Label(pai, text="Nenhum registro encontrado.").pack(anchor="w")
        return
    colunas = list(registros[0])
    quadro = ttk.Frame(pai)
    quadro.pack(fill="both", expand=True)
    quadro.rowconfigure(0, weight=1)
    quadro.columnconfigure(0, weight=1)
    ids = [f"c{i}" for i in range(len(colunas))]
    tabela = ttk.Treeview(quadro, columns=ids, show="headings")
    fonte = font.nametofont("TkDefaultFont", root=pai)
    for identificador, nome in zip(ids, colunas):
        tabela.heading(identificador, text=nome)
        amostra = [nome, *(str(linha[nome])[:80] for linha in registros[:20])]
        largura = max(120, min(420, max(map(fonte.measure, amostra)) + 28))
        tabela.column(identificador, width=largura, minwidth=largura, stretch=True)
    tabela.grid(row=0, column=0, sticky="nsew")
    vertical = ttk.Scrollbar(quadro, command=tabela.yview)
    horizontal = ttk.Scrollbar(quadro, orient="horizontal", command=tabela.xview)
    vertical.grid(row=0, column=1, sticky="ns")
    horizontal.grid(row=1, column=0, sticky="ew")
    tabela.configure(xscrollcommand=horizontal.set, yscrollcommand=vertical.set)
    controles = ttk.Frame(pai)
    controles.pack(fill="x", pady=(8, 0))
    pagina = 0

    def mostrar(indice):
        nonlocal pagina
        pagina = indice
        tabela.delete(*tabela.get_children())
        for linha in registros[indice:indice + 100]:
            tabela.insert("", "end", values=["NULL" if linha[c] is None else str(linha[c]) for c in colunas])
        anterior.configure(state="normal" if indice else "disabled")
        proxima.configure(state="normal" if indice + 100 < len(registros) else "disabled")
        posicao.configure(text=f"{indice + 1}–{min(indice + 100, len(registros))} de {len(registros)}")

    anterior = ttk.Button(controles, text="Anterior", command=lambda: mostrar(pagina - 100))
    proxima = ttk.Button(controles, text="Próxima", command=lambda: mostrar(pagina + 100))
    posicao = ttk.Label(controles, style="Suave.TLabel")
    if len(registros) > 100:
        anterior.pack(side="left")
        posicao.pack(side="left", padx=12)
        proxima.pack(side="left")
    mostrar(0)


class Aplicacao:
    def __init__(self, raiz, processar):
        self.raiz = raiz
        self.processar = processar
        self.fila = queue.Queue()
        self.ocupada = False
        self.fechando = False
        raiz.title("Agente Inteligente Local")
        raiz.geometry("940x680")
        raiz.minsize(580, 420)
        _estilo(raiz)
        quadro = ttk.Frame(raiz, padding=24)
        quadro.pack(fill="both", expand=True)
        ttk.Label(quadro, text="Agente Inteligente Local", style="Titulo.TLabel").pack(anchor="w")
        config = OllamaConfig.from_environment()
        self.conexao = (f"{os.getenv('MYSQL_DATABASE', 'agente_experimental')}    ·    "
                        f"Modelo: {config.model or 'não configurado'}")
        ttk.Label(quadro, text=f"Banco configurado: {self.conexao}", style="Suave.TLabel").pack(anchor="w", pady=(4, 22))
        ttk.Label(quadro, text="Requisição JSON  ·  v1.0").pack(anchor="w", pady=(0, 8))
        self.editor = _area(quadro, numerar=True)
        self.estado = tk.StringVar(value="Insira a requisição JSON.")
        ttk.Label(quadro, textvariable=self.estado, style="Suave.TLabel").pack(anchor="w", pady=10)
        acoes = ttk.Frame(quadro)
        acoes.pack(fill="x")
        self.botoes = []
        for rotulo, funcao, lado in [("Executar consulta", self.executar, "right"),
                                     ("Validar JSON", self.validar, "left"), ("Limpar", self.limpar, "left")]:
            botao = ttk.Button(acoes, text=rotulo, command=funcao,
                               style="Executar.TButton" if lado == "right" else "TButton")
            botao.pack(side=lado, padx=(0, 8) if lado == "left" else 0)
            self.botoes.append(botao)
        raiz.protocol("WM_DELETE_WINDOW", self.encerrar)
        self.editor.focus_set()

    def limpar(self):
        self.editor.delete("1.0", "end")
        self.estado.set("Insira a requisição JSON.")
        self.editor.focus_set()

    def validar(self):
        try:
            pedido = interpretar_json(self.editor.get("1.0", "end-1c"))
        except ValueError as erro:
            self.estado.set("Corrija a requisição e valide novamente.")
            messagebox.showerror("Requisição inválida", str(erro), parent=self.raiz)
            self.editor.focus_set()
            return None
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", _json(pedido))
        self.estado.set("JSON válido pelo contrato v1.0.")
        return pedido

    def _ocupacao(self, ativa):
        self.ocupada = ativa
        estado = "disabled" if ativa else "normal"
        self.editor.configure(state=estado)
        for botao in self.botoes:
            botao.configure(state=estado)

    def executar(self):
        if self.ocupada:
            return
        pedido = self.validar()
        if pedido is None:
            return
        self._ocupacao(True)

        def trabalhar():
            try:
                resultado = self.processar(pedido, lambda etapa: self.fila.put(("etapa", etapa)))
                self.fila.put(("resultado", resultado))
            except Exception as erro:
                self.fila.put(("erro", str(erro) or type(erro).__name__))

        threading.Thread(target=trabalhar, name="consulta-local").start()
        self.raiz.after(20, self._ler_eventos)

    def _ler_eventos(self):
        while not self.fila.empty():
            tipo, valor = self.fila.get_nowait()
            if tipo == "etapa":
                if not self.fechando:
                    self.estado.set(valor)
                continue
            self._ocupacao(False)
            if self.fechando:
                self.raiz.destroy()
            elif tipo == "erro":
                self.estado.set(f"Falha durante a consulta · {self.estado.get()}")
                messagebox.showerror("Falha na consulta", valor, parent=self.raiz)
                self.editor.focus_set()
            else:
                self.estado.set("Consulta concluída.")
                self.resultados(*valor)
            return
        self.raiz.after(40, self._ler_eventos)

    def encerrar(self):
        if self.ocupada:
            self.fechando = True
            self.estado.set("Encerrando após a consulta atual…")
        else:
            self.raiz.destroy()

    def resultados(self, resposta, aviso):
        janela = tk.Toplevel(self.raiz)
        janela.title("Resultados · Agente Inteligente Local")
        janela.geometry(self.raiz.geometry())
        janela.minsize(580, 420)
        self.raiz.withdraw()
        quadro = ttk.Frame(janela, padding=24)
        quadro.pack(fill="both", expand=True)
        ttk.Label(quadro, text="Resultado da consulta", style="Titulo.TLabel").pack(anchor="w")
        total = resposta["total_registros"]
        unidade = "registro recuperado" if total == 1 else "registros recuperados"
        ttk.Label(quadro, text=f"{total} {unidade}    ·    Banco: {self.conexao}",
                  style="Suave.TLabel").pack(anchor="w", pady=(4, 18))
        abas = ttk.Notebook(quadro)
        abas.pack(fill="both", expand=True)
        secoes = []
        for nome in ("Consulta SQL", "Resultados", "Interpretação", "Métricas"):
            secao = ttk.Frame(abas, padding=12)
            abas.add(secao, text=nome)
            secoes.append(secao)
        sql, tabela, interpretacao, metricas = secoes
        consulta = formatar_sql(resposta["consulta_sql"])

        def copiar():
            janela.clipboard_clear()
            janela.clipboard_append(consulta)
            copiar_btn.configure(text="SQL copiada")

        copiar_btn = ttk.Button(sql, text="Copiar SQL", command=copiar)
        copiar_btn.pack(anchor="e", pady=(0, 8))
        suporte = ttk.Panedwindow(sql, orient="vertical")
        suporte.pack(fill="both", expand=True)
        for titulo, conteudo, destaque, peso in [
            ("SQL", consulta, True, 3), ("Parâmetros", _json(resposta["parametros"]), False, 1)
        ]:
            bloco = ttk.Frame(suporte)
            suporte.add(bloco, weight=peso)
            ttk.Label(bloco, text=titulo).pack(anchor="w", pady=4)
            _leitura(bloco, conteudo, destaque)
        _tabela(tabela, resposta["registros"])
        _leitura(interpretacao, _json(resposta["interpretacao"]))
        ttk.Label(metricas, text=aviso, wraplength=520, style="Suave.TLabel").pack(anchor="w", pady=(0, 8))
        linhas_metricas = []
        for nome, valor in resposta["metricas"].items():
            itens = valor.items() if isinstance(valor, dict) else [(nome, valor)]
            for chave, dado in itens:
                rotulo = chave.removesuffix("_segundos").replace("_", " ").capitalize()
                if isinstance(valor, dict):
                    rotulo = f"{nome.capitalize()} · {rotulo}"
                exibido = "—" if dado is None else str(dado)
                if chave.endswith("_segundos") and dado is not None:
                    exibido = f"{dado:.4f} s"
                linhas_metricas.append({"Métrica": rotulo, "Valor": exibido})
        _tabela(metricas, linhas_metricas)

        def nova():
            janela.destroy()
            self.raiz.deiconify()
            self.editor.focus_set()

        rodape = ttk.Frame(quadro)
        rodape.pack(fill="x", pady=(12, 0))
        ttk.Button(rodape, text="Encerrar", command=self.encerrar).pack(side="left")
        ttk.Button(rodape, text="Nova consulta", command=nova, style="Executar.TButton").pack(side="right")
        janela.protocol("WM_DELETE_WINDOW", nova)
        janela.focus_set()


def abrir(processar):
    try:
        raiz = tk.Tk()
    except tk.TclError as erro:
        raise SystemExit("Não foi possível abrir a janela Tk. Verifique o ambiente gráfico ou use --cli.") from erro
    Aplicacao(raiz, processar)
    raiz.mainloop()

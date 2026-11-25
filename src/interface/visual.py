"""Identidade visual, cartões e componentes compartilhados das janelas."""
import tkinter as tk
from tkinter import font, ttk

FUNDO, PAINEL, BORDA = "#101923", "#192532", "#334557"
TEXTO, SUAVE, DESTAQUE = "#E6EEF5", "#A5B8C9", "#78DFCF"
ERRO, AVISO = "#FFABAB", "#E9C88B"
ESPACO = 16


def estilo(raiz):
    familia = font.nametofont("TkDefaultFont", root=raiz).actual("family")
    font.nametofont("TkFixedFont", root=raiz).configure(size=11)
    s = ttk.Style(raiz)
    s.theme_use("clam")
    raiz.configure(bg=FUNDO)
    s.configure(".", background=FUNDO, foreground=TEXTO, fieldbackground=PAINEL,
                bordercolor=BORDA, lightcolor=BORDA, darkcolor=BORDA, focuscolor=DESTAQUE)
    for nome, tamanho, peso, cor in [
        ("Titulo", 22, "bold", TEXTO), ("Secao", 13, "bold", TEXTO),
        ("Valor", 16, "bold", TEXTO), ("Suave", 10, "normal", SUAVE),
        ("Legenda", 9, "bold", SUAVE), ("Sucesso", 10, "bold", DESTAQUE),
        ("Erro", 11, "bold", ERRO), ("Aviso", 10, "normal", AVISO)
    ]:
        s.configure(nome + ".TLabel", font=(familia, tamanho, peso), foreground=cor)
    s.configure("TButton", padding=(12, 7), background=PAINEL)
    s.map("TButton", background=[("pressed", FUNDO), ("active", BORDA)], foreground=[("disabled", SUAVE)])
    s.configure("Executar.TButton", background=DESTAQUE, foreground=FUNDO, font=(familia, 10, "bold"))
    s.map("Executar.TButton", background=[("disabled", BORDA), ("pressed", SUAVE), ("active", "#9DEBDD")],
          foreground=[("disabled", SUAVE)])
    s.configure("TNotebook", borderwidth=0)
    s.configure("TNotebook.Tab", padding=(17, 9), background=FUNDO, foreground=SUAVE)
    s.map("TNotebook.Tab", foreground=[("selected", DESTAQUE)], background=[("selected", PAINEL)])
    s.configure("Treeview", rowheight=font.nametofont("TkDefaultFont").metrics("linespace") + 12)
    s.configure("Treeview.Heading", background=BORDA, padding=6)
    s.map("Treeview", background=[("selected", "#345761")], foreground=[("selected", TEXTO)])
    s.configure("TScrollbar", background=BORDA, troughcolor=PAINEL)
    s.map("TScrollbar", background=[("disabled", PAINEL), ("active", "#506579")])
    s.configure("Horizontal.TProgressbar", background=DESTAQUE, troughcolor=PAINEL)


def painel(pai, **opcoes):
    """Cartão nativo com cantos desenhados, mantendo o layout dos filhos."""
    caixa = tk.Frame(pai, bg=PAINEL, padx=ESPACO, pady=12, **opcoes)
    for x, y, ancora, cx, cy in [(0, 0, "nw", 0, 0), (1, 0, "ne", -14, 0),
                                  (0, 1, "sw", 0, -14), (1, 1, "se", -14, -14)]:
        canto = tk.Canvas(caixa, width=14, height=14, bg=FUNDO, highlightthickness=0)
        canto.create_oval(cx, cy, cx+28, cy+28, fill=PAINEL, outline="")
        canto.place(relx=x, rely=y, anchor=ancora, bordermode="outside")
    return caixa


def rotulo(pai, texto, tipo="Suave", **kwargs):
    return ttk.Label(pai, text=texto, style=tipo+".TLabel", background=PAINEL, **kwargs)


def icone_ambiente(pai, tipo):
    tela = tk.Canvas(pai, width=24, height=24, background=PAINEL, highlightthickness=0)
    linha = lambda *xy: tela.create_line(*xy, fill=DESTAQUE, width=1.5)
    if tipo == "Banco de dados":
        tela.create_oval(4, 4, 20, 10, outline=DESTAQUE)
        linha(4, 7, 4, 17)
        linha(20, 7, 20, 17)
        tela.create_arc(4, 14, 20, 20, start=180, extent=180, style="arc", outline=DESTAQUE)
    elif tipo == "Modelo local":
        tela.create_rectangle(6, 6, 18, 18, outline=DESTAQUE)
        tela.create_rectangle(9, 9, 15, 15, outline=DESTAQUE)
        for x in (9, 15):
            linha(x, 3, x, 6)
            linha(x, 18, x, 21)
            linha(3, x, 6, x)
            linha(18, x, 21, x)
    elif tipo == "Conexão MySQL":
        linha(8, 3, 8, 8)
        linha(16, 3, 16, 8)
        linha(5, 8, 19, 8, 17, 15, 12, 17, 7, 15, 5, 8)
        linha(12, 17, 12, 22)
    elif tipo == "Processamento":
        tela.create_rectangle(3, 4, 21, 16, outline=DESTAQUE)
        linha(12, 16, 12, 20)
        linha(7, 20, 17, 20)
    else:
        tela.create_arc(7, 3, 17, 16, start=0, extent=180, style="arc", outline=DESTAQUE)
        tela.create_rectangle(5, 10, 19, 20, outline=DESTAQUE)
        linha(12, 13, 12, 17)
    return tela


def cabecalho(pai, titulo, subtitulo, sucesso=False):
    barra = ttk.Frame(pai)
    barra.pack(fill="x", pady=(0, ESPACO))
    logo = tk.Canvas(barra, width=54, height=54, highlightthickness=0, bg=FUNDO)
    logo.pack(side="left", padx=(0, 14))
    logo.create_oval(2, 2, 52, 52, fill=PAINEL, outline=BORDA)
    if sucesso:
        logo.create_line(14, 27, 23, 36, 40, 17, fill=DESTAQUE, width=3)
    else:
        logo.create_oval(13, 13, 40, 23, outline=DESTAQUE, width=2)
        for y in (24, 32):
            logo.create_arc(13, y-5, 40, y+6, start=180, extent=180, style="arc", outline=DESTAQUE, width=2)
        for x in (13, 40):
            logo.create_line(x, 18, x, 33, fill=DESTAQUE, width=2)
    ttk.Label(barra, text=titulo, style="Titulo.TLabel").pack(anchor="w")
    ttk.Label(barra, text=subtitulo, style="Suave.TLabel").pack(anchor="w")


def indicador(pai, titulo, valor):
    caixa = painel(pai)
    rotulo(caixa, titulo, "Legenda").pack(anchor="w")
    texto = rotulo(caixa, valor, "Valor")
    texto.pack(anchor="w", pady=(4, 0))
    return caixa, texto

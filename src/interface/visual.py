"""Identidade visual, cartões e componentes compartilhados das janelas."""
import tkinter as tk
from tkinter import font, ttk

FUNDO, PAINEL, PAINEL_ELEVADO, EDITOR = "#221D21", "#433D3D", "#504949", "#30292C"
BORDA, BORDA_FOCO = "#5A5352", "#D88A55"
TEXTO, SUAVE = "#F5F1ED", "#B7AEA5"
DESTAQUE, DESTAQUE_ATIVO = "#F77014", "#E33C08"
SUCESSO, ERRO, AVISO = "#55C995", "#FF8178", "#F2C879"
SELECAO = "#624033"
ESPACOS = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32}
RAIOS = {"botao": 10, "painel": 14, "campo": 8}
ESPACO = ESPACOS["lg"]


def _imagem_botao(raiz, cor, raio=10, cor_foco=None):
    tamanho = raio * 2 + 4
    imagem = tk.PhotoImage(master=raiz, width=tamanho, height=tamanho)
    for y in range(tamanho):
        borda = max(0, raio - y) if y < raio else max(0, y - (tamanho - raio - 1)) if y >= tamanho - raio else 0
        inseto = raio - int(max(0, raio * raio - (raio - borda) ** 2) ** 0.5)
        if tamanho > inseto * 2:
            imagem.put(cor, to=(inseto, y, tamanho - inseto, y + 1))
            if cor_foco and (y in (raio, tamanho - raio - 1)):
                imagem.put(cor_foco, to=(inseto, y, tamanho - inseto, y + 1))
            elif cor_foco:
                imagem.put(cor_foco, to=(inseto, y))
                imagem.put(cor_foco, to=(tamanho - inseto - 1, y))
    return imagem


def _botao_arredondado(s, raiz, nome, cor, ativo, pressionado, desabilitado, texto):
    elemento = nome.replace(".", "_") + ".fundo"
    normal = _imagem_botao(raiz, cor)
    hover = _imagem_botao(raiz, ativo)
    press = _imagem_botao(raiz, pressionado)
    disabled = _imagem_botao(raiz, desabilitado)
    focado = _imagem_botao(raiz, cor, cor_foco=BORDA_FOCO)
    s.element_create(elemento, "image", normal, ("disabled", disabled),
                     ("pressed", press), ("active", hover), ("focus", focado),
                     border=10, sticky="nsew")
    s.layout(nome, [(elemento, {"sticky": "nsew", "children": [
        ("Button.label", {"sticky": "nsew"})]})])
    s.configure(nome, padding=(14, 10), foreground=texto,
                font=("TkDefaultFont", 10, "bold"), anchor="center")
    s.map(nome, foreground=[("disabled", SUAVE)])
    raiz._design_images.extend((normal, hover, press, disabled, focado))


def estilo(raiz):
    familias = set(font.families(root=raiz))
    familia = "Segoe UI" if "Segoe UI" in familias else font.nametofont("TkDefaultFont", root=raiz).actual("family")
    tecnica = "Consolas" if "Consolas" in familias else font.nametofont("TkFixedFont", root=raiz).actual("family")
    font.nametofont("TkDefaultFont", root=raiz).configure(family=familia, size=10)
    font.nametofont("TkFixedFont", root=raiz).configure(family=tecnica, size=10)
    raiz._design_images = []
    s = ttk.Style(raiz)
    s.theme_use("clam")
    raiz.configure(bg=FUNDO)
    s.configure(".", background=FUNDO, foreground=TEXTO, fieldbackground=EDITOR,
                bordercolor=BORDA, lightcolor=BORDA, darkcolor=FUNDO, focuscolor=BORDA_FOCO,
                font=(familia, 10))
    s.configure("TFrame", background=FUNDO)
    for nome, tamanho, peso, cor in [
        ("Titulo", 22, "bold", TEXTO), ("Secao", 13, "bold", TEXTO),
        ("Valor", 17, "bold", TEXTO), ("Suave", 10, "normal", SUAVE),
        ("Legenda", 9, "bold", SUAVE), ("Sucesso", 10, "bold", SUCESSO),
        ("Erro", 11, "bold", ERRO), ("Aviso", 10, "normal", AVISO),
        ("Tecnico", 10, "normal", SUAVE),
    ]:
        s.configure(nome + ".TLabel", font=(familia, tamanho, peso), foreground=cor)
    s.configure("TButton", background=PAINEL_ELEVADO)
    s.map("TButton", background=[("disabled", PAINEL), ("pressed", DESTAQUE_ATIVO), ("active", "#665D5A")])
    s.configure("Executar.TButton", background=DESTAQUE, foreground=FUNDO, font=(familia, 10, "bold"))
    s.map("Executar.TButton", background=[("disabled", "#6B5143"), ("pressed", DESTAQUE_ATIVO), ("active", "#FF883B")],
          foreground=[("disabled", SUAVE)])
    _botao_arredondado(s, raiz, "TButton", PAINEL_ELEVADO, "#665D5A", DESTAQUE_ATIVO, "#393334", TEXTO)
    _botao_arredondado(s, raiz, "Executar.TButton", DESTAQUE, "#FF883B", DESTAQUE_ATIVO, "#6B5143", FUNDO)
    _botao_arredondado(s, raiz, "Terciario.TButton", PAINEL, PAINEL_ELEVADO, BORDA, PAINEL, TEXTO)
    s.configure("TNotebook", background=FUNDO, borderwidth=0, relief="flat",
                bordercolor=FUNDO, lightcolor=FUNDO, darkcolor=FUNDO, tabmargins=(0, 0, 0, 0))
    s.configure("TNotebook.Tab", padding=(16, 10), background=FUNDO, foreground=SUAVE,
                borderwidth=0, relief="flat", bordercolor=FUNDO, lightcolor=FUNDO,
                darkcolor=FUNDO, focuscolor=FUNDO)
    s.map("TNotebook.Tab", foreground=[("selected", DESTAQUE), ("active", TEXTO)],
          background=[("selected", PAINEL), ("active", EDITOR)])
    s.configure("Treeview", background=EDITOR, fieldbackground=EDITOR, foreground=TEXTO,
                rowheight=max(32, font.nametofont("TkDefaultFont", root=raiz).metrics("linespace") + 14),
                borderwidth=0, relief="flat")
    s.configure("Treeview.Heading", background=PAINEL_ELEVADO, foreground=TEXTO,
                padding=(12, 10), borderwidth=0)
    s.map("Treeview.Heading", background=[("active", BORDA)])
    s.map("Treeview", background=[("selected", SELECAO)], foreground=[("selected", TEXTO)])
    s.configure("TEntry", fieldbackground=EDITOR, foreground=TEXTO, padding=(10, 8), borderwidth=1)
    s.map("TEntry", bordercolor=[("focus", DESTAQUE), ("!focus", BORDA)],
          fieldbackground=[("disabled", PAINEL), ("!disabled", EDITOR)])
    s.configure("TScrollbar", background=PAINEL_ELEVADO, troughcolor=FUNDO,
                bordercolor=FUNDO, arrowcolor=SUAVE, width=10)
    s.map("TScrollbar", background=[("disabled", FUNDO), ("active", DESTAQUE)])
    s.configure("Horizontal.TProgressbar", background=DESTAQUE, troughcolor=EDITOR, thickness=5)
    s.configure("Vertical.TProgressbar", background=DESTAQUE, troughcolor=EDITOR, thickness=5)


def painel(pai, **opcoes):
    """Painel de superfície suave com raio consistente e padding reutilizável."""
    cor_fundo = FUNDO
    try:
        cor_fundo = pai.cget("background") or FUNDO
    except tk.TclError:
        pass
    caixa = tk.Frame(pai, bg=PAINEL, padx=ESPACOS["xl"], pady=ESPACOS["lg"],
                     highlightthickness=0, **opcoes)
    raio = RAIOS["painel"]
    cantos = [
        (0, 0, "nw", (0, 0, raio * 2, raio * 2)),
        (1, 0, "ne", (-raio, 0, raio, raio * 2)),
        (0, 1, "sw", (0, -raio, raio * 2, raio)),
        (1, 1, "se", (-raio, -raio, raio, raio)),
    ]
    for x, y, ancora, oval in cantos:
        mascara = tk.Canvas(caixa, width=raio, height=raio, bg=cor_fundo, highlightthickness=0)
        mascara.create_oval(*oval, fill=PAINEL, outline="")
        mascara.place(relx=x, rely=y, anchor=ancora, bordermode="outside")
    return caixa


def rotulo(pai, texto, tipo="Suave", **kwargs):
    kwargs.setdefault("background", PAINEL)
    return ttk.Label(pai, text=texto, style=tipo+".TLabel", **kwargs)


def truncar(texto, limite=24):
    texto = str(texto)
    return texto if len(texto) <= limite else texto[:max(1, limite - 1)].rstrip() + "…"


def dica(widget, conteudo):
    """Exibe o texto integral em hover e foco para preservar acessibilidade."""
    atual = {"janela": None}

    def mostrar(_=None):
        if atual["janela"] or not conteudo:
            return
        janela = tk.Toplevel(widget)
        janela.wm_overrideredirect(True)
        janela.attributes("-topmost", True)
        ttk.Label(janela, text=conteudo, background=PAINEL_ELEVADO, foreground=TEXTO,
                  padding=(10, 7), wraplength=420).pack()
        janela.wm_geometry(f"+{widget.winfo_rootx()+12}+{widget.winfo_rooty()+widget.winfo_height()+6}")
        atual["janela"] = janela

    def ocultar(_=None):
        if atual["janela"]:
            atual["janela"].destroy()
            atual["janela"] = None

    widget.bind("<Enter>", mostrar, add="+")
    widget.bind("<FocusIn>", mostrar, add="+")
    widget.bind("<Leave>", ocultar, add="+")
    widget.bind("<FocusOut>", ocultar, add="+")


def icone_ambiente(pai, tipo):
    tela = tk.Canvas(pai, width=24, height=24, background=PAINEL, highlightthickness=0)
    linha = lambda *xy: tela.create_line(*xy, fill=DESTAQUE, width=1.6, capstyle="round", joinstyle="round")
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
        logo.create_line(14, 27, 23, 36, 40, 17, fill=SUCESSO, width=3, capstyle="round", joinstyle="round")
    else:
        logo.create_oval(13, 10, 30, 19, outline=DESTAQUE, width=2)
        logo.create_arc(13, 14, 30, 24, start=180, extent=180, style="arc", outline=DESTAQUE, width=2)
        logo.create_arc(13, 19, 30, 29, start=180, extent=180, style="arc", outline=DESTAQUE, width=2)
        logo.create_line(13, 14, 13, 24, fill=DESTAQUE, width=2)
        logo.create_line(30, 14, 30, 24, fill=DESTAQUE, width=2)
        logo.create_oval(33, 29, 40, 36, fill=DESTAQUE, outline="")
        for x, y in ((29, 29), (34, 24), (36, 37)):
            logo.create_line(x, y, 35, 32, fill=SUAVE, width=1.3)
    ttk.Label(barra, text=titulo, style="Titulo.TLabel").pack(anchor="w")
    if titulo == "Agente Inteligente Local":
        subtitulo = "Inteligência aplicada a bancos de dados"
    ttk.Label(barra, text=subtitulo, style="Suave.TLabel").pack(anchor="w")


def indicador(pai, titulo, valor):
    caixa = painel(pai)
    topo = tk.Frame(caixa, bg=PAINEL)
    topo.pack(fill="x")
    icone = tk.Canvas(topo, width=24, height=24, bg=PAINEL, highlightthickness=0)
    icone.pack(side="left", padx=(0, 8))
    if "Tempo" in titulo:
        icone.create_oval(4, 4, 20, 20, outline=DESTAQUE, width=1.5)
        icone.create_line(12, 7, 12, 12, 16, 14, fill=DESTAQUE, width=1.5, capstyle="round")
    elif "SQL" in titulo:
        icone.create_line(9, 5, 6, 5, 6, 19, 9, 19, fill=DESTAQUE, width=1.5)
        icone.create_line(15, 5, 18, 5, 18, 19, 15, 19, fill=DESTAQUE, width=1.5)
        icone.create_line(10, 16, 14, 8, fill=DESTAQUE, width=1.5)
    elif "interpretação" in titulo.lower():
        icone.create_line(6, 17, 12, 7, 18, 17, fill=DESTAQUE, width=1.3)
        for x, y in ((6, 17), (12, 7), (18, 17)):
            icone.create_oval(x-2, y-2, x+2, y+2, fill=DESTAQUE, outline="")
    else:
        icone.create_rectangle(5, 6, 19, 10, outline=DESTAQUE, width=1.3)
        icone.create_rectangle(5, 12, 19, 18, outline=DESTAQUE, width=1.3)
    rotulo(topo, titulo, "Legenda").pack(side="left", anchor="w")
    texto = rotulo(caixa, valor, "Valor")
    texto.pack(anchor="w", pady=(8, 0))
    return caixa, texto

"""Componentes e identidade compartilhados pelas janelas do agente."""
import tkinter as tk
from tkinter import font, ttk

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk

FUNDO = EDITOR = "#221D21"
PAINEL, COMPONENTE, PAINEL_ELEVADO = "#30292C", "#433D3D", "#504949"
BORDA, TEXTO, SUAVE = "#51484C", "#F5F1ED", "#B7AEA5"
DESTAQUE, DESTAQUE_ATIVO, SINTAXE = "#F77014", "#E33C08", "#F8A478"
SUCESSO, ERRO, AVISO = "#55C995", "#FF8178", "#F2C879"


def superficie(pai):
    if isinstance(pai, ctk.CTkFrame):
        return pai.cget("fg_color")
    if isinstance(pai, ttk.Widget):
        return ttk.Style(pai).lookup(pai.cget("style") or pai.winfo_class(), "background") or FUNDO
    return pai.cget("background")


def desenho(nome, cor):
    """Pictogramas em uma mesma grade. Só as ilustrações usam imagens."""
    img = Image.new("RGBA", (96, 96))
    d = ImageDraw.Draw(img)
    def linha(*p):
        d.line([int(n*4) for n in p], fill=cor, width=6, joint="curve")
    def oval(x, y, a, b):
        d.ellipse((4*x, 4*y, 4*a, 4*b), outline=cor, width=6)
    if nome in ("marca", "banco"):
        oval(3, 3, 17, 9)
        linha(3, 6, 3, 16, 5, 18, 9, 19, 13, 19)
        linha(17, 6, 17, 12)
        linha(3, 11, 6, 13, 12, 14, 16, 12)
        if nome == "marca":
            linha(15, 18, 20, 15, 22, 12)
            oval(13, 17, 16, 20)
            oval(19, 13, 22, 16)
        else:
            linha(13, 19, 17, 17, 17, 12)
    elif nome == "modelo":
        d.rounded_rectangle((24, 24, 72, 72), radius=7, outline=cor, width=6)
        for v in (9, 15):
            linha(v, 3, v, 6); linha(v, 18, v, 21)
            linha(3, v, 6, v); linha(18, v, 21, v)
    elif nome == "seguro":
        linha(4, 5, 12, 2, 20, 5, 19, 13, 16, 18, 12, 21, 8, 18, 5, 13, 4, 5)
        linha(8, 11, 11, 14, 16, 9)
    elif nome == "sucesso":
        linha(4, 12, 10, 18, 21, 6)
    elif nome == "tempo":
        oval(3, 3, 21, 21); linha(12, 6, 12, 12, 16, 14)
    elif nome == "rede":
        for x, y in ((2, 9), (16, 2), (16, 16)):
            d.rounded_rectangle((4*x, 4*y, 4*(x+5), 4*(y+5)), radius=3, outline=cor, width=5)
        linha(7, 12, 11, 12, 11, 5, 16, 5); linha(11, 12, 11, 18, 16, 18)
    elif nome == "tabela":
        d.rectangle((12, 16, 84, 80), outline=cor, width=6)
        linha(3, 10, 21, 10); linha(9, 10, 9, 20)
    elif nome == "executar":
        linha(6, 3, 20, 12, 6, 21, 6, 3)
    elif nome == "importar":
        linha(3, 17, 3, 6, 9, 6, 11, 9, 21, 9, 18, 18, 3, 18)
    elif nome == "codigo":
        linha(8, 6, 3, 12, 8, 18); linha(16, 6, 21, 12, 16, 18)
    elif nome == "limpar":
        linha(3, 14, 14, 3, 21, 10, 10, 21, 3, 14); linha(9, 20, 21, 20)
    elif nome == "novo":
        linha(4, 12, 20, 12); linha(12, 4, 12, 20)
    return img


def icone(pai, nome, cor=DESTAQUE, tamanho=20):
    imagem = ImageTk.PhotoImage(desenho(nome, cor).resize((tamanho, tamanho), Image.Resampling.LANCZOS), master=pai)
    item = tk.Label(pai, image=imagem, bg=superficie(pai), bd=0)
    item.imagem = imagem
    return item


def estilo(raiz):
    ctk.set_appearance_mode("dark")
    familias = set(font.families(root=raiz))
    # Em instalações Tk sem Xft a fonte de formas pode não estar disponível.
    if "CustomTkinter_shapes_font" not in familias and raiz.tk.call("tk", "windowingsystem") == "x11":
        ctk.DrawEngine.preferred_drawing_method = "polygon_shapes"
    familia = next((f for f in ("Segoe UI", "DejaVu Sans", "helvetica") if f in familias), "TkDefaultFont")
    tecnica = next((f for f in ("Consolas", "DejaVu Sans Mono", "courier") if f in familias), "TkFixedFont")
    for nome, fonte, tamanho in (("TkDefaultFont", familia, 11), ("TkFixedFont", tecnica, 11)):
        font.nametofont(nome, root=raiz).configure(family=fonte, size=tamanho)
    raiz.configure(bg=FUNDO)
    raiz.icone = ImageTk.PhotoImage(desenho("marca", DESTAQUE), master=raiz)
    raiz.iconphoto(True, raiz.icone)
    s = ttk.Style(raiz)
    s.theme_use("clam")
    s.configure(".", background=FUNDO, foreground=TEXTO, font=(familia, 11))
    s.configure("TFrame", background=FUNDO)
    for nome, tamanho, peso, cor in [
        ("Titulo", 24, "bold", TEXTO), ("Secao", 15, "bold", TEXTO),
        ("Valor", 22, "bold", TEXTO), ("Suave", 10, "normal", SUAVE),
        ("Legenda", 10, "bold", SUAVE), ("Sucesso", 10, "bold", SUCESSO),
        ("Erro", 12, "bold", ERRO), ("Aviso", 10, "normal", AVISO), ("Tecnico", 10, "normal", SUAVE)
    ]:
        s.configure(nome+".TLabel", font=(familia, tamanho, peso), foreground=cor)
    s.configure("Treeview", background=EDITOR, fieldbackground=EDITOR, foreground=TEXTO,
                rowheight=font.nametofont("TkDefaultFont", root=raiz).metrics("linespace")+16,
                borderwidth=0, relief="flat", bordercolor=PAINEL, lightcolor=PAINEL, darkcolor=PAINEL)
    s.configure("Treeview.Heading", background=COMPONENTE, foreground=TEXTO,
                padding=(10, 8), borderwidth=0)
    s.map("Treeview.Heading", background=[("active", PAINEL_ELEVADO)])
    s.map("Treeview", background=[("selected", "#624033")], foreground=[("selected", TEXTO)])


class Botao(ctk.CTkButton):
    def __init__(self, pai, text, command, tipo="secundario", simbolo=None, **opcoes):
        fundo = superficie(pai)
        self.normal = {"primario": DESTAQUE, "terciario": fundo}.get(tipo, COMPONENTE)
        self.sobre = "#FF934C" if tipo == "primario" else PAINEL_ELEVADO
        cor = FUNDO if tipo == "primario" else TEXTO
        imagem = ctk.CTkImage(dark_image=desenho(simbolo, cor), size=(17, 17)) if simbolo else None
        fonte = font.nametofont("TkDefaultFont", root=pai).actual("family")
        super().__init__(pai, text=text, command=command, fg_color=self.normal, bg_color=fundo,
                         hover_color=self.sobre, text_color=cor, text_color_disabled=SUAVE,
                         corner_radius=11, border_width=1, border_color=self.normal,
                         height=44 if tipo == "primario" else 36, width=36,
                         border_spacing=7, font=(fonte, 14, "bold" if tipo == "primario" else "normal"),
                         image=imagem, **opcoes)
        tk.Frame.configure(self, takefocus=1)
        tk.Misc.bind(self, "<FocusIn>", lambda _: self.configure(border_color=SINTAXE))
        tk.Misc.bind(self, "<FocusOut>", lambda _: self.configure(border_color=self.normal))
        for tecla in ("<space>", "<Return>"):
            tk.Misc.bind(self, tecla, self._tecla)
        self.bind("<ButtonPress-1>", self._pressionar)
        self.bind("<Leave>", self._soltar)

    def _on_release(self, evento):
        # O comando pode destruir esta janela. Finalize o estado antes de invocá-lo.
        self._soltar(evento)
        x = evento.x_root - self.winfo_rootx()
        y = evento.y_root - self.winfo_rooty()
        if 0 <= x < self.winfo_width() and 0 <= y < self.winfo_height():
            self.invoke()

    def _tecla(self, _):
        self.invoke()
        return "break"

    def _pressionar(self, _):
        if self.cget("state") != "disabled":
            tk.Misc.focus_set(self)
            self.configure(fg_color=DESTAQUE_ATIVO, hover_color=DESTAQUE_ATIVO)

    def _soltar(self, _):
        if self.winfo_exists() and self.cget("state") != "disabled":
            self.configure(fg_color=self.normal, hover_color=self.sobre)

    def configure(self, **kw):
        if "state" in kw:
            ativo = kw["state"] != "disabled"
            kw.update(fg_color=self.normal if ativo else PAINEL, border_color=self.normal if ativo else BORDA,
                      hover_color=self.sobre)
            tk.Frame.configure(self, takefocus=int(ativo))
        super().configure(**kw)


def barra(pai, command, orient="vertical"):
    return ctk.CTkScrollbar(pai, command=command, orientation=orient, fg_color=superficie(pai),
                            bg_color=superficie(pai), button_color=BORDA, button_hover_color=SUAVE,
                            **({"width": 13} if orient == "vertical" else {"height": 13}))


def painel(pai):
    caixa = ctk.CTkFrame(pai, fg_color=PAINEL, bg_color=superficie(pai), corner_radius=16)
    caixa.conteudo = tk.Frame(caixa, bg=PAINEL)
    caixa.conteudo.pack(fill="both", expand=True, padx=18, pady=12)
    return caixa


def rotulo(pai, texto, tipo="Suave", **kwargs):
    kwargs.setdefault("background", superficie(pai))
    return ttk.Label(pai, text=texto, style=tipo+".TLabel", **kwargs)


def truncar(texto, limite=40):
    return texto if len(texto) <= limite else texto[:limite-1].rstrip()+"…"


def dica(widget, conteudo):
    janela = None
    def mostrar(_):
        nonlocal janela
        if janela is None:
            janela = tk.Toplevel(widget)
            janela.overrideredirect(True)
            rotulo(janela, conteudo, background=COMPONENTE, padding=8, wraplength=600).pack()
            janela.geometry(f"+{widget.winfo_rootx()}+{widget.winfo_rooty()+widget.winfo_height()}")
    def ocultar(_):
        nonlocal janela
        if janela:
            janela.destroy()
            janela = None
    for evento in ("<Enter>", "<FocusIn>"):
        widget.bind(evento, mostrar)
    for evento in ("<Leave>", "<FocusOut>", "<Unmap>"):
        widget.bind(evento, ocultar)


def cabecalho(pai, titulo, subtitulo, sucesso=False):
    topo = ttk.Frame(pai)
    topo.pack(fill="x", pady=(0, 14))
    selo = ctk.CTkFrame(topo, corner_radius=14, fg_color=PAINEL, bg_color=FUNDO)
    selo.pack(side="left", padx=(0, 14))
    icone(selo, "sucesso" if sucesso else "marca", SUCESSO if sucesso else DESTAQUE, 32).pack(padx=11, pady=11)
    rotulo(topo, titulo, "Titulo").pack(anchor="w")
    rotulo(topo, subtitulo).pack(anchor="w")


def indicador(pai, titulo, valor, simbolo, detalhe=""):
    caixa = painel(pai)
    topo = tk.Frame(caixa.conteudo, bg=PAINEL)
    topo.pack(fill="x")
    icone(topo, simbolo, tamanho=18).pack(side="left", padx=(0, 8))
    rotulo(topo, titulo).pack(side="left")
    rotulo(caixa.conteudo, valor, "Valor").pack(anchor="w")
    if detalhe:
        rotulo(caixa.conteudo, detalhe).pack(anchor="w")
    return caixa


class Abas(ttk.Frame):
    """Navegação de largura fixa entre páginas que ocupam a mesma região."""
    def __init__(self, pai, nomes):
        super().__init__(pai)
        self.paginas, self.botoes = {}, {}
        self.atual = nomes[0]
        nav = ttk.Frame(self)
        nav.pack(fill="x", pady=(0, 8))
        for nome, simbolo in zip(nomes, ("codigo", "tabela", "rede")):
            botao = Botao(nav, nome, lambda n=nome: self.selecionar(n), simbolo=simbolo)
            botao.pack(side="left", padx=(0, 6))
            self.botoes[nome] = botao
            self.paginas[nome] = ttk.Frame(self)
        self.selecionar(self.atual)
        def avancar(evento, passo):
            self.selecionar(nomes[(nomes.index(self.atual)+passo) % len(nomes)])
            tk.Misc.focus_set(self.botoes[self.atual])
            return "break"
        self.winfo_toplevel().bind("<Control-Tab>", lambda e: avancar(e, 1))
        self.winfo_toplevel().bind("<Control-Shift-Tab>", lambda e: avancar(e, -1))

    def selecionar(self, nome):
        self.paginas[self.atual].pack_forget()
        self.atual = nome
        self.paginas[nome].pack(fill="both", expand=True)
        for chave, botao in self.botoes.items():
            ativo = chave == nome
            botao.normal = PAINEL_ELEVADO if ativo else FUNDO
            botao.configure(fg_color=botao.normal, border_color=botao.normal,
                            text_color=SINTAXE if ativo else SUAVE)

"""Linha do tempo alimentada pelos eventos reais da sessão local."""
from time import monotonic
import tkinter as tk
from tkinter import ttk

from src.interface.visual import SUAVE, DESTAQUE, ERRO, SUCESSO, PAINEL, EDITOR, painel, rotulo, Botao

ETAPAS = ("Validação da requisição", "Verificação do modelo local", "Conexão com o banco de dados",
          "Descoberta da estrutura", "Interpretação semântica", "Planejamento dos relacionamentos",
          "Geração e validação SQL", "Execução da consulta", "Conclusão")
EVENTOS = {"Verificação do modelo Ollama": 1, "Conexão com o banco": 2, "Descoberta da estrutura": 3,
           "Interpretação da requisição": 4, "Planejamento dos relacionamentos": 5,
           "Geração e validação SQL": 6, "Execução da consulta": 7}
ORIENTACOES = (
    "Revise os seis campos obrigatórios e a sintaxe do JSON.",
    "Verifique se o Ollama está em execução e se o modelo configurado está instalado.",
    "Confira o serviço MySQL e as configurações locais de conexão.",
    "Verifique se a conta pode consultar os metadados do banco.",
    "Especifique a entidade, os campos e os filtros com mais precisão.",
    "Esclareça o papel das tabelas relacionadas na requisição.",
    "Revise os campos, filtros e agrupamentos solicitados.",
    "Confira a disponibilidade do banco e as permissões de leitura.",
    "Confira o resultado e as permissões de gravação das métricas.",
)


class Progresso:
    def __init__(self, pai):
        self.caixa = painel(pai)
        topo = tk.Frame(self.caixa.conteudo, bg=PAINEL)
        topo.pack(fill="x")
        rotulo(topo, "Processamento da consulta", "Secao").pack(side="left")
        cronometro = tk.Frame(topo, bg=EDITOR, padx=12, pady=6)
        cronometro.pack(side="right")
        rotulo(cronometro, "TEMPO REAL", "Legenda", background=EDITOR).pack(side="left", padx=(0, 10))
        self.tempo = ttk.Label(cronometro, text="00:00", style="Valor.TLabel", background=EDITOR)
        self.tempo.pack(side="right")
        self.acao = Botao(self.caixa.conteudo, "Processando...", None, "primario")
        self.acao.configure(state="disabled")
        self.acao.pack(side="bottom", anchor="e", pady=(4, 0))
        self.estados, self.pontos = [], []
        for indice, nome in enumerate(ETAPAS):
            linha = tk.Frame(self.caixa.conteudo, bg=PAINEL)
            linha.pack(fill="x")
            ponto = tk.Canvas(linha, width=22, height=32, bg=PAINEL, highlightthickness=0)
            ponto.pack(side="left", padx=(0, 10))
            if indice:
                ponto.create_line(11, 0, 11, 9, fill=SUAVE)
            if indice < len(ETAPAS)-1:
                ponto.create_line(11, 23, 11, 32, fill=SUAVE)
            ponto.create_oval(4, 9, 18, 23, outline=SUAVE, width=1.3, tags="anel")
            ponto.create_line(7, 16, 10, 19, 15, 13, fill=EDITOR, width=2,
                              capstyle="round", joinstyle="round", state="hidden", tags="marca")
            ponto.create_arc(3, 8, 19, 24, start=30, extent=250, style="arc",
                             outline=DESTAQUE, width=2, state="hidden", tags="giro")
            ponto.create_text(11, 16, text="!", fill=EDITOR, font=("TkDefaultFont", 9, "bold"),
                              state="hidden", tags="alerta")
            self.pontos.append(ponto)
            rotulo(linha, nome).pack(side="left")
            estado = rotulo(linha, "Pendente", "Legenda")
            estado.pack(side="right")
            self.estados.append(estado)
        self.atual, self.inicio, self.giro, self.spinner_job = 0, None, 30, None

    def iniciar(self):
        self.parar_spinner()
        self.inicio = monotonic()
        self.tempo.configure(text="00:00")
        for estado, ponto in zip(self.estados, self.pontos):
            estado.configure(text="Pendente", foreground=SUAVE)
            ponto.itemconfigure("anel", outline=SUAVE, fill="")
            ponto.itemconfigure("alerta", state="hidden")
            ponto.itemconfigure("marca", state="hidden")
            ponto.itemconfigure("giro", state="hidden")
        self.atual = 0
        self.entrar(0)
        self.relogio()

    def relogio(self):
        if self.inicio is None:
            return
        segundos = int(monotonic() - self.inicio)
        self.tempo.configure(text=f"{segundos // 60:02}:{segundos % 60:02}")

    def animar(self):
        self.spinner_job = None
        if self.inicio is None:
            return
        self.giro = (self.giro + 30) % 360
        self.pontos[self.atual].itemconfigure("giro", start=self.giro)
        self.spinner_job = self.pontos[self.atual].after(90, self.animar)

    def parar_spinner(self):
        if self.spinner_job:
            try:
                self.pontos[self.atual].after_cancel(self.spinner_job)
            except tk.TclError:
                pass
            self.spinner_job = None

    def entrar(self, indice):
        self.parar_spinner()
        self.concluir_etapa()
        self.atual = indice
        self.estados[indice].configure(text="Em processamento", foreground=DESTAQUE)
        self.pontos[indice].itemconfigure("marca", state="hidden")
        self.pontos[indice].itemconfigure("anel", outline=DESTAQUE, fill="")
        self.pontos[indice].itemconfigure("giro", state="normal", start=self.giro)
        self.animar()
        if indice == 4:
            self.estados[5].configure(text="Pendente", foreground=SUAVE)
            self.pontos[5].itemconfigure("anel", outline=SUAVE, fill="")
            self.pontos[5].itemconfigure("marca", state="hidden")

    def concluir_etapa(self):
        if self.estados[self.atual].cget("text") == "Pendente":
            return
        self.estados[self.atual].configure(text="Concluída", foreground=SUCESSO)
        ponto = self.pontos[self.atual]
        ponto.itemconfigure("anel", outline=SUCESSO, fill=SUCESSO)
        ponto.itemconfigure("marca", state="normal")
        ponto.itemconfigure("giro", state="hidden")

    def finalizar(self, sucesso):
        self.relogio()
        self.parar_spinner()
        self.inicio = None
        if sucesso:
            self.entrar(8)
            self.parar_spinner()
            self.concluir_etapa()
        else:
            self.estados[self.atual].configure(text="Falha", foreground=ERRO)
            ponto = self.pontos[self.atual]
            ponto.itemconfigure("anel", fill=ERRO, outline=ERRO)
            ponto.itemconfigure("giro", state="hidden")
            ponto.itemconfigure("marca", state="hidden")
            ponto.itemconfigure("alerta", state="normal")

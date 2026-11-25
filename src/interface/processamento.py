"""Linha do tempo alimentada pelos eventos reais da sessão local."""
from time import monotonic
import tkinter as tk
from tkinter import ttk

from src.interface.visual import SUAVE, DESTAQUE, ERRO, TEXTO, painel, rotulo

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
        topo = tk.Frame(self.caixa, bg=self.caixa["bg"])
        topo.pack(fill="x")
        rotulo(topo, "Processamento da consulta", "Secao").pack(side="left")
        self.tempo = rotulo(topo, "", "Valor")
        self.tempo.pack(side="right")
        self.atividade = ttk.Progressbar(self.caixa, mode="indeterminate", length=180)
        self.atividade.pack(fill="x", pady=(10, 12))
        self.estados = []
        self.pontos = []
        for nome in ETAPAS:
            linha = tk.Frame(self.caixa, bg=self.caixa["bg"])
            linha.pack(fill="x", pady=4)
            ponto = tk.Canvas(linha, width=18, height=18, bg=self.caixa["bg"], highlightthickness=0)
            ponto.pack(side="left", padx=(0, 8))
            ponto.create_oval(4, 4, 13, 13, outline=SUAVE, tags="estado")
            self.pontos.append(ponto)
            rotulo(linha, nome).pack(side="left")
            estado = rotulo(linha, "Pendente", "Legenda")
            estado.pack(side="right")
            self.estados.append(estado)
        self.atual = 0

    def iniciar(self):
        self.inicio = monotonic()
        for e, ponto in zip(self.estados, self.pontos):
            e.configure(text="Pendente", foreground=SUAVE)
            ponto.itemconfigure("estado", fill="", outline=SUAVE)
        self.atual = 0
        self.entrar(0)
        self.atividade.start(24)
        self.relogio()

    def relogio(self):
        segundos = int(monotonic()-self.inicio)
        self.tempo.configure(text=f"{segundos//60:02}:{segundos%60:02}")

    def entrar(self, indice):
        self.concluir_etapa()
        self.atual = indice
        self.estados[indice].configure(text="Em processamento", foreground=DESTAQUE)
        self.pontos[indice].itemconfigure("estado", fill=DESTAQUE, outline=DESTAQUE)
        # Uma nova interpretação invalida o planejamento da tentativa anterior.
        if indice == 4:
            self.estados[5].configure(text="Pendente", foreground=SUAVE)
            self.pontos[5].itemconfigure("estado", fill="", outline=SUAVE)

    def concluir_etapa(self):
        self.estados[self.atual].configure(text="Concluída", foreground=TEXTO)
        self.pontos[self.atual].itemconfigure("estado", fill=SUAVE, outline=SUAVE)

    def finalizar(self, sucesso):
        self.atividade.stop()
        self.relogio()
        if sucesso:
            self.entrar(8)
            self.concluir_etapa()
        else:
            self.estados[self.atual].configure(text="Falha", foreground=ERRO)
            self.pontos[self.atual].itemconfigure("estado", fill=ERRO, outline=ERRO)

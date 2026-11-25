"""Visualização local, paginação e exportação dos registros já recuperados."""
import csv
import json
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from numbers import Number
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, font, ttk

from src.interface.visual import FUNDO, PAINEL


def selecionar(registros, busca, coluna=None, reversa=False):
    termo = busca.strip().casefold()
    linhas = [r for r in registros if any(termo in str(v).casefold() for v in r.values())] if termo else registros
    if coluna is None:
        return linhas

    def chave(registro):
        v = registro.get(coluna)
        if isinstance(v, Number):
            return (0, v)
        return (1, str(v).casefold())

    presentes = sorted((r for r in linhas if r.get(coluna) is not None), key=chave, reverse=reversa)
    presentes.extend(r for r in linhas if r.get(coluna) is None)
    return presentes


def gravar(caminho, dados, formato):
    """Grava em arquivo temporário para preservar o destino em caso de falha."""
    destino = Path(caminho)
    arquivo = tempfile.NamedTemporaryFile(mode="w", newline="", dir=destino.parent,
                                          encoding="utf-8-sig" if formato == "csv" else "utf-8",
                                          delete=False)
    try:
        with arquivo:
            if formato == "csv":
                if dados:
                    escritor = csv.DictWriter(arquivo, fieldnames=list(dados[0]))
                    escritor.writeheader()
                    escritor.writerows(dados)
            elif formato == "json":
                json.dump(dados, arquivo, ensure_ascii=False, default=str, indent=2)
            else:
                arquivo.write(dados)
        os.replace(arquivo.name, destino)
    finally:
        Path(arquivo.name).unlink(missing_ok=True)


class Tabela:
    def __init__(self, pai, registros):
        self.pai = pai
        self.registros = self.linhas = registros
        self.coluna = None
        self.reversa = False
        self.inicio = 0
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.futuro = self.timer = self.poll = None
        self.busca = tk.StringVar(pai)
        self.nomes = list(registros[0]) if registros else []
        barra = ttk.Frame(pai)
        barra.pack(fill="x", pady=(0, 8))
        ttk.Label(barra, text="Pesquisar registros").pack(side="left")
        ttk.Entry(barra, textvariable=self.busca, width=24).pack(side="left", padx=8)
        self.info = ttk.Label(barra, style="Suave.TLabel")
        self.info.pack(side="right")
        quadro = ttk.Frame(pai)
        quadro.pack(fill="both", expand=True)
        quadro.columnconfigure(0, weight=1)
        quadro.rowconfigure(0, weight=1)
        ids = [f"c{i}" for i in range(len(self.nomes))]
        self.grade = ttk.Treeview(quadro, columns=ids, show="headings")
        self.grade.grid(row=0, column=0, sticky="nsew")
        fonte = font.nametofont("TkDefaultFont", root=pai)
        for idx, nome in zip(ids, self.nomes):
            amostra = [r[nome] for r in registros[:32] if r[nome] is not None]
            largura = max([fonte.measure(nome), *(fonte.measure(str(v)[:80]) for v in amostra)])
            numerica = amostra and all(isinstance(v, Number) and not isinstance(v, bool) for v in amostra)
            self.grade.column(idx, anchor="e" if numerica else "w", width=max(100, min(400, largura+36)), minwidth=55)
            self.grade.heading(idx, text=nome, command=lambda n=nome: self.ordenar(n))
        self.grade.tag_configure("par", background=PAINEL)
        self.grade.tag_configure("impar", background=FUNDO)
        for eixo, orient, row, col, sticky in [("y", "vertical", 0, 1, "ns"), ("x", "horizontal", 1, 0, "ew")]:
            scroll = ttk.Scrollbar(quadro, orient=orient, command=getattr(self.grade, eixo+"view"))
            scroll.grid(row=row, column=col, sticky=sticky)
            self.grade.configure(**{eixo+"scrollcommand": scroll.set})
        rodape = ttk.Frame(pai)
        rodape.pack(fill="x", pady=(8, 0))
        self.ant = ttk.Button(rodape, text="Anterior", command=lambda: self.mostrar(self.inicio-100))
        self.prox = ttk.Button(rodape, text="Próxima", command=lambda: self.mostrar(self.inicio+100))
        self.prox.pack(side="right")
        self.ant.pack(side="right", padx=6)
        self.busca.trace_add("write", lambda *_: self.agendar())
        pai.bind("<Destroy>", self.fechar, add="+")
        self.mostrar(0)

    def fechar(self, evento):
        if evento.widget == self.pai:
            for agendamento in (self.timer, self.poll):
                if agendamento:
                    self.pai.after_cancel(agendamento)
            self.pool.shutdown(wait=False, cancel_futures=True)

    def agendar(self):
        if self.timer:
            self.pai.after_cancel(self.timer)
        if self.poll:
            self.pai.after_cancel(self.poll)
            self.poll = None
        if self.futuro:
            self.futuro.cancel()
        self.timer = self.pai.after(140, self.filtrar)

    def ordenar(self, coluna):
        self.reversa = self.coluna == coluna and not self.reversa
        self.coluna = coluna
        self.agendar()

    def filtrar(self):
        self.timer = None
        self.info.configure(text="Atualizando visualização…")
        self.futuro = self.pool.submit(selecionar, self.registros, self.busca.get(), self.coluna, self.reversa)
        self.receber()

    def receber(self):
        self.poll = None
        if not self.futuro.done():
            self.poll = self.pai.after(40, self.receber)
            return
        self.linhas = self.futuro.result()
        for i, nome in enumerate(self.nomes):
            seta = (" ↓" if self.reversa else " ↑") if self.coluna == nome else ""
            self.grade.heading(f"c{i}", text=nome+seta)
        self.mostrar(0)

    def mostrar(self, inicio):
        self.inicio = inicio
        self.grade.delete(*self.grade.get_children())
        for i, r in enumerate(self.linhas[inicio:inicio+100]):
            self.grade.insert("", "end", values=["NULL" if r[n] is None else str(r[n]) for n in self.nomes],
                              tags=("impar" if i % 2 else "par",))
        total = len(self.linhas)
        self.info.configure(text=(f"{inicio+1}–{min(inicio+100, total)} de {total}" if total
                                  else "Nenhum registro encontrado"))
        self.ant.configure(state="normal" if inicio else "disabled")
        self.prox.configure(state="normal" if inicio+100 < total else "disabled")


def escolher_exportacao(janela):
    return filedialog.asksaveasfilename(parent=janela, title="Exportar todos os resultados",
                                        defaultextension=".csv", filetypes=[("CSV", "*.csv"), ("JSON", "*.json")])

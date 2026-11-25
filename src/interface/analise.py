"""Visualizações da interpretação e das medições produzidas pelo agente."""
import json
import tkinter as tk
from tkinter import ttk

from src.interface.visual import FUNDO, PAINEL, BORDA, SUAVE, TEXTO, DESTAQUE, painel, rotulo


def segundos(valor):
    if valor is None:
        return "—"
    if 0 < valor < 0.01:
        return f"{valor * 1000:.2f} ms"
    return f"{valor:.2f} s"


def interpretacao(pai, plano, pedido, leitura):
    botoes = ttk.Frame(pai)
    botoes.pack(fill="x", pady=(0, 8))
    corpo = ttk.Frame(pai)
    corpo.pack(fill="both", expand=True)
    relacoes = plano.get("relacionamentos_necessarios", [])
    def mostrar(pagina):
        for filho in corpo.winfo_children():
            filho.destroy()
        for b in botoes.winfo_children():
            b.configure(state="disabled" if b.cget("text") == pagina else "normal")
        if pagina == "JSON completo":
            leitura(corpo, json.dumps(plano, ensure_ascii=False, indent=2))
            return
        if pagina == "Relacionamentos":
            # Uma aresta por FK, com ambas as colunas identificadas. A área rola
            # nas duas direções inclusive para identificadores físicos longos.
            tela = tk.Canvas(corpo, bg=PAINEL, highlightthickness=0)
            vertical = ttk.Scrollbar(corpo, command=tela.yview)
            horizontal = ttk.Scrollbar(corpo, orient="horizontal", command=tela.xview)
            horizontal.pack(side="bottom", fill="x")
            vertical.pack(side="right", fill="y")
            tela.pack(fill="both", expand=True)
            tela.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
            if not relacoes:
                tela.create_text(16, 24, anchor="w", text="Consulta sem relacionamentos.", fill=SUAVE)
            for i, r in enumerate(relacoes):
                y = 30 + 52*i
                origem = tela.create_text(26, y, anchor="w", text=r["origem"], fill=TEXTO, font="TkFixedFont")
                x = tela.bbox(origem)[2]+14
                tela.create_line(x+3, y, x+42, y, arrow="last", fill=DESTAQUE, width=2)
                destino = tela.create_text(x+62, y, anchor="w", text=r["destino"], fill=TEXTO, font="TkFixedFont")
                for item in (origem, destino):
                    l, t, d, b = tela.bbox(item)
                    fundo = tela.create_rectangle(l-8,t-7,d+8,b+7,fill=FUNDO,outline=BORDA)
                    tela.tag_lower(fundo, item)
            tela.configure(scrollregion=tela.bbox("all"))
            return
        filtros = [f"{f['campo']} {f['operador']} {json.dumps(f['valor'], ensure_ascii=False)}"
                   for f in plano.get("filtros", [])]
        grupos = plano.get("agrupamento", pedido.get("agrupamento", []))
        ags = plano.get("agregacoes", pedido.get("agregacoes", []))
        itens = [("Entidade solicitada", [pedido.get("entidade", "—")]),
                 ("Tabelas identificadas", plano.get("tabelas_identificadas", [])),
                 ("Campos selecionados", plano.get("campos_solicitados", [])), ("Filtros aplicados", filtros),
                 ("Relacionamentos", [r["origem"]+" → "+r["destino"] for r in relacoes]),
                 ("Agrupamento", grupos), ("Agregações", [f"{a['funcao']}({a['campo']})" for a in ags])]
        texto = leitura(corpo, "")
        texto.configure(state="normal")
        texto.tag_configure("titulo", foreground=DESTAQUE, spacing1=7, spacing3=2)
        for titulo, valores in itens:
            texto.insert("end", titulo+"\n", "titulo")
            texto.insert("end", ", ".join(valores)+"\n" if valores else "—\n")
        texto.configure(state="disabled")
    for nome in ("Resumo", "Relacionamentos", "JSON completo"):
        ttk.Button(botoes, text=nome, command=lambda n=nome: mostrar(n)).pack(side="left", padx=(0, 6))
    mostrar("Resumo")


def metricas(pai, m, aviso):
    aviso_falha = aviso.lower().startswith("aviso")
    ttk.Label(pai, text="Registro de métricas indisponível." if aviso_falha else "Métricas da execução",
              style="Aviso.TLabel" if aviso_falha else "Secao.TLabel").pack(anchor="w", pady=(0, 8))
    area = ttk.Frame(pai)
    area.pack(fill="both", expand=True)
    area.columnconfigure((0, 1), weight=1, uniform="metrica")
    grupos = [(0, "Requisição · acumulado", [
        ("Interpretação", m.get("tempo_interpretacao_segundos")),
        ("Geração e validação SQL", m.get("tempo_geracao_sql_segundos")),
        ("Execução MySQL", m.get("tempo_execucao_mysql_segundos"))]),
        (1, "Modelo · última interpretação", [(nome, m.get("interpretacao", {}).get(chave)) for nome, chave in
         [("Carregamento", "carregamento_segundos"), ("Processamento do prompt", "processamento_prompt_segundos"),
          ("Geração da resposta", "geracao_segundos")]])]
    for col, titulo, itens in grupos:
        bloco = painel(area)
        bloco.grid(row=0, column=col, sticky="new", padx=(0, 6) if col == 0 else (6, 0))
        rotulo(bloco, titulo, "Secao").pack(anchor="w", pady=(0, 8))
        maior = max((v for _, v in itens if v is not None), default=0)
        for nome, valor in itens:
            linha = tk.Frame(bloco, bg=PAINEL)
            linha.pack(fill="x")
            rotulo(linha, nome).pack(side="left")
            rotulo(linha, segundos(valor), "Legenda").pack(side="right")
            trilho = tk.Frame(bloco, bg=BORDA, height=5)
            trilho.pack(fill="x", pady=(4, 9))
            if valor and maior > 0:
                tk.Frame(trilho, bg=DESTAQUE).place(relwidth=valor/maior, relheight=1)
        if col == 0:
            detalhe = f"Tempo total   {segundos(m.get('tempo_total_segundos'))}"
        else:
            ollama = m.get("interpretacao", {})
            detalhe = f"Tokens   {ollama.get('tokens_entrada') if ollama.get('tokens_entrada') is not None else '—'} de entrada  /  {ollama.get('tokens_gerados') if ollama.get('tokens_gerados') is not None else '—'} de saída"
        rotulo(bloco, detalhe, "Legenda", wraplength=270).pack(anchor="w", pady=(6, 0))

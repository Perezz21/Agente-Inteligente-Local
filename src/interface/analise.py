"""Visualizações da interpretação e das medições produzidas pelo agente."""
import json
import math
import textwrap
import tkinter as tk
from tkinter import ttk

from src.interface.visual import (FUNDO, PAINEL, EDITOR, BORDA, SUAVE, TEXTO,
                                  DESTAQUE, DESTAQUE_ATIVO, painel, rotulo)


def segundos(valor):
    if valor is None:
        return "Não disponível"
    if 0 < valor < 0.01:
        return f"{valor * 1000:.2f} ms"
    return f"{valor:.2f} s"


def _arredondado(tela, x1, y1, x2, y2, raio=9, **opcoes):
    raio = min(raio, max(2, (x2 - x1) / 2), max(2, (y2 - y1) / 2))
    pontos = [x1+raio, y1, x2-raio, y1, x2, y1, x2, y1+raio,
              x2, y2-raio, x2, y2, x2-raio, y2, x1+raio, y2,
              x1, y2, x1, y2-raio, x1, y1+raio, x1, y1]
    return tela.create_polygon(pontos, smooth=True, splinesteps=12, **opcoes)


def _cartao(corpo, titulo, valor, linha, coluna):
    bloco = painel(corpo)
    bloco.grid(row=linha, column=coluna, sticky="nsew",
               padx=(0, 8) if coluna == 0 else (8, 0), pady=(0, 12))
    rotulo(bloco, titulo, "Legenda").pack(anchor="w")
    detalhe = ttk.Label(bloco, text=valor, background=PAINEL, foreground=TEXTO,
                        justify="left", wraplength=320, anchor="nw")
    detalhe.pack(fill="x", anchor="w", pady=(7, 0))
    return bloco, detalhe


def desenhar_grafo(tela, relacoes, tabelas):
    """Monta o grafo a partir dos nomes de tabelas e chaves do plano real."""
    nomes = list(dict.fromkeys(str(nome) for nome in (tabelas or []) if nome))
    arestas = []
    for relacao in relacoes or []:
        origem, destino = str(relacao.get("origem", "")), str(relacao.get("destino", ""))
        if not origem or not destino:
            continue
        tabela_origem = origem.rsplit(".", 1)[0] if "." in origem else origem
        tabela_destino = destino.rsplit(".", 1)[0] if "." in destino else destino
        for nome in (tabela_origem, tabela_destino):
            if nome not in nomes:
                nomes.append(nome)
        arestas.append((tabela_origem, origem, tabela_destino, destino))
    if not nomes:
        tela.create_text(24, 24, anchor="nw", text="Nenhum relacionamento identificado nesta interpretação.",
                         fill=SUAVE, font=("TkDefaultFont", 10))
        tela.configure(scrollregion=(0, 0, 620, 100))
        return

    adjacencia = {nome: set() for nome in nomes}
    for origem, _, destino, _ in arestas:
        adjacencia[origem].add(destino)
        adjacencia[destino].add(origem)
    niveis, proximo = {}, 0
    for raiz in nomes:
        if raiz in niveis:
            continue
        niveis[raiz] = proximo
        fila = [raiz]
        while fila:
            atual = fila.pop(0)
            for vizinho in nomes:
                if vizinho in adjacencia[atual] and vizinho not in niveis:
                    niveis[vizinho] = niveis[atual] + 1
                    fila.append(vizinho)
        proximo = max(niveis.values(), default=proximo) + 1
    colunas = {}
    for nome in nomes:
        colunas.setdefault(niveis[nome], []).append(nome)
    largura_no, passo_x, espacamento_y = 236, 450, 34
    contagem_pares, contagem_nos = {}, {nome: 0 for nome in nomes}
    for origem, _, destino, _ in arestas:
        par = tuple(sorted((origem, destino)))
        contagem_pares[par] = contagem_pares.get(par, 0) + 1
        contagem_nos[origem] += 1
        contagem_nos[destino] += 1
    alturas = {nome: max(84, 48 + 16 * math.ceil(len(nome) / 27),
                         48 + contagem_nos[nome] * 18) for nome in nomes}
    posicoes, max_y = {}, 40
    for nivel, itens in colunas.items():
        y = 40
        for nome in itens:
            posicoes[nome] = (40 + nivel * passo_x, y, alturas[nome])
            y += alturas[nome] + espacamento_y
        max_y = max(max_y, y)

    # Desenha as ligações antes dos nós para que os cartões fiquem à frente.
    repeticoes = {}
    for origem, campo_origem, destino, campo_destino in arestas:
        x1, y1, altura1 = posicoes[origem]
        x2, y2, altura2 = posicoes[destino]
        par = tuple(sorted((origem, destino)))
        indice = repeticoes.get(par, 0)
        repeticoes[par] = indice + 1
        deslocamento = (indice - (contagem_pares[par] - 1) / 2) * 18
        centro1, centro2 = y1 + altura1 / 2 + deslocamento, y2 + altura2 / 2 + deslocamento
        if x1 < x2:
            inicio, fim = (x1 + largura_no, centro1), (x2, centro2)
            tela.create_line(*inicio, *fim, arrow="last", fill=DESTAQUE, width=2, smooth=True)
            label_x = (inicio[0] + fim[0]) / 2
        elif x1 > x2:
            inicio, fim = (x1, centro1), (x2 + largura_no, centro2)
            tela.create_line(*inicio, *fim, arrow="last", fill=DESTAQUE, width=2, smooth=True)
            label_x = (inicio[0] + fim[0]) / 2
        else:
            faixa = x1 + largura_no + 18
            tela.create_line(x1 + largura_no, centro1, faixa, centro1, faixa, centro2,
                             x2 + largura_no, centro2, arrow="last", fill=DESTAQUE, width=2)
            label_x = faixa
        nome_fk = f"{campo_origem.rsplit('.', 1)[-1]} → {campo_destino.rsplit('.', 1)[-1]}"
        texto_fk = tela.create_text(label_x, (centro1 + centro2) / 2, text=nome_fk, fill=TEXTO,
                                    font=("TkFixedFont", 8), width=180, justify="center",
                                    tags=("rotulo_fk",))
        caixa_fk = tela.bbox(texto_fk)
        if caixa_fk:
            fundo_fk = _arredondado(tela, caixa_fk[0]-6, caixa_fk[1]-3,
                                     caixa_fk[2]+6, caixa_fk[3]+3,
                                     raio=5, fill=EDITOR, outline=BORDA, width=1)
            tela.tag_lower(fundo_fk, texto_fk)

    for nome in nomes:
        x, y, altura = posicoes[nome]
        _arredondado(tela, x, y, x + largura_no, y + altura, fill=PAINEL,
                     outline=BORDA, width=1, raio=12, tags=("no", f"tabela:{nome}"))
        tela.create_oval(x+14, y+14, x+22, y+22, fill=DESTAQUE, outline="")
        tela.create_text(x+32, y+11, anchor="nw", text="TABELA", fill=SUAVE,
                         font=("TkDefaultFont", 8, "bold"))
        tela.create_text(x+14, y+34, anchor="nw", width=largura_no-28,
                         text=textwrap.fill(nome, 27, break_long_words=True), fill=TEXTO,
                         font=("TkDefaultFont", 10, "bold"))
    max_nivel = max(niveis.values(), default=0)
    tela.configure(scrollregion=(0, 0, 80 + max_nivel * passo_x + largura_no, max_y + 40))


def interpretacao(pai, plano, pedido, leitura):
    botoes = ttk.Frame(pai)
    botoes.pack(fill="x", pady=(0, 10))
    corpo = ttk.Frame(pai)
    corpo.pack(fill="both", expand=True)
    relacoes = plano.get("relacionamentos_necessarios", [])

    def mostrar(pagina):
        for filho in corpo.winfo_children():
            filho.destroy()
        for botao in botoes.winfo_children():
            botao.configure(state="disabled" if botao.cget("text") == pagina else "normal")
        if pagina == "JSON completo":
            leitura(corpo, json.dumps(plano, ensure_ascii=False, indent=2))
            return
        if pagina == "Relacionamentos":
            tela = tk.Canvas(corpo, bg=EDITOR, highlightthickness=0,
                             xscrollincrement=24, yscrollincrement=24)
            vertical = ttk.Scrollbar(corpo, command=tela.yview)
            horizontal = ttk.Scrollbar(corpo, orient="horizontal", command=tela.xview)
            horizontal.pack(side="bottom", fill="x")
            vertical.pack(side="right", fill="y")
            tela.pack(fill="both", expand=True)
            tela.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
            desenhar_grafo(tela, relacoes, plano.get("tabelas_identificadas", []))
            return
        filtros = [f"{f.get('campo', f.get('chave_pedida', ''))} {f.get('operador', '')} "
                   f"{json.dumps(f.get('valor'), ensure_ascii=False, default=str)}"
                   for f in plano.get("filtros", [])]
        agrupamentos = plano.get("agrupamento", pedido.get("agrupamento", []))
        agregacoes = [f"{a.get('funcao', '')}({a.get('campo', '')})"
                      for a in plano.get("agregacoes", pedido.get("agregacoes", []))]
        itens = [
            ("Entidade solicitada", [pedido.get("entidade")]),
            ("Tabelas identificadas", plano.get("tabelas_identificadas", [])),
            ("Campos selecionados", plano.get("campos_solicitados", [])),
            ("Filtros", filtros),
            ("Relacionamentos", [f"{r.get('origem', '')} → {r.get('destino', '')}" for r in relacoes]),
            ("Agrupamentos", agrupamentos),
            ("Agregações", agregacoes),
        ]
        tela = tk.Canvas(corpo, bg=FUNDO, highlightthickness=0)
        barra = ttk.Scrollbar(corpo, command=tela.yview)
        tela.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        tela.configure(yscrollcommand=barra.set)
        cards = tk.Frame(tela, bg=FUNDO)
        janela_cards = tela.create_window((0, 0), window=cards, anchor="nw")
        conteudos = []
        for titulo, valores in itens:
            conteudo = "\n".join(str(valor) for valor in valores) if valores else "Não disponível"
            conteudos.append(_cartao(cards, titulo, conteudo, 0, 0))

        def organizar(evento):
            tela.itemconfigure(janela_cards, width=evento.width)
            colunas = 2 if evento.width < 850 else 3
            for coluna in range(3):
                cards.columnconfigure(coluna, weight=1 if coluna < colunas else 0,
                                      uniform="interpretacao" if coluna < colunas else "")
            for indice, (cartao, detalhe) in enumerate(conteudos):
                cartao.grid_configure(row=indice // colunas, column=indice % colunas,
                                      padx=(0, 8) if indice % colunas < colunas - 1 else (0, 0),
                                      pady=(0, 10), sticky="nsew")
                detalhe.configure(wraplength=max(180, int(evento.width / colunas) - 64))
            tela.configure(scrollregion=tela.bbox("all"))

        cards.bind("<Configure>", lambda _e: tela.configure(scrollregion=tela.bbox("all")), add="+")
        tela.bind("<Configure>", organizar, add="+")
        tela.bind("<MouseWheel>", lambda evento: tela.yview_scroll(int(-evento.delta / 120), "units"), add="+")

    for nome in ("Resumo", "Relacionamentos", "JSON completo"):
        ttk.Button(botoes, text=nome, command=lambda n=nome: mostrar(n)).pack(side="left", padx=(0, 8))
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
        maior = max((v for _, v in itens if v is not None and v > 0), default=0)
        for nome, valor in itens:
            linha = tk.Frame(bloco, bg=PAINEL)
            linha.pack(fill="x")
            rotulo(linha, nome).pack(side="left")
            rotulo(linha, segundos(valor) if valor is not None else "Não disponível",
                   "Legenda" if valor is not None else "Aviso").pack(side="right")
            trilho = tk.Canvas(bloco, height=8, bg=PAINEL, highlightthickness=0)
            trilho.pack(fill="x", pady=(5, 11))
            cor_barra = DESTAQUE if col == 0 else DESTAQUE_ATIVO

            def desenhar_barra(evento, canvas=trilho, atual=valor, maximo=maior, cor=cor_barra):
                canvas.delete("all")
                largura = evento.width
                if largura < 4:
                    return
                _arredondado(canvas, 0, 1, largura, 7, raio=3, fill=EDITOR, outline="")
                if atual is not None and atual > 0 and maximo > 0:
                    preenchimento = min(largura, max(6, largura * atual / maximo))
                    _arredondado(canvas, 0, 1, preenchimento, 7, raio=3, fill=cor, outline="")
            trilho.bind("<Configure>", desenhar_barra, add="+")
        if col == 0:
            detalhe = "Escala relativa à etapa mais longa"
        else:
            ollama = m.get("interpretacao", {})
            entrada = ollama.get("tokens_entrada")
            saida = ollama.get("tokens_gerados")
            detalhe = f"Tokens de entrada / saída: {entrada if entrada is not None else 'Não disponível'} / {saida if saida is not None else 'Não disponível'}"
        rotulo(bloco, detalhe, "Legenda", wraplength=330).pack(anchor="w", pady=(6, 0))

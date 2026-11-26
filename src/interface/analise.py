"""Visualizações da interpretação e das medições produzidas pelo agente."""
import json
import tkinter as tk
from tkinter import font, ttk

from src.interface.visual import (FUNDO, PAINEL, EDITOR, BORDA, SUAVE, TEXTO,
                                  DESTAQUE, DESTAQUE_ATIVO, SINTAXE, Botao, barra, painel, rotulo)


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


def janela_auxiliar(pai, titulo):
    janela = tk.Toplevel(pai)
    janela.title(titulo)
    janela.transient(pai.winfo_toplevel())
    janela.geometry(f"{min(920, pai.winfo_screenwidth()-64)}x{min(540, pai.winfo_screenheight()-90)}")
    janela.configure(bg=FUNDO)
    quadro = ttk.Frame(janela, padding=20)
    quadro.pack(fill="both", expand=True)
    janela.bind("<Escape>", lambda _: janela.destroy())
    return quadro


def desenhar_grafo(tela, relacoes, tabelas, entidade=""):
    """Cada ponta de FK tem uma porta rotulada. Cada aresta tem um corredor próprio."""
    from src.agente.relacionamentos import tabelas_mencionadas
    fonte = font.nametofont("TkDefaultFont", root=tela)
    altura = fonte.metrics("linespace") + 9
    tabelas = dict.fromkeys(tabelas)
    arestas = []
    for r in relacoes:
        a, b = r.get("origem", "").rpartition("."), r.get("destino", "").rpartition(".")
        if all((a[0], a[2], b[0], b[2])):
            arestas.append(((a[0], a[2]), (b[0], b[2])))
            tabelas.update(dict.fromkeys((a[0], b[0])))
    candidatas = tabelas_mencionadas(entidade, tabelas, entidade=True)
    principal = next(iter(candidatas)) if len(candidatas) == 1 else None
    portas = {nome: [] for nome in tabelas}
    for i, par in enumerate(arestas):
        for ponta, (nome, chave) in enumerate(par):
            portas[nome].append((i, ponta, chave))
    titulos = {nome: nome+" · Principal" if nome == principal else nome for nome in portas}
    largura = max([145] + [fonte.measure(v)+42 for nome, lista in portas.items()
                           for v in [titulos[nome], *(chave for _, _, chave in lista)]])
    margem, intervalo = 16, max(64, (len(arestas)+1)*12)
    niveis = [margem, margem + altura//2]
    pontos = {}
    # Usa duas faixas de nós. Os rótulos ficam dentro dos nós, fora das arestas.
    ordem = ([principal] if principal else []) + [nome for nome in portas if nome != principal]
    for j, nome in enumerate(ordem):
        lado = j % 2
        x, y = margem + lado*(largura+intervalo), niveis[lado]
        h = (1 + len(portas[nome])) * altura + 12
        _arredondado(tela, x, y, x+largura, y+h, raio=10, fill=PAINEL,
                     outline=DESTAQUE if nome == principal else BORDA, tags=("no",))
        tela.create_text(x+12, y+6, text=titulos[nome], fill=SINTAXE if nome == principal else TEXTO,
                         font=fonte, anchor="nw")
        for k, (i, ponta, chave) in enumerate(portas[nome], start=1):
            yp = y+6+k*altura+altura//2
            tela.create_text(x+12, yp, text=chave, anchor="w", font=fonte, fill=SUAVE, tags="rotulo_fk")
            xp = x if lado else x+largura
            pontos[i, ponta] = (xp, yp)
        niveis[lado] += h + altura - 12
    for i in range(len(arestas)):
        (x1, y1), (x2, y2) = pontos[i, 0], pontos[i, 1]
        faixa = margem + largura + (i+1)*intervalo/(len(arestas)+1)
        tela.create_line(x1, y1, faixa, y1, faixa, y2, x2, y2, arrow="last",
                         width=1.6, fill=DESTAQUE, tags="aresta")
        tela.create_oval(x1-2, y1-2, x1+2, y1+2, fill=DESTAQUE, outline="")
    limites = tela.bbox("all")
    if limites:
        def centralizar(_=None):
            x1, y1, x2, y2 = tela.bbox("all")
            w, h = x2-x1+2*margem, y2-y1+2*margem
            dx = max(0, (tela.winfo_width()-w)//2) + margem - x1
            dy = max(0, (tela.winfo_height()-h)//2) + margem - y1
            tela.move("all", dx, dy)
            tela.configure(scrollregion=(0, 0, max(w, tela.winfo_width()), max(h, tela.winfo_height())))
        centralizar()
        tela.bind("<Configure>", centralizar)


def interpretacao(pai, plano, pedido, leitura):
    quadro = painel(pai)
    quadro.pack(fill="both", expand=True)
    corpo = quadro.conteudo
    cab = tk.Frame(corpo, bg=PAINEL)
    cab.pack(fill="x", pady=(0, 8))
    rotulo(cab, "Interpretação da requisição", "Secao").pack(side="left")
    def completa():
        auxiliar = janela_auxiliar(pai, "Interpretação completa")
        leitura(auxiliar, json.dumps(plano, ensure_ascii=False, indent=2, default=str))
    Botao(cab, "Ver interpretação completa", completa, "terciario").pack(side="right")
    conteudo = tk.Frame(corpo, bg=PAINEL)
    conteudo.pack(fill="both", expand=True)
    conteudo.columnconfigure(0, weight=2, uniform="interpretacao")
    conteudo.columnconfigure(1, weight=3, uniform="interpretacao")
    conteudo.rowconfigure(0, weight=1)
    resumo = tk.Frame(conteudo, bg=PAINEL)
    resumo.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
    grafico = tk.Frame(conteudo, bg=PAINEL)
    grafico.grid(row=0, column=1, sticky="nsew")
    campos = plano.get("campos_solicitados", [])
    filtros = [f"{f.get('campo', '')} {f.get('operador', '')} {json.dumps(f.get('valor'), ensure_ascii=False, default=str)}"
               for f in plano.get("filtros", [])]
    agregacoes = [f"{a.get('funcao', '')}({a.get('campo', '')})"
                  for a in plano.get("agregacoes", pedido.get("agregacoes", []))]
    itens = [("Entidade solicitada", [pedido.get("entidade")]), ("Campos identificados", campos),
             ("Filtros aplicados", filtros), ("Agregações", agregacoes),
             ("Agrupamentos", plano.get("agrupamento", pedido.get("agrupamento", [])))]
    texto = tk.Text(resumo, bg=PAINEL, fg=TEXTO, wrap="word", font="TkDefaultFont",
                    padx=2, bd=0, width=1, height=1, highlightthickness=0)
    scroll = barra(resumo, texto.yview)
    scroll.pack(side="right", fill="y")
    texto.configure(yscrollcommand=scroll.set)
    texto.pack(fill="both", expand=True)
    texto.tag_configure("legenda", foreground=SUAVE, spacing1=6, spacing3=2)
    for nome, valores in itens:
        if valores and any(v is not None for v in valores):
            texto.insert("end", nome+"\n", "legenda")
            texto.insert("end", "\n".join(str(v) for v in valores)+"\n")
    texto.configure(state="disabled")
    rotulo(grafico, "Relacionamentos identificados", "Legenda").pack(anchor="w", pady=(4, 7))
    relacoes = plano.get("relacionamentos_necessarios", [])
    if not relacoes:
        rotulo(grafico, "Esta consulta não precisou de relacionamentos.", wraplength=300).pack(anchor="w")
        return
    tela = tk.Canvas(grafico, bg=EDITOR, width=1, height=1, highlightthickness=0)
    horizontal = barra(grafico, tela.xview, "horizontal")
    vertical = barra(grafico, tela.yview)
    horizontal.pack(side="bottom", fill="x")
    vertical.pack(side="right", fill="y")
    tela.pack(fill="both", expand=True)
    tela.configure(xscrollcommand=horizontal.set, yscrollcommand=vertical.set)
    desenhar_grafo(tela, relacoes, plano.get("tabelas_identificadas", []), pedido.get("entidade", ""))


def metricas(pai, m, aviso):
    aviso_falha = aviso.lower().startswith("aviso")
    ttk.Label(pai, text="Registro de métricas indisponível." if aviso_falha else "Métricas da execução",
              style="Aviso.TLabel" if aviso_falha else "Secao.TLabel").pack(anchor="w", pady=(0, 8))
    area = ttk.Frame(pai)
    area.pack(fill="x")
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
        bloco = bloco.conteudo
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

    detalhes = painel(pai)
    detalhes.pack(fill="x", pady=(12, 0))
    detalhes = detalhes.conteudo
    for i, (titulo, valor) in enumerate([
            ("Tempo total", segundos(m.get("tempo_total_segundos"))),
            ("Tentativas de interpretação", m.get("tentativas_interpretacao")),
            ("Tentativas SQL", m.get("tentativas_sql"))]):
        detalhes.columnconfigure(i, weight=1, uniform="tentativas")
        rotulo(detalhes, titulo).grid(row=0, column=i, sticky="w")
        rotulo(detalhes, "—" if valor is None else str(valor), "Secao").grid(row=1, column=i, sticky="w")

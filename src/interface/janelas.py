"""Interface Tk do agente. Somente a thread do mainloop acessa os widgets."""
import json
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, ttk
from pathlib import Path
import re
from src.interface.processamento import Progresso, ETAPAS, EVENTOS, ORIENTACOES
from src.interface.registros import Tabela as _tabela, gravar, escolher_exportacao

from sqlglot import Dialect
from sqlglot.errors import TokenError

from src.agente.config import OllamaConfig
from src.agente.entrada import interpretar_json


from src.interface.visual import (FUNDO, PAINEL, BORDA, TEXTO, SUAVE, DESTAQUE, ERRO, ESPACO,
                                  painel, rotulo, indicador, cabecalho, estilo, icone_ambiente)

CLAUSULAS = {"FROM", "WHERE", "GROUP_BY", "ORDER_BY", "LIMIT", "HAVING",
             "JOIN", "LEFT", "RIGHT", "INNER", "CROSS", "AND", "ON"}
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
    profundidade = 0
    projetando = True
    for token in tokens:
        separador = sql[anterior:token.start]
        tipo = token.token_type.name
        if tipo == "FROM" and profundidade == 0:
            projetando = False
        if projetando and tipo_anterior == "COMMA" and profundidade == 0 and not separador.strip():
            separador = "\n    "
        if tipo in CLAUSULAS and separador.isspace():
            if tipo != "JOIN" or tipo_anterior not in {"INNER", "LEFT", "RIGHT", "CROSS", "OUTER"}:
                separador = "\n    " if tipo in {"ON", "AND"} else "\n"
        partes.extend((separador, sql[token.start:token.end + 1]))
        anterior = token.end + 1
        tipo_anterior = tipo
        if tipo == "L_PAREN":
            profundidade += 1
        elif tipo == "R_PAREN":
            profundidade -= 1
    return "".join(partes) + sql[anterior:]


def _area(pai, numerar=False, json_editor=False):
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
            if json_editor:
                colorir(texto)
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
    texto = _area(pai, numerar=sql)
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


MODELO = {"versao": "1.0", "entidade": "<entidade>", "campos": ["<campo solicitado>"],
          "filtros": {}, "agrupamento": [], "agregacoes": []}

JSON_TOKENS = re.compile(r'("(?:\\.|[^"\\])*")\s*(:)?|\b(?:true|false|null|-?\d+(?:\.\d+)?)\b')


def colorir(texto):
    inicio = texto.index("@0,0 linestart")
    fim = texto.index(f"@0,{texto.winfo_height()} lineend")
    trecho = texto.get(inicio, fim)
    for tag in ("chave", "valor", "numero"):
        texto.tag_remove(tag, inicio, fim)
    for match in JSON_TOKENS.finditer(trecho):
        tag = "chave" if match[2] else "valor" if match[1] else "numero"
        texto.tag_add(tag, f"{inicio}+{match.start()}c", f"{inicio}+{match.end()}c")


def indentar(evento):
    texto = evento.widget
    antes = texto.get("insert linestart", "insert")
    espacos = re.match(r"\s*", antes)[0]
    if antes.rstrip().endswith(("{", "[")):
        espacos += "  "
    texto.insert("insert", "\n"+espacos)
    return "break"


class Aplicacao:
    def __init__(self, raiz, processar):
        self.raiz, self.processar = raiz, processar
        self.fila = queue.Queue()
        self.ocupada = self.fechando = False
        self.anterior = None
        raiz.title("Agente Inteligente Local")
        raiz.geometry(f"{min(1152, raiz.winfo_screenwidth()-50)}x{min(720, raiz.winfo_screenheight()-85)}")
        raiz.minsize(800, 560)
        estilo(raiz)
        self.quadro = ttk.Frame(raiz, padding=(24, 18))
        self.quadro.pack(fill="both", expand=True)
        cabecalho(self.quadro, "Agente Inteligente Local", "Assistente inteligente de consultas SQL")
        self.estado = tk.StringVar(value="Pronto para editar")
        rodape = ttk.Frame(self.quadro)
        rodape.pack(side="bottom", fill="x", pady=(12, 0))
        ttk.Label(rodape, textvariable=self.estado, style="Suave.TLabel", wraplength=450).pack(side="left")
        self.botoes = []
        self.acao = self.botao(rodape, "Executar consulta", self.executar, principal=True)
        self.acao.pack(side="right")
        corpo = ttk.Frame(self.quadro)
        corpo.pack(fill="both", expand=True)
        self.lateral = painel(corpo, width=225)
        self.lateral.pack(side="right", fill="y", padx=(14, 0))
        rotulo(self.lateral, "Ambiente da sessão", "Secao").pack(anchor="w", pady=(2, 14))
        config = OllamaConfig.from_environment()
        self.banco = os.getenv("MYSQL_DATABASE", "agente_experimental")
        self.modelo = config.model or "Não configurado"
        self.conexao = tk.StringVar(value="Não verificada")
        for nome, valor in [("Banco de dados", self.banco), ("Modelo local", self.modelo),
                            ("Conexão MySQL", None), ("Processamento", "Local"),
                            ("Acesso do agente", "Somente leitura")]:
            cartao = tk.Frame(self.lateral, bg=PAINEL)
            cartao.pack(fill="x", pady=(0, 15))
            icone_ambiente(cartao, nome).pack(side="left", anchor="n", padx=(0, 9))
            rotulo(cartao, nome, "Legenda").pack(anchor="w")
            rotulo(cartao, valor or "", "Sucesso" if nome == "Acesso do agente" else "Secao",
                   **({"textvariable": self.conexao} if valor is None else {}),
                   wraplength=178).pack(anchor="w", pady=(3, 0))
        self.centro = ttk.Frame(corpo)
        self.centro.pack(fill="both", expand=True)
        self.ambiente_btn = ttk.Button(rodape, text="Ambiente", command=self.alternar_ambiente)
        self.compacta = False
        def adaptar(evento):
            estreita = evento.width < raiz.winfo_fpixels("660p")
            if estreita != self.compacta:
                self.compacta = estreita
                if estreita:
                    self.lateral.pack_forget()
                    self.ambiente_btn.pack(side="right", padx=8)
                else:
                    self.ambiente_btn.pack_forget()
                    self.lateral.pack(side="right", before=self.centro, fill="y", padx=(14, 0))
        corpo.bind("<Configure>", adaptar)
        self.entrada = painel(self.centro)
        self.entrada.pack(fill="both", expand=True)
        topo = tk.Frame(self.entrada, bg=PAINEL)
        topo.pack(fill="x")
        rotulo(topo, "Requisição JSON", "Secao").pack(side="left")
        rotulo(topo, "Contrato v1.0", "Legenda").pack(side="right")
        rotulo(self.entrada, "Substitua os campos entre < > ou importe uma requisição.").pack(anchor="w", pady=(3, 9))
        barra = tk.Frame(self.entrada, bg=PAINEL)
        barra.pack(fill="x", pady=(0, 8))
        for nome, funcao in [("Importar JSON", self.importar), ("Formatar", self.formatar),
                             ("Validar JSON", self.validar), ("Limpar", self.limpar)]:
            self.botao(barra, nome, funcao).pack(side="left", padx=(0, 5))
        self.editor = _area(self.entrada, True, json_editor=True)
        for tag, cor in [("chave", DESTAQUE), ("valor", TEXTO), ("numero", "#B7C8ED")]:
            self.editor.tag_configure(tag, foreground=cor)
        self.editor.tag_configure("falha", underline=True, foreground=ERRO)
        self.editor.bind("<Return>", indentar)
        def atalho(acao):
            def chamar(_):
                if not self.ocupada and self.raiz.state() != "withdrawn":
                    acao()
                return "break"
            return chamar
        raiz.bind("<Control-o>", atalho(self.importar))
        raiz.bind("<Control-Shift-F>", atalho(self.formatar))
        self.editor.bind("<Control-Return>", atalho(self.executar))
        self.editor.bind("<Tab>", self._tab)
        self.editor.insert("1.0", _json(MODELO))
        self.progresso = Progresso(self.centro)
        self.erro = None
        raiz.protocol("WM_DELETE_WINDOW", self.encerrar)
        self.editor.focus_set()

    def _tab(self, _):
        self.editor.tk_focusNext().focus_set()
        return "break"

    def alternar_ambiente(self):
        if self.lateral.winfo_manager():
            self.lateral.pack_forget()
        else:
            self.lateral.pack(side="right", before=self.centro, fill="y", padx=(12, 0))

    def botao(self, pai, nome, funcao, principal=False):
        b = ttk.Button(pai, text=nome, command=funcao, style="Executar.TButton" if principal else "TButton")
        self.botoes.append(b)
        return b

    def limpar_erro(self):
        if self.erro:
            self.erro.destroy()
            self.erro = None
        self.editor.tag_remove("falha", "1.0", "end")

    def exibir_erro(self, etapa, descricao, tecnico):
        self.limpar_erro()
        self.erro = painel(self.centro)
        self.erro.pack(before=self.entrada, fill="x", pady=(0, 8))
        rotulo(self.erro, f"Falha · {ETAPAS[etapa]}", "Erro").pack(anchor="w")
        rotulo(self.erro, descricao, wraplength=470).pack(anchor="w", pady=3)
        detalhes = rotulo(self.erro, tecnico, wraplength=470)
        def alternar():
            if detalhes.winfo_manager():
                detalhes.pack_forget()
            else:
                detalhes.pack(anchor="w")
        acoes = tk.Frame(self.erro, bg=PAINEL)
        acoes.pack(anchor="w")
        ttk.Button(acoes, text="Detalhes técnicos", command=alternar).pack(side="left")
        def corrigir():
            self.limpar_erro()
            self.editor.focus_set()
        ttk.Button(acoes, text="Editar requisição", command=corrigir).pack(side="left", padx=6)
        self.estado.set("Revise a requisição para tentar novamente.")
        self.editor.focus_set()

    def trocar_texto(self, texto):
        self.limpar_erro()
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", texto)

    def limpar(self):
        self.trocar_texto("")
        self.estado.set("Editor vazio.")
        self.editor.focus_set()

    def importar(self):
        arquivo = filedialog.askopenfilename(parent=self.raiz, filetypes=[("Requisição JSON", "*.json")])
        if arquivo:
            try:
                texto = Path(arquivo).read_text(encoding="utf-8-sig")
            except (OSError, UnicodeError) as exc:
                self.exibir_erro(0, "Escolha um arquivo JSON legível em UTF-8.", type(exc).__name__)
                return
            self.trocar_texto(texto)
            self.estado.set("Arquivo importado. Valide a requisição.")

    def validar(self, apenas_formatar=False):
        self.limpar_erro()
        bruto = self.editor.get("1.0", "end-1c")
        try:
            pedido = json.loads(bruto) if apenas_formatar else interpretar_json(bruto)
        except ValueError as exc:
            try:
                json.loads(bruto)
            except json.JSONDecodeError as sintaxe:
                pos = f"{sintaxe.lineno}.{sintaxe.colno-1}"
                self.exibir_erro(0, f"JSON inválido na linha {sintaxe.lineno}, coluna {sintaxe.colno}.",
                                 "JSONDecodeError · " + sintaxe.msg)
                self.editor.tag_add("falha", f"{pos} linestart", f"{pos} lineend +1c")
                self.editor.mark_set("insert", pos)
                self.editor.see(pos)
                return None
            # O validador pode incluir valores fornecidos pelo usuário na exceção.
            dados = json.loads(bruto)
            faltam = [k for k in MODELO if isinstance(dados, dict) and k not in dados]
            descricao = ("Preencha: " + ", ".join(faltam) + ".") if faltam else ORIENTACOES[0]
            self.exibir_erro(0, descricao, "Contrato v1.0 · " + type(exc).__name__)
            return None
        self.trocar_texto(_json(pedido))
        self.estado.set("JSON formatado." if apenas_formatar else "JSON válido pelo contrato v1.0.")
        return pedido

    def formatar(self):
        self.validar(apenas_formatar=True)

    def _ocupacao(self, ativa):
        self.ocupada = ativa
        estado = "disabled" if ativa else "normal"
        self.editor.configure(state=estado)
        for botao in self.botoes:
            botao.configure(state=estado)

    def executar(self):
        if self.ocupada:
            return
        self.progresso.iniciar()
        pedido = self.validar()
        if pedido is None:
            self.progresso.finalizar(False)
            return
        self.anterior = pedido
        self.progresso.concluir_etapa()
        self.entrada.pack_forget()
        self.progresso.caixa.pack(fill="both", expand=True)
        self.conexao.set("Não verificada")
        self._ocupacao(True)

        def trabalhar():
            try:
                resultado = self.processar(pedido, lambda etapa: self.fila.put(("etapa", etapa)))
                self.fila.put(("resultado", resultado))
            except Exception as erro:
                self.fila.put(("erro", type(erro).__name__))

        threading.Thread(target=trabalhar, name="consulta-local").start()
        self.raiz.after(20, self._ler_eventos)

    def _ler_eventos(self):
        self.progresso.relogio()
        while not self.fila.empty():
            tipo, valor = self.fila.get_nowait()
            if tipo == "etapa":
                nome = valor.split(" · ")[0]
                if nome in EVENTOS:
                    self.progresso.entrar(EVENTOS[nome])
                if nome == "Descoberta da estrutura":
                    self.conexao.set("Conectada")
                if nome == "Estrutura carregada":
                    self.progresso.concluir_etapa()
                if not self.fechando:
                    self.estado.set(valor)
                continue
            self.progresso.finalizar(tipo == "resultado")
            self.progresso.caixa.pack_forget()
            self.entrada.pack(fill="both", expand=True)
            if self.conexao.get() == "Conectada":
                self.conexao.set("Sessão encerrada")
            self._ocupacao(False)
            if self.fechando:
                self.raiz.destroy()
            elif tipo == "erro":
                etapa = self.progresso.atual
                if etapa == 2:
                    self.conexao.set("Falha na conexão")
                self.exibir_erro(etapa, ORIENTACOES[etapa], f"Etapa {etapa+1} · {valor}")
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
        from src.interface.analise import segundos, interpretacao, metricas
        janela = tk.Toplevel(self.raiz)
        janela.title("Consulta concluída · Agente Inteligente Local")
        janela.geometry(self.raiz.geometry())
        janela.minsize(800, 560)
        self.raiz.withdraw()
        quadro = ttk.Frame(janela, padding=(24, 16))
        quadro.pack(fill="both", expand=True)
        total = resposta["total_registros"]
        cabecalho(quadro, "Consulta concluída", f"Consulta executada em {self.banco}  ·  "
                  + ("Nenhum registro recuperado." if not total else "Resultados disponíveis para consulta."), True)
        m = resposta["metricas"]
        cards = ttk.Frame(quadro)
        cards.pack(fill="x", pady=(0, 12))
        for i, (titulo, valor) in enumerate([
            ("Registros recuperados", total), ("Tempo da requisição", segundos(m.get("tempo_total_segundos"))),
            ("Tentativas de interpretação", m.get("tentativas_interpretacao")), ("Tentativas SQL", m.get("tentativas_sql"))
        ]):
            cards.columnconfigure(i, weight=1, uniform="resumo")
            caixa, _ = indicador(cards, titulo, "—" if valor is None else str(valor))
            caixa.grid(row=0, column=i, sticky="nsew", padx=(0, 8) if i < 3 else 0)
        rodape = ttk.Frame(quadro)
        rodape.pack(side="bottom", fill="x", pady=(10, 0))
        abas = ttk.Notebook(quadro)
        abas.pack(fill="both", expand=True)
        abas.enable_traversal()
        secoes = []
        for nome in ("Consulta SQL", "Resultados", "Interpretação", "Métricas"):
            secao = ttk.Frame(abas, padding=10)
            abas.add(secao, text=nome)
            secoes.append(secao)
        sql, tabela, plano, met = secoes
        consulta = formatar_sql(resposta["consulta_sql"])
        parametros = _json(resposta["parametros"])
        barra = ttk.Frame(sql)
        barra.pack(fill="x", pady=(0, 6))
        retorno = tk.StringVar(janela)
        ttk.Label(barra, textvariable=retorno, style="Sucesso.TLabel").pack(side="left")

        def copiar(conteudo, mensagem):
            janela.clipboard_clear()
            janela.clipboard_append(conteudo)
            retorno.set(mensagem)

        def salvar_sql():
            caminho = filedialog.asksaveasfilename(parent=janela, defaultextension=".sql", filetypes=[("SQL", "*.sql")])
            if caminho:
                try:
                    gravar(caminho, resposta["consulta_sql"], "sql")
                    retorno.set("SQL salva.")
                except OSError:
                    retorno.set("Falha ao salvar. Confira a pasta.")
        for nome, funcao in [("Salvar SQL", salvar_sql),
                             ("Copiar parâmetros", lambda: copiar(parametros, "Parâmetros copiados.")),
                             ("Copiar SQL", lambda: copiar(consulta, "SQL copiada."))]:
            ttk.Button(barra, text=nome, command=funcao).pack(side="right", padx=(6, 0))
        suporte = ttk.Panedwindow(sql, orient="vertical")
        suporte.pack(fill="both", expand=True)
        for titulo, conteudo, destaque, peso in [
            ("SQL aprovada", consulta, True, 4), ("Parâmetros", parametros, False, 1)
        ]:
            bloco = ttk.Frame(suporte)
            suporte.add(bloco, weight=peso)
            ttk.Label(bloco, text=titulo, style="Legenda.TLabel").pack(anchor="w", pady=3)
            _leitura(bloco, conteudo, destaque)
        _tabela(tabela, resposta["registros"])
        interpretacao(plano, resposta["interpretacao"], self.anterior or {}, _leitura)
        metricas(met, m, aviso)

        def voltar(nova=False):
            janela.destroy()
            self.raiz.deiconify()
            if nova:
                self.trocar_texto(_json(MODELO))
                self.estado.set("Nova requisição.")
            self.editor.focus_set()

        def exportar():
            caminho = escolher_exportacao(janela)
            if not caminho:
                return
            formato = Path(caminho).suffix.lower().lstrip(".")
            if formato not in {"csv", "json"}:
                status.set("Escolha .csv ou .json.")
                return
            exportacao.configure(state="disabled")
            status.set("Exportando…")
            eventos = queue.Queue()
            def escrever():
                try:
                    gravar(caminho, resposta["registros"], formato)
                    eventos.put("Exportação concluída.")
                except (ValueError, TypeError, OSError):
                    eventos.put("Falha ao gravar. Confira a pasta.")
            def conferir():
                if eventos.empty():
                    janela.after(60, conferir)
                else:
                    status.set(eventos.get_nowait())
                    exportacao.configure(state="normal")
            threading.Thread(target=escrever, name="exportacao-local").start()
            janela.after(60, conferir)
        ttk.Button(rodape, text="Encerrar", command=self.encerrar).pack(side="left")
        exportacao = ttk.Button(rodape, text="Exportar resultados", command=exportar)
        exportacao.pack(side="left", padx=6)
        status = tk.StringVar(janela)
        ttk.Label(rodape, textvariable=status, style="Suave.TLabel").pack(side="left")
        ttk.Button(rodape, text="Nova consulta", command=lambda: voltar(True),
                   style="Executar.TButton").pack(side="right")
        ttk.Button(rodape, text="Voltar à requisição", command=voltar).pack(side="right", padx=6)
        janela.protocol("WM_DELETE_WINDOW", voltar)
        janela.focus_set()


def abrir(processar):
    try:
        raiz = tk.Tk()
    except tk.TclError as erro:
        raise SystemExit("Não foi possível abrir a janela Tk. Verifique o ambiente gráfico ou use --cli.") from erro
    Aplicacao(raiz, processar)
    raiz.mainloop()

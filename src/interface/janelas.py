"""Interface Tk do agente. Somente a thread do mainloop acessa os widgets."""
import json
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, font, ttk
from pathlib import Path
import re
from src.interface.processamento import Progresso, ETAPAS, EVENTOS, ORIENTACOES
from src.interface.registros import Tabela as _tabela, gravar, escolher_exportacao

from sqlglot import Dialect
from sqlglot.errors import TokenError

from src.agente.config import OllamaConfig
from src.agente.entrada import interpretar_json


from src.interface.visual import (PAINEL, EDITOR, TEXTO, SUAVE, DESTAQUE, ERRO,
                                  painel, rotulo, indicador, cabecalho, estilo,
                                  FUNDO, BORDA, SINTAXE, Botao, Abas, barra as rolagem_tk, icone, truncar, dica)

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
    texto = tk.Text(quadro, bg=EDITOR, fg=TEXTO, insertbackground=DESTAQUE,
                    selectbackground="#624033", selectforeground=TEXTO,
                    font="TkFixedFont", wrap="none", borderwidth=0, padx=14, pady=12,
                    width=1, height=2, undo=numerar, highlightthickness=1,
                    highlightbackground=EDITOR, highlightcolor=BORDA)
    texto.grid(row=0, column=1, sticky="nsew")
    vertical = rolagem_tk(quadro, command=texto.yview)
    horizontal = rolagem_tk(quadro, orient="horizontal", command=texto.xview)
    vertical.grid(row=0, column=2, sticky="ns")
    horizontal.grid(row=1, column=1, sticky="ew")
    texto.configure(xscrollcommand=horizontal.set, yscrollcommand=vertical.set)
    if numerar:
        margem = tk.Canvas(quadro, width=48, bg=EDITOR, highlightthickness=0)
        margem.grid(row=0, column=0, sticky="ns")

        def desenhar(*_):
            if json_editor:
                colorir(texto)
            margem.delete("all")
            linha = int(texto.index("@0,0").split(".")[0])
            while (info := texto.dlineinfo(f"{linha}.0")) is not None:
                margem.create_text(40, info[1], text=str(linha), anchor="ne", fill="#887F7A", font="TkFixedFont")
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
        texto.tag_configure("sql", foreground=SINTAXE)
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


MODELO = {"entidade": "<entidade>", "campos": ["<campo solicitado>"],
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
        cabecalho(self.quadro, "Agente Inteligente Local", "Inteligência aplicada a bancos de dados")
        self.estado = tk.StringVar(value="Pronto para editar")
        self.botoes = []
        self.banco = os.getenv("MYSQL_DATABASE", "agente_experimental")
        self.modelo = OllamaConfig.from_environment().model or "Não configurado"
        self.conexao = tk.StringVar(value="Não verificada")
        self.centro = ttk.Frame(self.quadro)
        self.centro.pack(fill="both", expand=True)
        self.sessao = ttk.Frame(self.centro)
        self.sessao.pack(fill="x", side="bottom", pady=(12, 0))
        for i, (nome, valor, simbolo) in enumerate([
                ("Banco de dados", self.banco, "banco"), ("Modelo de inteligência", self.modelo, "modelo")]):
            self.sessao.columnconfigure(i, weight=1, uniform="ambiente")
            card = painel(self.sessao)
            card.grid(row=0, column=i, sticky="nsew", padx=(0, 6) if not i else (6, 0))
            icone(card.conteudo, simbolo, tamanho=21).pack(side="left", padx=(0, 12))
            if i:
                rotulo(card.conteudo, "Local").pack(side="right")
            else:
                estado = tk.Frame(card.conteudo, bg=PAINEL)
                estado.pack(side="right")
                rotulo(estado, "MySQL", "Legenda").pack(anchor="e")
                rotulo(estado, "", textvariable=self.conexao).pack(anchor="e")
            info = tk.Frame(card.conteudo, bg=PAINEL, width=1)
            info.pack(side="left", fill="x", expand=True)
            rotulo(info, nome).pack(anchor="w")
            detalhe = rotulo(info, truncar(valor), "Legenda", foreground=TEXTO, takefocus=True)
            detalhe.pack(anchor="w")
            dica(detalhe, valor)
            fonte = font.Font(root=raiz, font=ttk.Style(raiz).lookup("Legenda.TLabel", "font"))
            def ajustar(evento, label=detalhe, completo=valor, fonte=fonte):
                minimo, maximo = 1, len(completo)
                while minimo < maximo:
                    meio = (minimo + maximo + 1) // 2
                    if fonte.measure(truncar(completo, meio)) <= evento.width - 8:
                        minimo = meio
                    else:
                        maximo = meio - 1
                label.configure(text=truncar(completo, minimo))
            info.bind("<Configure>", ajustar)
        self.entrada = painel(self.centro)
        self.entrada.pack(fill="both", expand=True)
        topo = tk.Frame(self.entrada.conteudo, bg=PAINEL)
        topo.pack(fill="x")
        rotulo(topo, "Nova consulta", "Secao").pack(side="left")
        icone(topo, "seguro", tamanho=16).pack(side="left", padx=(16, 5))
        rotulo(topo, "Somente leitura").pack(side="left")
        rotulo(self.entrada.conteudo, "Cole uma requisição JSON ou substitua os campos entre < >.").pack(anchor="w", pady=(2, 8))
        barra = tk.Frame(self.entrada.conteudo, bg=PAINEL)
        barra.pack(fill="x", pady=(0, 8))
        for nome, funcao, simbolo in [("Importar JSON", self.importar, "importar"), ("Formatar", self.formatar, "codigo"),
                                      ("Validar", self.validar, "sucesso"), ("Limpar", self.limpar, "limpar")]:
            self.botao(barra, nome, funcao, "terciario" if nome == "Limpar" else "secundario",
                       simbolo).pack(side="left", padx=(0, 6))
        rodape = tk.Frame(self.entrada.conteudo, bg=PAINEL)
        rodape.pack(side="bottom", fill="x", pady=(10, 0))
        rotulo(rodape, "", textvariable=self.estado, wraplength=400).pack(side="left")
        self.acao = self.botao(rodape, "Executar consulta", self.executar, "primario", "executar")
        self.acao.pack(side="right")
        self.editor = _area(self.entrada.conteudo, True, json_editor=True)
        for tag, cor in [("chave", "#F59A62"), ("valor", TEXTO), ("numero", "#D7B4E8")]:
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

    def botao(self, pai, nome, funcao, tipo="secundario", simbolo=None):
        b = Botao(pai, nome, funcao, tipo, simbolo)
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
        aviso = tk.Canvas(self.erro.conteudo, width=24, height=24, bg=PAINEL, highlightthickness=0)
        aviso.pack(side="left", anchor="n", padx=(0, 10))
        aviso.create_oval(3, 3, 21, 21, outline=ERRO, width=1.5)
        aviso.create_line(12, 7, 12, 13, fill=ERRO, width=2, capstyle="round")
        aviso.create_oval(11, 16, 13, 18, fill=ERRO, outline="")
        conteudo = tk.Frame(self.erro.conteudo, bg=PAINEL)
        conteudo.pack(side="left", fill="x", expand=True)
        rotulo(conteudo, f"Falha · {ETAPAS[etapa]}", "Erro").pack(anchor="w")
        rotulo(conteudo, descricao, wraplength=650, justify="left").pack(anchor="w", pady=3)
        detalhes = rotulo(conteudo, tecnico, "Tecnico", wraplength=650, justify="left")
        def alternar():
            if detalhes.winfo_manager():
                detalhes.pack_forget()
            else:
                detalhes.pack(anchor="w")
        acoes = tk.Frame(conteudo, bg=PAINEL)
        acoes.pack(anchor="w", pady=(4, 0))
        Botao(acoes, "Detalhes técnicos", alternar, "terciario").pack(side="left")
        def corrigir():
            self.limpar_erro()
            self.editor.focus_set()
        Botao(acoes, text="Editar requisição", command=corrigir).pack(side="left", padx=6)
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
            if isinstance(dados, dict) and "versao" in dados:
                descricao = "Remova a propriedade 'versao' da requisição."
            self.exibir_erro(0, descricao, "Contrato · " + type(exc).__name__)
            return None
        self.trocar_texto(_json(pedido))
        self.estado.set("JSON formatado." if apenas_formatar else "JSON válido pelo contrato.")
        return pedido

    def formatar(self):
        self.validar(apenas_formatar=True)

    def _ocupacao(self, ativa):
        self.ocupada = ativa
        self.acao.configure(text="Processando..." if ativa else "Executar consulta")
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
        self.sessao.pack_forget()
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
            self.sessao.pack(fill="x", side="bottom", pady=(12, 0))
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
        cabecalho(quadro, "Consulta concluída", "Consulta validada e executada no banco de dados.", True)
        m = resposta["metricas"]
        plano_real = resposta["interpretacao"]
        identificadas = plano_real.get("tabelas_identificadas")
        cards = ttk.Frame(quadro)
        cards.pack(fill="x", pady=(0, 12))
        for i, (titulo, valor, simbolo, detalhe) in enumerate([
            ("Registros recuperados", str(total), "tabela", truncar(self.banco)),
            ("Tempo de execução", segundos(m.get("tempo_total_segundos")), "tempo", "Interpretação, geração e execução"),
            ("Tabelas identificadas", str(len(set(identificadas))) if identificadas is not None else "—",
             "rede", "")]):
            cards.columnconfigure(i, weight=1, uniform="resumo")
            indicador(cards, titulo, valor, simbolo, detalhe).grid(row=0, column=i, sticky="nsew",
                                                                  padx=(0, 10) if i < 2 else 0)
        rodape = ttk.Frame(quadro)
        rodape.pack(side="bottom", fill="x", pady=(10, 0))
        abas = Abas(quadro, ("Consulta SQL", "Resultados", "Interpretação"))
        abas.pack(fill="both", expand=True)
        painel_sql = painel(abas.paginas["Consulta SQL"])
        painel_sql.pack(fill="both", expand=True)
        sql = painel_sql.conteudo
        tabela, plano = abas.paginas["Resultados"], abas.paginas["Interpretação"]
        consulta = formatar_sql(resposta["consulta_sql"])
        parametros = _json(resposta["parametros"])
        barra = tk.Frame(sql, bg=PAINEL)
        barra.pack(fill="x", pady=(0, 8))
        rotulo(barra, "Consulta SQL gerada", "Secao").pack(side="left")
        retorno = tk.StringVar(janela)
        rotulo(barra, "", "Sucesso", textvariable=retorno).pack(side="left", padx=8)

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
        Botao(barra, "Copiar SQL", lambda: copiar(consulta, "SQL copiada.")).pack(side="right")
        Botao(barra, "Salvar SQL", salvar_sql, "terciario").pack(side="right", padx=6)
        params = tk.Frame(sql, bg=PAINEL)
        params.pack(side="bottom", fill="x", pady=(8, 0))
        if resposta["parametros"]:
            Botao(params, "Copiar parâmetros", lambda: copiar(parametros, "Parâmetros copiados."),
                  "terciario").pack(side="right")
            rotulo(params, "Parâmetros", "Legenda").pack(side="left", padx=(0, 8))
            texto_params = tk.Entry(params, readonlybackground=PAINEL, fg=TEXTO, relief="flat",
                                    font="TkFixedFont", width=1, highlightthickness=0)
            texto_params.pack(side="left", fill="x", expand=True)
            texto_params.insert(0, json.dumps(resposta["parametros"], ensure_ascii=False, default=str))
            texto_params.configure(state="readonly")
        else:
            rotulo(params, "Nenhum parâmetro utilizado.").pack(anchor="w")
        _leitura(sql, consulta, True)
        registros = _tabela(tabela, resposta["registros"])
        interpretacao(plano, plano_real, self.anterior or {}, _leitura)

        def detalhes():
            from src.interface.analise import janela_auxiliar
            auxiliar = janela_auxiliar(janela, "Detalhes técnicos")
            metricas(auxiliar, m, aviso)

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
        Botao(rodape, "Encerrar", self.encerrar, "terciario").pack(side="left")
        Botao(rodape, "Detalhes técnicos", detalhes, "terciario").pack(side="left", padx=6)
        exportacao = Botao(registros.rodape, "Exportar resultados", exportar)
        exportacao.pack(side="left")
        status = tk.StringVar(janela)
        rotulo(registros.rodape, "", textvariable=status).pack(side="left", padx=6)
        Botao(rodape, "Nova consulta", lambda: voltar(True), "primario", "novo").pack(side="right")
        Botao(rodape, "Voltar à requisição", voltar).pack(side="right", padx=8)
        janela.protocol("WM_DELETE_WINDOW", voltar)
        janela.focus_set()


def abrir(processar):
    try:
        raiz = tk.Tk()
    except tk.TclError as erro:
        raise SystemExit("Não foi possível abrir a janela Tk. Verifique o ambiente gráfico ou use --cli.") from erro
    Aplicacao(raiz, processar)
    raiz.mainloop()

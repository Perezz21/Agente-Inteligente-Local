"""Resolve referências no catálogo descoberto e valida a interpretação do pedido."""
import re
from collections import defaultdict

from src.agente.relacionamentos import chaves_do_catalogo, menciona, palavras, planejar_relacoes, tabelas_mencionadas

_NOME = r"[A-Za-z_]\w*"
_REFERENCIA = re.compile(rf"{_NOME}\.{_NOME}")
_PROJECAO = re.compile(
    rf"(?:(?P<funcao>AVG|SUM|MIN|MAX|COUNT)\(\s*)?"
    rf"(?P<coluna>(?:{_NOME}\.)?{_NOME})(?(funcao)\s*\))", re.IGNORECASE,
)
_TERMOS_ID = {"id", "identificador", "identificacao", "chave", "numero", "codigo",
              "identifier", "key", "number", "code"}


def _validar_papel_identificador(pedido, tabela, coluna, dados_tabela):
    termos = set(palavras(pedido)) - set(palavras(tabela))
    if coluna == "id" and not termos.intersection(_TERMOS_ID):
        raise ValueError(f"O pedido {pedido!r} não identifica a coluna {tabela}.id.")
    rotulos = termos & {"numero", "codigo", "number", "code"}
    if not rotulos:
        return
    candidatas = [c["nome"] for c in dados_tabela["colunas"] if rotulos.intersection(palavras(c["nome"]))]
    descritas = [c for c in candidatas if menciona(pedido, c)]
    opcoes = descritas or candidatas
    if opcoes and (len(opcoes) != 1 or coluna != opcoes[0].casefold()):
        raise ValueError(f"Especifique a coluna para {pedido!r}. Opções do catálogo: "
                         + ", ".join(f"{tabela}.{c}" for c in opcoes))


def resolver_mapeamento(candidato: dict, requisicao: dict, estrutura: dict) -> dict:
    """Devolve uma cópia canônica ou um diagnóstico para a próxima tentativa."""
    tabelas = estrutura.get("tabelas", {})
    if not tabelas:
        raise ValueError("Banco sem tabelas visíveis para mapear a requisição.")
    nomes = {t.casefold() for t in tabelas}
    colunas = defaultdict(list)
    for tabela, dados in tabelas.items():
        for coluna in dados["colunas"]:
            colunas[coluna["nome"].casefold()].append(f"{tabela}.{coluna['nome']}")

    tabelas_entidade = tabelas_mencionadas(requisicao["entidade"], nomes, entidade=True)
    if len(tabelas_entidade) != 1:
        tabelas_entidade.clear()

    # Reúna pistas antes de resolver o primeiro campo. A ordem do JSON e a
    # lista de tabelas sugerida pelo modelo não determinam o contexto.
    descricoes = [*requisicao["campos"], *requisicao.get("filtros", {}),
                  *requisicao.get("agrupamento", []),
                  *(a["campo"] for a in requisicao.get("agregacoes", []))]
    contexto = set(tabelas_entidade)
    for descricao in descricoes:
        if _REFERENCIA.fullmatch(descricao):
            tabela, nome = descricao.casefold().split(".")
            if any(c.casefold() == descricao.casefold() for c in colunas.get(nome, [])):
                contexto.add(tabela)
        else:
            citadas = tabelas_mencionadas(descricao, nomes)
            contexto.update(citadas)
            if not citadas:
                atributos = tabelas_mencionadas(descricao, colunas, entidade=True)
                origens = {c.split(".")[0].casefold() for atributo in atributos for c in colunas[atributo]}
                if len(origens) == 1:
                    contexto.update(origens)

    vizinhas = defaultdict(set)
    for componentes in chaves_do_catalogo(estrutura).values():
        a, b = (componentes[0][lado].split(".")[0].casefold() for lado in ("origem", "destino"))
        vizinhas[a].add(b)
        vizinhas[b].add(a)

    def resolver(campo: str, pedido: str, *, contagem=False) -> str:
        if not isinstance(campo, str):
            raise ValueError("A coluna interpretada deve ser texto.")
        abreviado = campo.rsplit(".", 1)[-1].casefold()
        opcoes = colunas.get(abreviado, [])
        chave = pedido.strip().casefold()
        if _REFERENCIA.fullmatch(chave):
            fisicas = colunas.get(chave.split(".")[1], [])
            if not any(c.casefold() == chave for c in fisicas):
                raise ValueError(f"Referência física inexistente no catálogo: {pedido!r}.")
            if campo.casefold() not in (chave, chave.split(".")[1]):
                raise ValueError(f"Para a chave explícita {pedido!r}, use a coluna {chave}.")
            opcoes = [c for c in opcoes if c.casefold() == chave]
        elif chave in colunas and chave != abreviado:
            raise ValueError(f"Coluna divergente para o campo solicitado {pedido!r}.")
        else:
            tabelas_descritas = tabelas_mencionadas(pedido, nomes)
            locais = [c for c in opcoes if c.split(".")[0].casefold() in tabelas_descritas]
            if locais:
                if len(locais) > 1:
                    raise ValueError(f"Campo ambíguo para {pedido!r}. Opções do catálogo: "
                                     + ", ".join(sorted(locais)))
                opcoes = locais
            elif tabelas_descritas and "." not in campo and not (
                set(palavras(abreviado)) & set(palavras(pedido))
            ):
                raise ValueError(f"A coluna abreviada {campo!r} não pertence à tabela "
                                 f"indicada em {pedido!r}. Verifique a referência no catálogo.")
            elif len(opcoes) > 1:
                # Um identificador genérico exige a entidade ou uma indicação
                # no próprio campo. Para outros atributos, cruze as pistas.
                ancoras = tabelas_entidade if abreviado in _TERMOS_ID else contexto
                contextual = [c for c in opcoes if c.split(".")[0].casefold() in ancoras]
                if not contextual and "." in campo and abreviado not in _TERMOS_ID:
                    # Uma sugestão qualificada só ganha apoio estrutural se a
                    # candidata ligar diretamente duas tabelas citadas no pedido.
                    contextual = [c for c in opcoes if
                                  len(vizinhas[c.split(".")[0].casefold()] & contexto) >= 2]
                if len(contextual) != 1 or (abreviado in _TERMOS_ID and chave != abreviado):
                    raise ValueError(f"Campo ambíguo para {pedido!r}. Opções do catálogo: "
                                     + ", ".join(sorted(opcoes)))
                opcoes = contextual
        if "." in campo:
            opcoes = [c for c in opcoes if c.casefold() == campo.casefold()]
        if len(opcoes) != 1:
            alternativas = ", ".join(sorted(opcoes)) or "nenhuma coluna compatível"
            raise ValueError(f"Confira {pedido!r} e a coluna {campo!r}. Opções: {alternativas}.")
        resolvida = opcoes[0]
        if contagem:
            return resolvida
        tabela = resolvida.split(".")[0]
        if not _REFERENCIA.fullmatch(chave) and chave != abreviado:
            _validar_papel_identificador(pedido, tabela, abreviado, tabelas[tabela])
        if not _REFERENCIA.fullmatch(chave) and not menciona(pedido, abreviado):
            alternativas = [f"{tabela}.{c['nome']}" for c in tabelas[tabela]["colunas"]
                            if c["nome"].casefold() != abreviado and menciona(pedido, c["nome"])]
            if alternativas:
                raise ValueError(f"Confira a coluna indicada por {pedido!r}: {', '.join(alternativas)}.")
        return resolvida

    selecionados = candidato["campos_solicitados"]
    if not selecionados:
        raise ValueError("Nenhuma coluna foi identificada para a requisição.")
    if not candidato["tabelas_identificadas"] or any(
        not isinstance(t, str) or t.casefold() not in nomes for t in candidato["tabelas_identificadas"]
    ):
        raise ValueError("Tabela não identificada ou inexistente no esquema.")
    projecoes = []
    agregacoes = {(a["funcao"].upper(), a["campo"].casefold())
                  for a in requisicao.get("agregacoes", [])}
    necessarias = set(tabelas_entidade)
    for pedido, campo in zip(requisicao["campos"], selecionados):
        expr = _PROJECAO.fullmatch(campo) if isinstance(campo, str) else None
        if not expr or expr["coluna"].split(".")[-1].casefold() not in colunas:
            raise ValueError(f"Campo solicitado inexistente ou inválido: {campo!r}.")
        funcao = (expr["funcao"] or "").upper()
        referencia = pedido
        if funcao and not _REFERENCIA.fullmatch(pedido) and pedido.casefold() not in colunas:
            # O contrato já pode identificar a coluna física para a expressão natural.
            terminal = expr["coluna"].rsplit(".", 1)[-1].casefold()
            declaradas = [c for f, c in agregacoes if f == funcao and c.split(".")[-1] == terminal]
            if len(declaradas) == 1:
                referencia = declaradas[0]
        coluna = resolver(expr["coluna"], referencia, contagem=funcao == "COUNT")
        if expr["funcao"] and (_REFERENCIA.fullmatch(pedido) or pedido.casefold() in colunas):
            if (expr["funcao"].upper(), coluna.casefold()) not in agregacoes:
                raise ValueError(f"Agregação não solicitada para a coluna explícita {pedido!r}.")
        necessarias.add(coluna.split(".")[0].casefold())
        projecoes.append(f"{expr['funcao'].upper()}({coluna})" if expr["funcao"] else coluna)
    if len(selecionados) != len(requisicao["campos"]):
        raise ValueError("Quantidade de campos interpretados difere da requisição.")

    pedidos = requisicao.get("filtros", {})
    pendentes = set(pedidos)
    filtros = []
    for filtro in candidato["filtros"]:
        if not pedidos:
            raise ValueError("O modelo criou filtros que não foram solicitados.")
        if not isinstance(filtro, dict):
            raise ValueError("Filtro com estrutura inválida.")
        chave = filtro.get("chave_pedida")
        if not isinstance(chave, str) or chave not in pendentes:
            raise ValueError("Filtro sem correspondência única com uma chave da requisição.")
        if filtro.get("operador") not in ("=", "!=", ">", ">=", "<", "<=", "ANO_IGUAL"):
            raise ValueError("Operador de filtro não suportado.")
        valor = filtro.get("valor")
        if type(valor) is not type(pedidos[chave]) or valor != pedidos[chave]:
            raise ValueError(f"Valor ou tipo alterado no filtro {chave!r}.")
        coluna = resolver(filtro.get("campo"), chave)
        filtros.append({**filtro, "campo": coluna})
        necessarias.add(coluna.split(".")[0].casefold())
        pendentes.remove(chave)

    if pendentes:
        raise ValueError(f"Filtros solicitados ausentes: {sorted(pendentes)}.")
    usadas, relacoes = planejar_relacoes(necessarias, candidato["relacionamentos_necessarios"],
                                          estrutura, requisicao)
    return {**candidato, "campos_solicitados": projecoes, "filtros": filtros,
            "tabelas_identificadas": usadas, "relacionamentos_necessarios": relacoes}


def validar_mapeamento(candidato: dict, requisicao: dict, estrutura: dict) -> str | None:
    """Compatibilidade para chamadas que só pedem a mensagem de validação."""
    try:
        resolver_mapeamento(candidato, requisicao, estrutura)
    except ValueError as exc:
        return str(exc)
    return None

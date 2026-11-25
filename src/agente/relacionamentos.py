"""Planeja ligações entre tabelas usando somente as FKs do catálogo recebido."""
import re
import unicodedata
from collections import defaultdict, deque


def palavras(texto: str) -> tuple[str, ...]:
    texto = unicodedata.normalize("NFKD", texto.casefold())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return tuple(re.findall(r"[^\W_]+", texto))


def _termos(texto):
    return tuple(p for p in palavras(texto) if p not in {"de", "do", "da", "dos", "das"})


def _plural(singular, plural):
    if singular.endswith("ao"):
        return plural in {singular[:-2] + fim for fim in ("oes", "aes", "aos")}
    if singular.endswith("m"):
        return plural == singular[:-1] + "ns"
    if singular.endswith(("r", "z", "s")):
        return plural == singular + "es"
    if singular.endswith("il"):
        return plural == singular[:-1] + "s"
    if singular.endswith("l"):
        return plural == singular[:-1] + "is"
    return plural == singular + "s"


def _ocorrencias(frase, termo):
    for i in range(len(frase) - len(termo) + 1):
        if termo and all(a == b or _plural(a, b) or _plural(b, a)
                         for a, b in zip(frase[i:], termo)):
            yield (i, i + len(termo))


def menciona(texto: str, nome: str) -> bool:
    return any(_ocorrencias(_termos(texto), _termos(nome)))


def tabelas_mencionadas(texto, nomes, *, entidade=False):
    """Uma menção composta domina só as menções contidas na mesma posição."""
    if entidade and texto.strip().casefold() in nomes:
        return {texto.strip().casefold()}
    frase = _termos(texto)
    ocorrencias = [(t, i, j) for t in nomes for i, j in _ocorrencias(frase, _termos(t))]
    if entidade:
        return {t for t, i, j in ocorrencias if i == 0 and j == len(frase)}
    return {t for t, i, j in ocorrencias if not any(
        a <= i and j <= b and (i, j) != (a, b) for _, a, b in ocorrencias
    )}


def _ocorrencias_papel(descricoes, papel):
    """Localiza o papel mesmo em nomes compostos gravados sem separador."""
    procurado = "".join(palavras(papel))
    for indice, partes in enumerate(descricoes):
        for inicio in range(len(partes)):
            trecho = ""
            for fim in range(inicio, len(partes)):
                trecho += partes[fim]
                if trecho == procurado:
                    yield (indice, inicio, fim)
                    break
                if not procurado.startswith(trecho):
                    break


def _papeis_indicados(opcoes):
    # "idioma original" especifica a ocorrência de "idioma" na mesma frase.
    # Papéis distintos em frases ou posições diferentes continuam ambíguos.
    trechos = set().union(*(pistas for _, pistas in opcoes.values()))
    especificos = {t for t in trechos if not any(
        u != t and u[0] == t[0] and u[1] <= t[1] and t[2] <= u[2] for u in trechos
    )}
    return {ch for ch, (explicita, pistas) in opcoes.items() if explicita or pistas & especificos}


def par_colunas(origem: str, destino: str) -> frozenset[str]:
    return frozenset((origem.casefold(), destino.casefold()))


def chaves_do_catalogo(estrutura: dict) -> dict:
    """Agrupa componentes da mesma FK; catálogos antigos têm FKs simples."""
    chaves = defaultdict(list)
    for relacao in estrutura.get("relacionamentos", []):
        origem, destino = relacao["origem"], relacao["destino"]
        chave = (origem.split(".")[0], relacao.get("restricao", par_colunas(origem, destino)))
        chaves[chave].append(relacao)
    visiveis = {f"{t}.{c['nome']}".casefold()
                for t, dados in estrutura.get("tabelas", {}).items() for c in dados["colunas"]}
    return {
        frozenset(par_colunas(r["origem"], r["destino"]) for r in componentes): componentes
        for componentes in chaves.values()
        if all(par_colunas(r["origem"], r["destino"]) <= visiveis for r in componentes)
    }


def _caminho(vizinhos, inicio, fim, *, permitidas=None, ignorar=None):
    """Um caminho de FKs; o chamador verifica a unicidade antes de usá-lo."""
    anteriores = {inicio: None}
    fila = deque([inicio])
    while fila:
        atual = fila.popleft()
        if atual == fim:
            caminho = []
            while atual != inicio:
                atual, chave = anteriores[atual]
                caminho.append(chave)
            return caminho
        for vizinho, chave in vizinhos[atual]:
            if vizinho in anteriores or chave == ignorar:
                continue
            if permitidas is None or chave in permitidas:
                anteriores[vizinho] = (atual, chave)
                fila.append(vizinho)
    return None


def planejar_relacoes(necessarias: set[str], propostas: list, estrutura: dict, requisicao: dict):
    """Liga campos, filtros e entidade. Uma proposta do LLM sozinha não desfaz empates."""
    chaves = chaves_do_catalogo(estrutura)
    declarados = set()
    for par in propostas:
        if not isinstance(par, dict) or not all(isinstance(par.get(k), str) for k in ("origem", "destino")):
            raise ValueError("Relacionamento sem origem ou destino qualificado.")
        declarados.add(par_colunas(par["origem"], par["destino"]))
    if declarados - set().union(*chaves):
        raise ValueError("Relacionamento inexistente no esquema.")

    termos = [*requisicao["campos"], *requisicao.get("filtros", {})]
    termos.extend(requisicao.get("agrupamento", []))
    termos.extend(a["campo"] for a in requisicao.get("agregacoes", []))
    referencias = {t.strip().casefold() for t in termos}
    # Uma referência física aponta a coluna, não necessariamente o papel da tabela
    # do outro lado. Use a descrição natural apenas entre tabelas efetivamente pedidas.
    descricoes = [palavras(t) for t in termos if "." not in t]
    vizinhos = defaultdict(list)
    extremos = {}
    papeis = defaultdict(dict)
    for chave, componentes in chaves.items():
        primeiro = componentes[0]
        a, b = (primeiro[k].split(".")[0].casefold() for k in ("origem", "destino"))
        extremos[chave] = (a, b)
        vizinhos[a].append((b, chave))
        vizinhos[b].append((a, chave))
        if a == b or not {a, b} <= necessarias:
            continue
        explicita = False
        pistas = set()
        for relacao in componentes:
            origem = relacao["origem"].casefold()
            coluna = origem.split(".")[1]
            papel = coluna.removesuffix("_id").removeprefix("id_")
            if origem in referencias:
                explicita = True
            if papel != coluna:
                pistas.update(_ocorrencias_papel(descricoes, papel))
        papeis[frozenset((a, b))][chave] = (explicita, pistas)

    permitidas = set()
    for opcoes in papeis.values():
        indicadas = _papeis_indicados(opcoes)
        if len(indicadas) == 1:
            permitidas.update(indicadas)

    # Dentro das tabelas efetivamente pedidas, uma cadeia de FKs com papéis
    # coerentes pode estar completa mesmo se outra rota sair desse conjunto.
    internas = {ch for ch, (a, b) in extremos.items() if {a, b} <= necessarias}
    for ch in internas - permitidas:
        a, b = extremos[ch]
        if a == b or _caminho(vizinhos, a, b, permitidas=internas, ignorar=ch) is not None:
            continue
        # Exija uma terceira âncora na componente e o papel da tabela destino
        # na chave de origem. Proximidade por si só não identifica um papel.
        papel_neutro = any(
            _termos(r["origem"].casefold().split(".")[1].removeprefix("id_").removesuffix("_id"))
            == _termos(b) for r in chaves[ch]
        )
        terceira_ancora = any(t not in (a, b) and t in necessarias
                              for ponta in (a, b) for t, _ in vizinhos[ponta])
        if papel_neutro and terceira_ancora:
            permitidas.add(ch)

    principais = tabelas_mencionadas(requisicao["entidade"], necessarias, entidade=True)
    inicio = next(iter(principais)) if len(principais) == 1 else min(necessarias)
    destinos = sorted(necessarias - {inicio})
    candidatas = set()
    for fim in destinos:
        caminho = _caminho(vizinhos, inicio, fim)
        if caminho is None:
            raise ValueError(f"Sem caminho de chaves estrangeiras entre {inicio} e {fim}.")
        candidatas.update(caminho)
    # Toda ligação obrigatória está em qualquer caminho entre os extremos.
    # Remover essa FK desconecta suas tabelas. Uma FK composta é uma única aresta.
    for chave in candidatas - permitidas:
        a, b = extremos[chave]
        if _caminho(vizinhos, a, b, ignorar=chave) is None:
            permitidas.add(chave)

    usadas = set()
    for fim in destinos:
        caminho = _caminho(vizinhos, inicio, fim, permitidas=permitidas)
        if caminho is None or any(
            _caminho(vizinhos, inicio, fim, permitidas=permitidas, ignorar=ch) is not None
            for ch in caminho
        ):
            raise ValueError(f"Caminho ambíguo entre {inicio} e {fim}. Especifique o papel ou a coluna da FK.")
        usadas.update(caminho)
    if declarados - set().union(*usadas):
        raise ValueError("JOIN adicional ou divergente do caminho solicitado.")
    for chave in usadas:
        if chave & declarados and not chave <= declarados:
            raise ValueError("Chave estrangeira composta incompleta na interpretação.")

    tabelas = necessarias.union(*(extremos[ch] for ch in usadas))
    return (
        [t for t in estrutura["tabelas"] if t.casefold() in tabelas],
        [{k: r[k] for k in ("origem", "destino")}
         for ch, componentes in chaves.items() if ch in usadas for r in componentes],
    )

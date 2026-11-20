"""Valida mapeamentos produzidos pelo modelo contra o esquema descoberto."""

import re
from typing import Any


_CAMPO = re.compile(
    r"^(?:(?:AVG|SUM|MIN|MAX|COUNT)\()?([A-Za-z_]\w*\.[A-Za-z_]\w*)\)?$",
    re.IGNORECASE,
)


def validar_mapeamento(
    candidato: dict[str, Any], requisicao: dict, estrutura: dict
) -> str | None:
    """Retorna uma mensagem de erro ou None, sem presumir nomes de tabelas."""
    tabelas = estrutura.get("tabelas", {})
    if not tabelas:
        return None  # Compatibilidade com testes unitários sem esquema real.

    disponiveis = {
        f"{tabela}.{coluna['nome']}".casefold()
        for tabela, dados in tabelas.items()
        for coluna in dados.get("colunas", [])
    }
    nomes = {nome.casefold() for nome in tabelas}
    selecionados = candidato["campos_solicitados"]
    if not selecionados:
        return "Nenhuma coluna foi identificada para a requisição."

    colunas_selecionadas = []
    for campo in selecionados:
        if not isinstance(campo, str):
            return "Campo solicitado deve ser texto no formato tabela.coluna."
        correspondencia = _CAMPO.fullmatch(campo.replace(" ", ""))
        if not correspondencia or correspondencia.group(1).casefold() not in disponiveis:
            return f"Campo solicitado inexistente ou não qualificado: {campo!r}."

        colunas_selecionadas.append(correspondencia.group(1))

    for tabela in candidato["tabelas_identificadas"]:
        if not isinstance(tabela, str) or tabela.casefold() not in nomes:
            return f"Tabela não existente no esquema: {tabela!r}."

    if not candidato["tabelas_identificadas"]:
        return "Nenhuma tabela identificada."

    # Um filtro não pedido não deve ser introduzido pelo modelo.
    if not requisicao.get("filtros") and candidato["filtros"]:
        return "O modelo criou filtros que não foram solicitados."

    pedidos = requisicao.get("filtros", {})
    pendentes = set(pedidos)

    def corresponde_ao_identificador(pedido: str, coluna: str) -> bool:
        # Um identificador físico fornecido pelo usuário tem precedência.
        nome = pedido.strip().casefold()
        if re.fullmatch(r"[\w]+\.[\w]+", nome):
            return coluna.casefold() == nome
        if nome in nomes_colunas:
            return coluna.rsplit(".", 1)[-1].casefold() == nome
        return True  # Termo conceitual: a resolução semântica cabe ao modelo.

    nomes_colunas = {nome.rsplit(".", 1)[-1] for nome in disponiveis}
    for filtro in candidato["filtros"]:
        if not isinstance(filtro, dict):
            return "Filtro com estrutura inválida."
        campo = filtro.get("campo")
        operador = filtro.get("operador")
        if not isinstance(campo, str) or campo.casefold() not in disponiveis:
            return f"Coluna de filtro inexistente: {campo!r}."
        if operador not in ("=", "!=", ">", ">=", "<", "<=", "ANO_IGUAL"):
            return "Operador de filtro não suportado."
        if "valor" not in filtro:
            return "Filtro sem valor."

        origem = filtro.get("chave_pedida")
        if not isinstance(origem, str) or origem not in pendentes:
            return "Filtro sem correspondência única com uma chave da requisição."
        esperado = pedidos[origem]
        recebido = filtro["valor"]
        if type(recebido) is not type(esperado) or recebido != esperado:
            return f"Valor ou tipo alterado no filtro {origem!r}."
        if not corresponde_ao_identificador(origem, campo):
            return f"Coluna divergente para o filtro {origem!r}."
        pendentes.remove(origem)

    if pendentes:
        return f"Filtros solicitados ausentes: {sorted(pendentes)}."

    conhecidos = {
        frozenset((r["origem"].casefold(), r["destino"].casefold()))
        for r in estrutura.get("relacionamentos", [])
    }
    for relacao in candidato["relacionamentos_necessarios"]:
        if not isinstance(relacao, dict):
            return "Relacionamento com estrutura inválida."
        origem, destino = relacao.get("origem"), relacao.get("destino")
        if not isinstance(origem, str) or not isinstance(destino, str):
            return "Relacionamento sem origem ou destino."
        if frozenset((origem.casefold(), destino.casefold())) not in conhecidos:
            return "Relacionamento inexistente no esquema."

    # Evita interpretações que copiam todas as colunas do catálogo.
    campos_pedidos = requisicao.get("campos")
    if isinstance(campos_pedidos, list) and campos_pedidos:
        if len(selecionados) != len(campos_pedidos):
            return (
                "Quantidade de campos interpretados difere da requisição: "
                f"{len(selecionados)} em vez de {len(campos_pedidos)}."
            )

        for pedido, coluna in zip(campos_pedidos, colunas_selecionadas):
            if not corresponde_ao_identificador(pedido, coluna):
                return f"Coluna divergente para o campo solicitado {pedido!r}."

    return None

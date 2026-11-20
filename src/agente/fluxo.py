"""Fluxo reutilizável do agente: interpretação, SQL e consulta MySQL."""

import json
from time import perf_counter
from typing import Any

from src.agente.interpretacao import completar_interpretacao
from src.agente.esquema_interpretacao import ESQUEMA_INTERPRETACAO
from src.agente.validacao_mapeamento import validar_mapeamento
from src.agente.sql_generator import SQLGenerator, SQLGenerationError


def montar_prompt(requisicao: dict, estrutura: dict) -> str:
    """Prompt compacto: metadados são referências, não campos a devolver."""
    catalogo = {
        nome: [coluna["nome"] for coluna in dados.get("colunas", [])]
        for nome, dados in estrutura.get("tabelas", {}).items()
    }
    relacionamentos = estrutura.get("relacionamentos", [])
    return (
        "TAREFA: interpretar APENAS a REQUISICAO abaixo para MySQL.\n"
        "O CATALOGO é um inventário de tabelas e colunas, NÃO é a resposta.\n"
        "Não liste todas as tabelas ou colunas do catálogo.\n"
        "Para cada campo pedido, escolha uma coluna existente no formato "
        "tabela.coluna; para agregações use FUNCAO(tabela.coluna).\n"
        "Use só as tabelas necessárias, sem filtros ou JOINs adicionais.\n"
        "O campo status será 'ambiguo' se não for possível mapear.\n"
        "Retorne somente o JSON de interpretação com as chaves "
        "tabelas_identificadas, campos_solicitados, filtros, "
        "relacionamentos_necessarios, status e observacoes.\n"
        "Formato dos filtros: {campo, operador, valor}. "
        "Formato dos JOINs: {origem, destino}.\n"
        "CATALOGO (não copiar para a resposta):\n"
        + json.dumps(
            {"tabelas_colunas": catalogo, "relacionamentos": relacionamentos},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\nREQUISICAO DO USUARIO (objetivo prioritário):\n"
        + json.dumps(requisicao, ensure_ascii=False, separators=(",", ":"))
        + "\nResponda somente ao objetivo da REQUISICAO, nunca descreva o CATALOGO."
    )


def executar_requisicao(
    requisicao: dict[str, Any],
    estrutura: dict[str, Any],
    modelo: Any,
    banco: Any,
) -> dict[str, Any]:
    """Executa uma requisição JSON com dependências já inicializadas.

    O banco deve estar conectado. A função não faz input/print nem encerra
    a conexão, permitindo execução automatizada e testes com mocks.
    """
    inicio = perf_counter()
    prompt = montar_prompt(requisicao, estrutura)
    obrigatorios = {
        "tabelas_identificadas",
        "campos_solicitados",
        "filtros",
        "relacionamentos_necessarios",
        "status",
        "observacoes",
    }
    interpretacao = None
    erro_interpretacao = "O modelo não retornou JSON válido."
    resultado_modelo = None
    tentativas_interpretacao = 0
    for tentativa in range(1, 3):
        tentativas_interpretacao = tentativa
        prompt_tentativa = prompt
        if tentativa > 1:
            prompt_tentativa += (
                "\nA interpretação anterior foi rejeitada: "
                + erro_interpretacao
                + "\nRefaça somente o mapeamento solicitado, "
                "usando nomes qualificados tabela.coluna do catálogo."
            )
        resultado_modelo = modelo.generate(
            prompt=prompt_tentativa,
            max_tokens=1200,
            json_mode=True,
            json_schema=ESQUEMA_INTERPRETACAO,
        )
        try:
            candidato = json.loads(resultado_modelo.content)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(candidato, dict):
            erro_interpretacao = "A interpretação deve ser um objeto JSON."
            continue
        faltantes = obrigatorios - candidato.keys()
        if faltantes:
            erro_interpretacao = (
                f"Campos obrigatórios ausentes na interpretação: {sorted(faltantes)}"
            )
            continue
        if not (
            isinstance(candidato["tabelas_identificadas"], list)
            and isinstance(candidato["campos_solicitados"], list)
            and isinstance(candidato["filtros"], list)
            and isinstance(candidato["relacionamentos_necessarios"], list)
            and isinstance(candidato["status"], str)
            and isinstance(candidato["observacoes"], str)
        ):
            erro_interpretacao = "Tipos inválidos na interpretação JSON."
            continue
        if candidato["status"] != "sucesso":
            observacoes = candidato["observacoes"].strip()
            erro_interpretacao = (
                f"Interpretação com status {candidato['status']!r}."
                + (f" Motivo informado: {observacoes[:500]}" if observacoes else
                   " O modelo não informou uma justificativa.")
            )
            continue
        erro_mapeamento = validar_mapeamento(candidato, requisicao, estrutura)
        if erro_mapeamento is not None:
            erro_interpretacao = erro_mapeamento
            continue
        interpretacao = candidato
        break

    if interpretacao is None:
        raise ValueError(erro_interpretacao + " Após 2 tentativas.")

    interpretacao = completar_interpretacao(
        requisicao, interpretacao, estrutura
    )
    fim_interpretacao = perf_counter()

    gerador = SQLGenerator(modelo)
    try:
        consulta = gerador.generate(
            interpretacao=interpretacao, estrutura=estrutura
        )
    except SQLGenerationError as erro:
        # Diagnóstico seguro: mostra mapeamentos, sem expor valores de filtros.
        tabelas = interpretacao.get("tabelas_identificadas", [])
        campos = interpretacao.get("campos_solicitados", [])
        filtros = [
            item.get("campo") for item in interpretacao.get("filtros", [])
            if isinstance(item, dict)
        ]
        raise SQLGenerationError(
            f"{erro}\nInterpretação recebida pelo gerador:"
            f"\nTabelas: {tabelas!r}"
            f"\nCampos: {campos!r}"
            f"\nColunas dos filtros: {filtros!r}"
        ) from erro
    fim_geracao_sql = perf_counter()

    registros = banco.execute_select(
        consulta=consulta["consulta_sql"],
        parametros=consulta["parametros"],
    )
    fim_execucao = perf_counter()

    return {
        "interpretacao": interpretacao,
        "consulta_sql": consulta["consulta_sql"],
        "parametros": consulta["parametros"],
        "registros": registros,
        "total_registros": len(registros),
        "metricas": {
            "tempo_total_segundos": fim_execucao - inicio,
            "tempo_interpretacao_segundos": fim_interpretacao - inicio,
            "tempo_geracao_sql_segundos": fim_geracao_sql - fim_interpretacao,
            "tempo_execucao_mysql_segundos": fim_execucao - fim_geracao_sql,
            "tentativas_sql": consulta.get("tentativas_sql"),
            "tentativas_interpretacao": tentativas_interpretacao,
            "interpretacao": {
                "carregamento_segundos": resultado_modelo.load_seconds,
                "processamento_prompt_segundos": (
                    resultado_modelo.prompt_eval_seconds
                ),
                "geracao_segundos": resultado_modelo.generation_seconds,
                "tokens_entrada": resultado_modelo.prompt_tokens,
                "tokens_gerados": resultado_modelo.generated_tokens,
            },
        },
    }

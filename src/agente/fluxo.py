"""Fluxo reutilizável do agente: interpretação, SQL e consulta MySQL."""

import json
from time import perf_counter

from jsonschema import Draft202012Validator
from typing import Any

from src.agente.interpretacao import completar_interpretacao
from src.agente.contrato_requisicao import compactar_requisicao_validada, validar_requisicao
from src.agente.esquema_interpretacao import ESQUEMA_INTERPRETACAO
from src.agente.validacao_mapeamento import resolver_mapeamento
from src.agente.sql_generator import SQLGenerator, SQLGenerationError


_FORMATO = Draft202012Validator(ESQUEMA_INTERPRETACAO)


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
        "FILTROS SÃO OPCIONAIS: ausência de filtros significa consultar todos "
        "os registros correspondentes, não é ambiguidade.\n"
        "Se não houver filtros na requisição, retorne filtros: [] e "
        "NÃO invente condições WHERE.\n"
        "Se o campo pedido tiver correspondência clara no catálogo, retorne "
        "status sucesso mesmo sem um valor ou filtro específico.\n"
        "Use status ambiguo somente se não conseguir escolher uma coluna "
        "ou relacionamento com segurança.\n"
        "O campo status será 'ambiguo' se não for possível mapear.\n"
        "Retorne somente o JSON de interpretação com as chaves "
        "tabelas_identificadas, campos_solicitados, filtros, "
        "relacionamentos_necessarios, status e observacoes.\n"
        "Mantenha os campos na ordem do pedido e respeite identificadores explícitos. "
        "Mapeie cada chave de filtros exatamente uma vez, preservando valor e tipo. "
        "Formato dos filtros: {chave_pedida, campo, operador, valor}. "
        "Copie chave_pedida literalmente da requisição. Em campo escreva sempre "
        "tabela.coluna, inclusive para filtros. Se a chave pedida já nomeia "
        "uma coluna qualificada do catálogo, preserve essa referência. Se o "
        "termo puder identificar várias colunas, explique a ambiguidade. "
        "Use as FKs do catálogo, incluindo as tabelas intermediárias necessárias. "
        "Para uma chave estrangeira composta, inclua todos os pares da restrição. "
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
    *, progresso: dict | None = None,
) -> dict[str, Any]:
    """Executa uma requisição JSON com dependências já inicializadas.

    O banco deve estar conectado. A função não faz input/print nem encerra
    a conexão, permitindo execução automatizada e testes com mocks.
    """
    return _executar_requisicao_validada(
        validar_requisicao(requisicao), estrutura, modelo, banco, progresso=progresso
    )


def _executar_requisicao_validada(
    requisicao: dict[str, Any], estrutura: dict[str, Any], modelo: Any, banco: Any,
    *, progresso: dict | None = None, notificar=None,
) -> dict[str, Any]:
    """Uso interno após a validação da entrada."""
    if progresso is None:
        progresso = {}
    progresso["etapa"] = "interpretacao"
    inicio = perf_counter()
    requisicao = compactar_requisicao_validada(requisicao)
    prompt = montar_prompt(requisicao, estrutura)
    obrigatorios = set(ESQUEMA_INTERPRETACAO["required"])
    interpretacao = None
    erro_interpretacao = "O modelo não retornou JSON válido."
    resultado_modelo = None
    tentativas_interpretacao = 0
    for tentativa in range(1, 3):
        tentativas_interpretacao = tentativa
        progresso["tentativas_interpretacao"] = tentativa
        prompt_tentativa = prompt
        if tentativa > 1:
            prompt_tentativa += (
                "\nA interpretação anterior foi rejeitada: "
                + erro_interpretacao
                + "\nRefaça somente o mapeamento solicitado, "
                "usando nomes qualificados tabela.coluna do catálogo. Para um filtro, "
                "conserve chave_pedida, operador e valor. Se o pedido não "
                "distinguir as opções, use status ambiguo e indique a dúvida."
            )
        if notificar:
            notificar(f"Interpretação da requisição · tentativa {tentativa}")
        resultado_modelo = modelo.generate(
            prompt=prompt_tentativa,
            max_tokens=1200,
            json_mode=True,
            json_schema=ESQUEMA_INTERPRETACAO,
        )
        try:
            candidato = json.loads(resultado_modelo.content)
        except (json.JSONDecodeError, TypeError):
            erro_interpretacao = "O modelo não retornou JSON válido."
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
        try:
            candidato = resolver_mapeamento(candidato, requisicao, estrutura, notificar=notificar)
            erro_formato = next(_FORMATO.iter_errors(candidato), None)
            if erro_formato is not None:
                caminho = ".".join(map(str, erro_formato.absolute_path)) or "raiz"
                raise ValueError(f"Formato inesperado no campo {caminho} da interpretação.")
            interpretacao = completar_interpretacao(requisicao, candidato, estrutura)
        except ValueError as erro:
            erro_interpretacao = str(erro)
            continue
        break

    if interpretacao is None:
        raise ValueError(erro_interpretacao + " Após 2 tentativas.")

    fim_interpretacao = perf_counter()

    progresso.update(etapa="geracao_sql", tempo_interpretacao_segundos=fim_interpretacao - inicio)
    if notificar:
        notificar("Geração e validação SQL")
    gerador = SQLGenerator(modelo)
    try:
        consulta = gerador.generate(
            interpretacao=interpretacao, estrutura=estrutura
        )
    except SQLGenerationError as erro:
        progresso.update(etapa=erro.etapa, tentativas_sql=erro.tentativas_sql,
                         sql_sintaticamente_valida=erro.sintaxe)
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
            f"\nColunas dos filtros: {filtros!r}",
            etapa=erro.etapa, sintaxe=erro.sintaxe, tentativas_sql=erro.tentativas_sql,
        ) from erro
    fim_geracao_sql = perf_counter()

    progresso.update(etapa="execucao_mysql", sql_aprovada=True, sql_sintaticamente_valida=True,
                     tentativas_sql=consulta.get("tentativas_sql"),
                     tempo_geracao_sql_segundos=fim_geracao_sql - fim_interpretacao)
    if notificar:
        notificar("Execução da consulta")
    registros = banco.execute_select(
        consulta=consulta["consulta_sql"],
        parametros=consulta["parametros"],
    )
    fim_execucao = perf_counter()

    progresso.update(consulta_executada=True, tempo_execucao_mysql_segundos=fim_execucao - fim_geracao_sql)

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

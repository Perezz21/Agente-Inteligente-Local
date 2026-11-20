"""Fluxo reutilizável do agente: interpretação, SQL e consulta MySQL."""

import json
from time import perf_counter
from typing import Any

from src.agente.interpretacao import completar_interpretacao
from src.agente.sql_generator import SQLGenerator


def montar_prompt(requisicao: dict, estrutura: dict) -> str:
    """Prepara as instruções para interpretação da requisição."""

    return f"""
Você é um componente especializado em interpretar requisições
estruturadas para consultas a bancos de dados relacionais.

Sua tarefa é analisar a requisição e identificar como seus campos
e filtros correspondem às tabelas e colunas existentes no banco.

REGRAS OBRIGATÓRIAS:

1. Utilize exclusivamente tabelas e colunas presentes no esquema.
2. Identifique os campos solicitados com seus nomes completos,
   no formato tabela.coluna.
3. Relacione cada filtro à coluna que representa semanticamente
   seu conteúdo.
4. Não associe valores textuais diretamente a campos numéricos.
5. Quando um filtro representar o nome de uma entidade, utilize
   a coluna de nome correspondente, mesmo que seja necessário
   estabelecer um relacionamento entre tabelas.
6. Não converta nomes em IDs. Essa conversão não faz parte
   desta etapa.
7. Para filtros de ano, utilize o campo de data correspondente
   e o operador ANO_IGUAL.
8. Identifique os relacionamentos necessários utilizando
   exclusivamente as chaves estrangeiras disponíveis.
9. Não invente tabelas, colunas ou relacionamentos.
10. Não gere SQL.
11. Se não houver informação suficiente, indique a ambiguidade
    no campo observacoes e utilize status "ambiguo".

EXEMPLO DE MAPEAMENTO:

Se a requisição solicitar medições do município Jataí em 2025,
e o banco possuir:
- medicoes.municipio_id
- medicoes.data_medicao
- municipios.id
- municipios.nome

O mapeamento correto dos filtros será:

"filtros": [
    {{
        "campo": "municipios.nome",
        "operador": "=",
        "valor": "Jataí"
    }},
    {{
        "campo": "medicoes.data_medicao",
        "operador": "ANO_IGUAL",
        "valor": 2025
    }}
]

O relacionamento necessário será:

"origem": "medicoes.municipio_id",
"destino": "municipios.id"

FORMATO OBRIGATÓRIO DA RESPOSTA:

Retorne exclusivamente um objeto JSON válido, sem Markdown,
sem blocos de código e sem explicações fora do JSON.

O objeto deve possuir exatamente estas propriedades:

{{
    "tabelas_identificadas": [],
    "campos_solicitados": [],
    "filtros": [],
    "relacionamentos_necessarios": [],
    "status": "sucesso",
    "observacoes": ""
}}

REQUISIÇÃO:
{json.dumps(requisicao, ensure_ascii=False, indent=2)}

ESTRUTURA DO BANCO:
{json.dumps(estrutura, ensure_ascii=False, indent=2)}
"""



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
        resultado_modelo = modelo.generate(
            prompt=prompt,
            max_tokens=1200,
            json_mode=True,
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
        interpretacao = candidato
        break

    if interpretacao is None:
        raise ValueError(erro_interpretacao + " Após 2 tentativas.")

    interpretacao = completar_interpretacao(
        requisicao, interpretacao, estrutura
    )
    fim_interpretacao = perf_counter()

    gerador = SQLGenerator(modelo)
    consulta = gerador.generate(
        interpretacao=interpretacao, estrutura=estrutura
    )
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

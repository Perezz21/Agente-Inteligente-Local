
"""Teste de integração entre o agente, Ollama e MySQL."""

import json
from src.agente.sql_generator import (
    SQLGenerator,
    SQLGenerationError,
)
from src.agente.config import OllamaConfig
from src.agente.database import DatabaseClient
from src.agente.entrada import receber_json
from src.agente.ollama_client import (
    OllamaModelClient,
    OllamaModelError,
)


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


def main():
    banco = DatabaseClient()

    try:
        config = OllamaConfig.from_environment()
        modelo = OllamaModelClient(config)

        modelos_disponiveis = modelo.check_connection()

        if config.model not in modelos_disponiveis:
            raise OllamaModelError(
                f"Modelo não encontrado: {config.model}"
            )

        print(f"Modelo local: {config.model}")

        banco.connect()
        print("Conexão com MySQL estabelecida.")

        estrutura = banco.get_database_structure()

        print(
            f"Estrutura carregada: "
            f"{len(estrutura['tabelas'])} tabelas e "
            f"{len(estrutura['relacionamentos'])} relacionamentos."
        )

        requisicao = receber_json()

        prompt = montar_prompt(requisicao, estrutura)

        print("\nEnviando requisição ao modelo local...")

        resultado = modelo.generate(
            prompt=prompt,
            max_tokens=500
        )

        print("\n" + "=" * 50)
        print("INTERPRETAÇÃO DO AGENTE")
        print("=" * 50)

        try:
            resposta = json.loads(resultado.content)

            campos_obrigatorios = {
                "tabelas_identificadas",
                "campos_solicitados",
                "filtros",
                "relacionamentos_necessarios",
                "status",
                "observacoes",
            }

            if not isinstance(resposta, dict):
                raise ValueError("A resposta não é um objeto JSON.")

            faltantes = campos_obrigatorios - resposta.keys()

            if faltantes:
                raise ValueError(
                    f"Campos ausentes na resposta: {faltantes}"
                )

            print(
                json.dumps(
                    resposta,
                    ensure_ascii=False,
                    indent=4
                )
            )

            print("\nJSON validado com sucesso!")

            # 7. Gerar consulta SQL
            print("\nGerando consulta SQL...")

            gerador_sql = SQLGenerator(modelo)

            consulta = gerador_sql.generate(
                interpretacao=resposta,
                estrutura=estrutura,
            )

            print("\n" + "=" * 50)
            print("CONSULTA SQL GERADA")
            print("=" * 50)

            print(consulta["consulta_sql"])

            print("\nPARÂMETROS")
            print("=" * 50)

            print(
                json.dumps(
                    consulta["parametros"],
                    ensure_ascii=False,
                    indent=4
                )
            )

            print("\nConsulta SQL validada com sucesso!")

            # 8. Executar consulta no MySQL
            print("\nExecutando consulta no MySQL...")

            registros = banco.execute_select(
                consulta=consulta["consulta_sql"],
                parametros=consulta["parametros"],
            )

            print("\n" + "=" * 50)
            print("RESULTADOS DA CONSULTA")
            print("=" * 50)

            print(
                json.dumps(
                    registros,
                    ensure_ascii=False,
                    indent=4,
                    default=str
                )
            )

            print(f"\nTotal de registros recuperados: {len(registros)}")

        except (json.JSONDecodeError, ValueError) as erro:
            print(f"\nA resposta do modelo não passou na validação: {erro}")
            print("\nResposta original:")
            print(resultado.content)

        print("\nMÉTRICAS DA EXECUÇÃO")
        print("=" * 50)
        print(f"Carregamento: {resultado.load_seconds:.2f} s")
        print(f"Processamento do prompt: {resultado.prompt_eval_seconds:.2f} s")
        print(f"Geração: {resultado.generation_seconds:.2f} s")
        print(f"Tokens de entrada: {resultado.prompt_tokens}")
        print(f"Tokens gerados: {resultado.generated_tokens}")

    except (OllamaModelError, ValueError) as erro:
        print(f"\nErro: {erro}")

    except Exception as erro:
        print(f"\nErro inesperado: {erro}")

    finally:
        banco.close()


if __name__ == "__main__":
    main()

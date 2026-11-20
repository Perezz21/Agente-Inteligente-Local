"""Executor sequencial de cenários JSON para experimentos locais.

Uso: python -m src.executar_experimentos --arquivo experiments/cenarios_exemplo.json --repeticoes 2
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from src.agente.avaliacao import avaliar_resultados
from src.agente.contrato_requisicao import validar_requisicao
from src.agente.config import OllamaConfig
from src.agente.database import DatabaseClient
from src.agente.fluxo import executar_requisicao
from src.agente.ollama_client import OllamaModelClient
from src.agente.registro_metricas import CAMINHO_PADRAO, registrar_execucao


def carregar_cenarios(caminho: Path) -> list[dict]:
    """Aceita uma lista de objetos com id único e requisicao estruturada."""
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    if not isinstance(dados, list) or not dados:
        raise ValueError("O arquivo deve conter uma lista não vazia de cenários.")

    vistos = set()
    cenarios = []
    for item in dados:
        if not isinstance(item, dict):
            raise ValueError("Cada cenário deve ser um objeto JSON.")
        identificador = item.get("id")
        requisicao = item.get("requisicao")
        if not isinstance(identificador, str) or not identificador.strip():
            raise ValueError("Todo cenário precisa de um id textual não vazio.")
        if identificador in vistos:
            raise ValueError("IDs de cenários repetidos não são permitidos.")
        if not isinstance(requisicao, dict) or not requisicao:
            raise ValueError("Cada cenário precisa de uma requisicao JSON não vazia.")
        requisicao = validar_requisicao(requisicao)
        vistos.add(identificador)
        esperado = item.get("resultado_esperado")
        if "resultado_esperado" in item:
            if not isinstance(esperado, list) or not all(
                isinstance(linha, dict) for linha in esperado
            ):
                raise ValueError("resultado_esperado deve ser lista de objetos.")
        ordem_importa = item.get("ordem_importa", False)
        if not isinstance(ordem_importa, bool):
            raise ValueError("ordem_importa deve ser booleano.")
        colunas_referencia = item.get("colunas_referencia")
        if colunas_referencia is not None:
            if (
                not isinstance(colunas_referencia, dict)
                or not colunas_referencia
                or not all(
                    isinstance(chave, str) and chave
                    and isinstance(valor, str) and valor
                    for chave, valor in colunas_referencia.items()
                )
                or len(set(colunas_referencia.values())) != len(colunas_referencia)
            ):
                raise ValueError("colunas_referencia inválidas.")
            if esperado is None:
                raise ValueError("colunas_referencia exige resultado_esperado.")
        cenarios.append({
            "id": identificador,
            "requisicao": requisicao,
            "resultado_esperado": esperado,
            "ordem_importa": ordem_importa,
            "colunas_referencia": colunas_referencia,
        })
    return cenarios


def executar_cenarios(
    cenarios: list[dict],
    repeticoes: int,
    modelo,
    banco,
    estrutura: dict,
    destino: Path = CAMINHO_PADRAO,
    rodada_id: str | None = None,
) -> dict:
    """Executa cenários em sequência; registra sucesso e falha sem dados sensíveis."""
    if not isinstance(repeticoes, int) or not 1 <= repeticoes <= 100:
        raise ValueError("Repetições devem estar entre 1 e 100.")

    resumo = {
        "sucessos": 0, "falhas": 0,
        "corretos": 0, "incorretos": 0, "nao_avaliados": 0,
    }
    destino = Path(destino)
    if rodada_id is None:
        rodada_id = uuid4().hex
    if not isinstance(rodada_id, str) or not rodada_id.strip():
        raise ValueError("Identificador da rodada inválido.")

    for cenario in cenarios:
        for numero in range(1, repeticoes + 1):
            print(f"\nCenário {cenario['id']} — repetição {numero}/{repeticoes}")
            inicio = perf_counter()
            try:
                resposta = executar_requisicao(
                    cenario["requisicao"], estrutura, modelo, banco
                )
                esperado = cenario.get("resultado_esperado")
                avaliacao = (
                    avaliar_resultados(
                        resposta["registros"], esperado,
                        ordem_importa=cenario.get("ordem_importa", False),
                        consulta_sql=resposta.get("consulta_sql"),
                        colunas_referencia=cenario.get("colunas_referencia"),
                    )
                    if esperado is not None else None
                )
                registrar_execucao(
                    resposta, modelo.model, cenario["id"], destino,
                    repeticao=numero, avaliacao=avaliacao,
                    rodada_id=rodada_id,
                )
                resumo["sucessos"] += 1
                if avaliacao is None:
                    resumo["nao_avaliados"] += 1
                    print("Resultado: sucesso (sem referência)")
                elif avaliacao["correto"]:
                    resumo["corretos"] += 1
                    print("Resultado: sucesso, dados corretos")
                else:
                    resumo["incorretos"] += 1
                    print("Resultado: sucesso, dados INCORRETOS")
            except Exception as exc:
                # O texto da exceção pode conter valores de filtros, SQL ou dados.
                # Registrar somente a categoria da falha, não sua mensagem.
                falha = {
                    "data_hora_utc": datetime.now(timezone.utc).isoformat(),
                    "modelo": modelo.model,
                    "cenario": cenario["id"],
                    "repeticao": numero,
                    "rodada_id": rodada_id,
                    "status": "falha",
                    "tipo_erro": type(exc).__name__,
                    "tempo_total_segundos": perf_counter() - inicio,
                }
                destino.parent.mkdir(parents=True, exist_ok=True)
                with destino.open("a", encoding="utf-8") as arquivo:
                    arquivo.write(json.dumps(falha, ensure_ascii=False) + "\n")
                resumo["falhas"] += 1
                print(f"Resultado: falha ({type(exc).__name__})")

    return resumo


def main() -> None:
    parser = argparse.ArgumentParser(description="Executar cenários locais em sequência.")
    parser.add_argument(
        "--arquivo", required=True, type=Path,
        help="Arquivo JSON com lista de cenários."
    )
    parser.add_argument("--repeticoes", type=int, default=1)
    parser.add_argument("--validar", action="store_true",
                        help="Validar cenários sem executar Ollama ou MySQL.")
    args = parser.parse_args()

    try:
        cenarios = carregar_cenarios(args.arquivo)
        if args.validar:
            com_referencia = sum(
                item["resultado_esperado"] is not None for item in cenarios
            )
            print(
                f"Cenários válidos: {len(cenarios)}; "
                f"com referência: {com_referencia}; "
                f"pendentes: {len(cenarios) - com_referencia}."
            )
            return
        if not 1 <= args.repeticoes <= 100:
            raise ValueError("Repetições devem estar entre 1 e 100.")
        config = OllamaConfig.from_environment()
        modelo = OllamaModelClient(config)
        if config.model not in modelo.check_connection():
            raise RuntimeError("Modelo configurado não está disponível no Ollama.")

        rodada_id = uuid4().hex
        print(f"Rodada experimental: {rodada_id}")
        banco = DatabaseClient()
        try:
            banco.connect()
            estrutura = banco.get_database_structure()
            resumo = executar_cenarios(
                cenarios, args.repeticoes, modelo, banco, estrutura,
                rodada_id=rodada_id,
            )
        finally:
            banco.close()

        print(f"\nResumo: {resumo['sucessos']} sucessos e {resumo['falhas']} falhas.")
        print(
            f"Avaliação: {resumo['corretos']} corretos, "
            f"{resumo['incorretos']} incorretos e "
            f"{resumo['nao_avaliados']} sem referência."
        )
        print(f"Registros: {CAMINHO_PADRAO}")
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        # Evita exibir a mensagem, que pode conter dados inseridos.
        print(f"Falha na preparação dos experimentos: {type(exc).__name__}")


if __name__ == "__main__":
    main()

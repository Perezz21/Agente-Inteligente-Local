"""Executor sequencial de cenários JSON para experimentos locais.

Uso: python -m src.executar_experimentos --arquivo experiments/cenarios_exemplo.json --repeticoes 2
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

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
        vistos.add(identificador)
        cenarios.append({"id": identificador, "requisicao": requisicao})
    return cenarios


def executar_cenarios(
    cenarios: list[dict],
    repeticoes: int,
    modelo,
    banco,
    estrutura: dict,
    destino: Path = CAMINHO_PADRAO,
) -> dict:
    """Executa cenários em sequência; registra sucesso e falha sem dados sensíveis."""
    if not isinstance(repeticoes, int) or not 1 <= repeticoes <= 100:
        raise ValueError("Repetições devem estar entre 1 e 100.")

    resumo = {"sucessos": 0, "falhas": 0}
    destino = Path(destino)

    for cenario in cenarios:
        for numero in range(1, repeticoes + 1):
            print(f"\nCenário {cenario['id']} — repetição {numero}/{repeticoes}")
            inicio = perf_counter()
            try:
                resposta = executar_requisicao(
                    cenario["requisicao"], estrutura, modelo, banco
                )
                registrar_execucao(
                    resposta, modelo.model, cenario["id"], destino, repeticao=numero
                )
                resumo["sucessos"] += 1
                print("Resultado: sucesso")
            except Exception as exc:
                # O texto da exceção pode conter valores de filtros, SQL ou dados.
                # Registrar somente a categoria da falha, não sua mensagem.
                falha = {
                    "data_hora_utc": datetime.now(timezone.utc).isoformat(),
                    "modelo": modelo.model,
                    "cenario": cenario["id"],
                    "repeticao": numero,
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
    args = parser.parse_args()

    try:
        cenarios = carregar_cenarios(args.arquivo)
        if not 1 <= args.repeticoes <= 100:
            raise ValueError("Repetições devem estar entre 1 e 100.")
        config = OllamaConfig.from_environment()
        modelo = OllamaModelClient(config)
        if config.model not in modelo.check_connection():
            raise RuntimeError("Modelo configurado não está disponível no Ollama.")

        banco = DatabaseClient()
        try:
            banco.connect()
            estrutura = banco.get_database_structure()
            resumo = executar_cenarios(
                cenarios, args.repeticoes, modelo, banco, estrutura
            )
        finally:
            banco.close()

        print(f"\nResumo: {resumo['sucessos']} sucessos e {resumo['falhas']} falhas.")
        print(f"Registros: {CAMINHO_PADRAO}")
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        # Evita exibir a mensagem, que pode conter dados inseridos.
        print(f"Falha na preparação dos experimentos: {type(exc).__name__}")


if __name__ == "__main__":
    main()

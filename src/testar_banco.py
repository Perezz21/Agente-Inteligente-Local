"""Teste de conexão e identificação da estrutura do banco MySQL."""

import json

from src.agente.database import DatabaseClient


def main():
    banco = DatabaseClient()

    try:
        print("Tentando conectar ao MySQL...")

        banco.connect()

        print("Conexão estabelecida com sucesso!")

        print("\nRecuperando estrutura completa do banco...")

        estrutura = banco.get_database_structure()

        print("\nESTRUTURA DO BANCO")
        print("=" * 50)

        print(
            json.dumps(
                estrutura,
                indent=4,
                ensure_ascii=False
            )
        )

        print("\nRESUMO")
        print("=" * 50)

        print(f"Banco: {estrutura['banco']}")
        print(f"Tabelas: {len(estrutura['tabelas'])}")
        print(
            f"Relacionamentos: "
            f"{len(estrutura['relacionamentos'])}"
        )

    except Exception as erro:
        print(f"\nErro: {erro}")

    finally:
        banco.close()


if __name__ == "__main__":
    main()

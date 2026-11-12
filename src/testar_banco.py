
from src.agente.database import DatabaseClient


def main():
    banco = DatabaseClient()

    try:
        print("Tentando conectar ao MySQL...")

        banco.connect()

        print("Conexão estabelecida com sucesso!")

        cursor = banco.connection.cursor()
        cursor.execute("SELECT DATABASE()")
        resultado = cursor.fetchone()
        cursor.close()

        print(f"Banco conectado: {resultado[0]}")

        print("\nIdentificando estrutura do banco...")

        esquema = banco.get_schema()

        for tabela, colunas in esquema.items():
            print(f"\nTabela: {tabela}")

            for coluna in colunas:
                print(
                    f"  - {coluna['nome']} "
                    f"({coluna['tipo']}) "
                    f"[Chave: {coluna['chave'] or 'Não'}]"
                )

        print("\nTotal de tabelas identificadas:", len(esquema))

    except Exception as erro:
        print(f"Erro: {erro}")

    finally:
        banco.close()


if __name__ == "__main__":
    main()

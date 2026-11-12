
"""Gerenciamento da conexão com o banco de dados MySQL."""

import mysql.connector
from mysql.connector import MySQLConnection


class DatabaseClient:
    """Cliente responsável pela conexão com o MySQL."""

    def __init__(self) -> None:
        self.connection: MySQLConnection | None = None

    def connect(self) -> None:
        """Estabelece conexão com o banco experimental."""

        self.connection = mysql.connector.connect(
            host="localhost",
            port=3306,
            user="root",
            password="rootroot",
            database="agente_experimental",
        )

    def get_schema(self) -> dict:
        """Recupera as tabelas e colunas do banco de dados."""

        if not self.connection or not self.connection.is_connected():
            raise RuntimeError(
                "Não existe uma conexão ativa com o MySQL."
            )

        cursor = self.connection.cursor(dictionary=True)

        try:
            cursor.execute(
                """
                SELECT
                    TABLE_NAME,
                    COLUMN_NAME,
                    COLUMN_TYPE,
                    IS_NULLABLE,
                    COLUMN_KEY
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s
                ORDER BY TABLE_NAME, ORDINAL_POSITION
                """,
                ("agente_experimental",),
            )

            colunas = cursor.fetchall()
            esquema = {}

            for coluna in colunas:
                tabela = coluna["TABLE_NAME"]

                if tabela not in esquema:
                    esquema[tabela] = []

                esquema[tabela].append({
                    "nome": coluna["COLUMN_NAME"],
                    "tipo": coluna["COLUMN_TYPE"],
                    "permite_nulo": coluna["IS_NULLABLE"],
                    "chave": coluna["COLUMN_KEY"],
                })

            return esquema

        finally:
            cursor.close()

    def close(self) -> None:
        """Encerra a conexão com o banco."""

        if self.connection and self.connection.is_connected():
            self.connection.close()
            self.connection = None

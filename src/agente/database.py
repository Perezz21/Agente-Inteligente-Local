
"""Gerenciamento da conexão com o banco de dados MySQL."""

import os

import mysql.connector
import sqlglot
from mysql.connector import MySQLConnection
from sqlglot import exp

from src.agente.config import load_local_environment


class DatabaseClient:
    """Cliente responsável pela conexão com o MySQL."""

    def __init__(self) -> None:
        self.connection: MySQLConnection | None = None

    def connect(self) -> None:
        """Estabelece conexão com o banco experimental."""

        load_local_environment()

        usuario = os.getenv("MYSQL_USER")
        senha = os.getenv("MYSQL_PASSWORD")
        banco = os.getenv("MYSQL_DATABASE", "agente_experimental")
        host = os.getenv("MYSQL_HOST", "localhost")
        porta = os.getenv("MYSQL_PORT", "3306")

        if not usuario or not senha:
            raise RuntimeError(
                "Configure MYSQL_USER e MYSQL_PASSWORD no ambiente. "
                "Utilize uma conta MySQL somente de leitura."
            )

        try:
            porta_numero = int(porta)
        except ValueError as exc:
            raise RuntimeError("MYSQL_PORT deve ser um número inteiro.") from exc

        if not 1 <= porta_numero <= 65535:
            raise RuntimeError("MYSQL_PORT fora da faixa permitida.")

        self.connection = mysql.connector.connect(
            host=host,
            port=porta_numero,
            user=usuario,
            password=senha,
            database=banco,
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
                (os.getenv("MYSQL_DATABASE", "agente_experimental"),),
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

    def get_relationships(self) -> list[dict]:
        """Identifica os relacionamentos entre as tabelas."""

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
                    CONSTRAINT_NAME,
                    ORDINAL_POSITION,
                    REFERENCED_TABLE_NAME,
                    REFERENCED_COLUMN_NAME
                FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = %s
                  AND REFERENCED_TABLE_SCHEMA = TABLE_SCHEMA
                  AND REFERENCED_TABLE_NAME IS NOT NULL
                ORDER BY TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION
                """,
                (os.getenv("MYSQL_DATABASE", "agente_experimental"),),
            )

            return cursor.fetchall()

        finally:
            cursor.close()

    def get_database_structure(self) -> dict:
        """Retorna a estrutura completa do banco de dados."""

        esquema = self.get_schema()
        relacionamentos = self.get_relationships()

        tabelas = {}

        for nome_tabela, colunas in esquema.items():
            tabelas[nome_tabela] = {
                "colunas": colunas
            }

        estrutura = {
            "banco": os.getenv("MYSQL_DATABASE", "agente_experimental"),
            "tabelas": tabelas,
            "relacionamentos": [
                {
                    "restricao": relacao["CONSTRAINT_NAME"],
                    "posicao": relacao["ORDINAL_POSITION"],
                    "origem": (
                        f"{relacao['TABLE_NAME']}."
                        f"{relacao['COLUMN_NAME']}"
                    ),
                    "destino": (
                        f"{relacao['REFERENCED_TABLE_NAME']}."
                        f"{relacao['REFERENCED_COLUMN_NAME']}"
                    )
                }
                for relacao in relacionamentos
            ]
        }

        return estrutura

    def execute_select(
        self,
        consulta: str,
        parametros: list | None = None,
    ) -> list[dict]:
        """Executa uma consulta SELECT parametrizada e retorna os registros."""

        if not self.connection or not self.connection.is_connected():
            raise RuntimeError(
                "Não existe uma conexão ativa com o MySQL."
            )

        # Defesa adicional: não confia apenas na validação do gerador.
        # A proteção principal é a conta MySQL com privilégios SELECT.
        if not isinstance(consulta, str) or not consulta.strip():
            raise ValueError("Consulta SQL vazia ou inválida.")

        sql = consulta.strip()
        if ";" in sql or "--" in sql or "/*" in sql or "#" in sql:
            raise ValueError("Comentários e múltiplas instruções não permitidos.")

        try:
            instrucoes = sqlglot.parse(
                sql.replace("%s", "NULL"), read="mysql"
            )
        except Exception as exc:
            raise ValueError("Consulta SQL inválida.") from exc

        if len(instrucoes) != 1 or not isinstance(instrucoes[0], exp.Select):
            raise ValueError("Somente consultas SELECT são permitidas.")

        arvore = instrucoes[0]
        proibidos = (
            exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create,
            exp.Alter, exp.Command, exp.Union, exp.Intersect, exp.Except,
        )
        if any(isinstance(no, proibidos) for no in arvore.walk()):
            raise ValueError("Consulta contém operação não autorizada.")

        if arvore.args.get("into") is not None or arvore.args.get("locks"):
            raise ValueError("SELECT INTO e bloqueios não são permitidos.")

        if any(isinstance(no, exp.Select) for no in arvore.walk() if no is not arvore):
            raise ValueError("Subconsultas ainda não são permitidas.")

        cursor = self.connection.cursor(dictionary=True)
        try:
            cursor.execute(consulta, tuple(parametros or []))
            return cursor.fetchall()
        finally:
            cursor.close()

    def close(self) -> None:
        """Encerra a conexão com o banco."""

        if self.connection and self.connection.is_connected():
            self.connection.close()
            self.connection = None

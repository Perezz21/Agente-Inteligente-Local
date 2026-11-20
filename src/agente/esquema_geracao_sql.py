"""Formato da resposta SQL do modelo, independente do banco conectado."""

ESQUEMA_GERACAO_SQL = {
    "type": "object",
    "properties": {
        "consulta_sql": {"type": "string"},
        "parametros": {
            "type": "array",
            "items": {"type": ["string", "integer", "number", "boolean", "null"]},
        },
    },
    "required": ["consulta_sql", "parametros"],
    "additionalProperties": False,
}

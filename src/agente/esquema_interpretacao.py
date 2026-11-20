"""Contrato de saída estruturada para a etapa de interpretação do agente.

Independente do esquema de qualquer banco MySQL. Não confundir com o
futuro contrato versionado do JSON de entrada.
"""

ESQUEMA_INTERPRETACAO = {
    "type": "object",
    "properties": {
        "tabelas_identificadas": {
            "type": "array", "items": {"type": "string"}
        },
        "campos_solicitados": {
            "type": "array", "items": {"type": "string"}
        },
        "filtros": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "chave_pedida": {"type": "string"},
                    "campo": {"type": "string"},
                    "operador": {"type": "string"},
                    "valor": {"type": ["string", "integer", "number", "boolean", "null"]},
                },
                "required": ["chave_pedida", "campo", "operador", "valor"],
                "additionalProperties": False,
            },
        },
        "relacionamentos_necessarios": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "origem": {"type": "string"},
                    "destino": {"type": "string"},
                },
                "required": ["origem", "destino"],
                "additionalProperties": False,
            },
        },
        "status": {"type": "string", "enum": ["sucesso", "ambiguo"]},
        "observacoes": {"type": "string"},
    },
    "required": [
        "tabelas_identificadas", "campos_solicitados", "filtros",
        "relacionamentos_necessarios", "status", "observacoes",
    ],
    "additionalProperties": False,
}

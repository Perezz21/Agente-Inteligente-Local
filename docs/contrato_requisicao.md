# Contrato obrigatório de entrada JSON

O agente recebe **uma requisição JSON estruturada**. O formato é independente do
modelo de banco de dados: nenhuma tabela ou coluna do Sakila, do banco ambiental
ou de outro banco é exigida no código para aceitar um pedido.

A fonte única do padrão é
[`schemas/requisicao.schema.json`](../schemas/requisicao.schema.json).
A validação acontece em `src/agente/contrato_requisicao.py`, **antes de conectar
ao Ollama ou ao MySQL**. Requisições com propriedades ausentes, extras ou tipos
incorretos são recusadas.

## Requisição válida

```json
{
  "entidade": "filmes",
  "campos": ["título do filme"],
  "filtros": {},
  "agrupamento": [],
  "agregacoes": []
}
```

As **cinco propriedades são obrigatórias**, mesmo que `filtros`,
`agrupamento` e `agregacoes` estejam vazios.

| Propriedade | Formato | O que informa |
| --- | --- | --- |
| `entidade` | texto não vazio | Assunto da requisição em linguagem natural |
| `campos` | lista não vazia de textos | Campos desejados descritos pelo usuário |
| `filtros` | objeto com chaves livres e valores simples | Critérios de consulta; `{}` para todos os registros |
| `agrupamento` | lista de `tabela.coluna` | Agrupamentos, ou `[]` |
| `agregacoes` | lista de objetos `{funcao, campo}` | `AVG`, `SUM`, `MIN`, `MAX`, `COUNT`, ou `[]` |

As propriedades de `filtros` são livres (por exemplo, `titulo`, `ano`
ou `municipio`). O validador **não escolhe tabelas ou colunas**;
apenas verifica a estrutura. Em seguida, o agente descobre o banco conectado,
interpreta os termos, gera SQL, valida e executa consultas somente de leitura.

**Limitação atual:** `agrupamento` e `agregacoes[*].campo` ainda exigem
referências físicas `tabela.coluna`. Isso não fixa nenhum
nome no código, mas exige que quem forneça essas operações conheça esses
identificadores. Torná-los semânticos também é uma evolução planejada.

## Requisições rejeitadas

```json
{"entidade": "filmes", "campos": ["título do filme"]}
```

Faltam `filtros`, `agrupamento` e `agregacoes`.

```json
{
  "entidade": "filmes",
  "campos": ["título do filme"],
  "filtros": {},
  "agrupamento": [],
  "agregacoes": [],
  "sql": "SELECT * FROM filme"
}
```

A propriedade `sql` não pertence ao contrato e é rejeitada. SQL não é
recebido do usuário; é produzido e validado internamente pelo agente.

## Como executar

Instale as dependências após atualizar o projeto:

```powershell
python -m pip install -r requirements.txt
```

Rode a consulta:

```powershell
python -m src.main --arquivo experiments/requisicao_sakila_filmes.json
```

Também é possível executar `python -m src.main` e colar o JSON válido.

Os arquivos de `experiments/cenarios_*.json` contêm listas de cenários, e
cada `requisicao` dentro da lista deve obedecer a esse mesmo contrato.

## Separação arquitetural

- **JSON externo:** descreve a intenção do usuário, conforme o JSON Schema.
- **Interpretação interna do modelo:** identifica colunas e relacionamentos
  existentes no banco conectado.
- **Geração SQL interna:** constrói e valida um SELECT e seus parâmetros.

O mesmo contrato vale para o terminal, arquivos, cenários experimentais e chamadas Python a `executar_requisicao`. O nome do arquivo é livre.

A validação do formato não garante a correção semântica do mapeamento: a
interpretação, a geração SQL e os resultados ainda precisam ser avaliados
com testes reais em diferentes bancos.

Não inclua credenciais nem comandos SQL em arquivos de requisição.

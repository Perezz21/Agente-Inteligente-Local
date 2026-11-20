# Contrato de requisição JSON v1.0

O agente recebe um **único arquivo JSON por consulta**. Os nomes de tabelas e
colunas são descobertos automaticamente pelo MySQL durante a execução.

## Formato obrigatório para requisições v1.0

```json
{
  "versao": "1.0",
  "entidade": "filmes",
  "campos": ["título do filme"],
  "filtros": {},
  "agrupamento": [],
  "agregacoes": []
}
```

As **seis propriedades são obrigatórias** na versão 1.0, mesmo quando
`filtros`, `agrupamento` e `agregacoes` estão vazios.

| Propriedade | Tipo | Significado |
| --- | --- | --- |
| `versao` | string | Contrato de entrada; atualmente `"1.0"` |
| `entidade` | string não vazia | Assunto da consulta, como `"filmes"` ou `"medições"` |
| `campos` | lista não vazia de strings | Atributos descritos em linguagem natural |
| `filtros` | objeto | Condições semânticas como `"municipio": "Jataí"` e `"ano": 2025` |
| `agrupamento` | lista | Colunas de agrupamento `tabela.coluna`; `[]` quando não há |
| `agregacoes` | lista | Objetos `{"funcao": "AVG", "campo": "tabela.coluna"}` |

As funções atualmente suportadas são `AVG`, `SUM`, `MIN`, `MAX` e
`COUNT`. Cada objeto de agregação deve conter exatamente `funcao` e
`campo`. O validador rejeita tipos incorretos, versões desconhecidas,
campos obrigatórios ausentes e propriedades extras. A versão 1.0 ainda
exige referências físicas `tabela.coluna` para agregações e agrupamentos:
a interpretação totalmente semântica dessas duas operações é uma melhoria
futura, não uma capacidade que já tenha sido implementada.

**Atenção:** os nomes de filtros não são fixados para um banco específico.
O agente é responsável por interpretar as chaves semânticas de acordo com
o esquema descoberto. A validação do contrato garante a **estrutura** do
JSON, não a exatidão semântica do modelo.

## Exemplo com filtros

```json
{
  "versao": "1.0",
  "entidade": "medições",
  "campos": ["data da medição", "vazão", "nome do município"],
  "filtros": {"municipio": "Jataí", "ano": 2025},
  "agrupamento": [],
  "agregacoes": []
}
```

## Execução

Com `MYSQL_DATABASE=sakila` no `.env`:

```powershell
python -m src.main --arquivo experiments/requisicao_sakila_filmes_v1.json
```

Ou forneça um arquivo próprio com as mesmas seis propriedades.

## Compatibilidade e evolução

- Requisições antigas **sem** a propriedade `versao` continuam aceitas,
  preservando os cenários experimentais existentes.
- A validação e a normalização estão centralizadas em
  `src/agente/contrato_requisicao.py`.
- Um JSON v1.0 validado é convertido internamente ao formato usado pelo
  agente, sem os campos vazios e sem `versao`. Isso evita afetar os prompts
  e a geração SQL já testados.
- Ao criar v2, um novo contrato poderá ser implementado e despachado pelo
  campo `versao`, com os contratos anteriores mantidos.
- O JSON de **entrada** é diferente do JSON interno de **interpretação**
  do modelo e do JSON interno de **geração SQL**.
- O arquivo de cenários experimentais contém uma *lista de cenários*
  com `id` e `requisicao`; cada `requisicao` pode utilizar o contrato v1.0.

Não envie senhas, credenciais nem instruções SQL no JSON de entrada.

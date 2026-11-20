# Proposta do contrato de entrada — v1 (ainda não aplicado ao agente)

Este documento descreve o **próximo passo**, depois de validar a interpretação
estruturada no banco Sakila. Não altera o formato já aceito pelo agente.

Objetivos:
- Um único contrato para bancos diferentes, sem nomes de tabelas fixos no código.
- Compatibilidade com as requisições já usadas nos cenários.
- Uma versão explícita para futuras migrações (`versao`).
- Validar tipos e campos de entrada antes de chamar o Ollama.

Exemplo proposto (ainda **não obrigatório**):

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

Na v1, `entidade` é um texto conceitual informado pelo usuário,
`campos` é uma lista não vazia de textos, `filtros` é um objeto com
chaves semânticas e valores JSON, `agrupamento` é uma lista de
referências `tabela.coluna` (quando presente), e `agregacoes` é uma
lista de objetos com `funcao` e `campo`. O modelo consulta o esquema
do banco conectado para resolver os campos conceituais.

Importante: `filtros` hoje é um dicionário flexível; impor chaves fixas
como `municipio` ou `rio` tornaria o agente dependente de um banco.
O contrato deve validar o *formato*, não exigir um vocabulário único
para os bancos.

**Não colocar instruções SQL ou credenciais na entrada.** O SQL é
gerado e validado pelo agente, não fornecido pelo usuário.

## Antes de tornar obrigatório

1. Validar no Ollama local que a etapa de interpretação agora retorna JSON.
2. Definir regras de tipos, campos opcionais e versão na validação central.
3. Adaptar cenários antigos com compatibilidade retroativa ou migração
   explícita; preservar as referências e logs antigos.
4. Criar testes para JSON v1 válido e inválido, inclusive entrada de outros bancos.

O JSON de interpretação do Ollama e o JSON de saída da consulta são
contratos **diferentes** deste JSON de entrada.

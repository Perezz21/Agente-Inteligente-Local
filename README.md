# Agente Inteligente Local

Projeto de Trabalho de Conclusão de Curso em Ciência da Computação (UFJ).

O objetivo é desenvolver um agente local em Python que recebe requisições estruturadas em JSON, interpreta seus parâmetros, realiza o mapeamento semântico com o esquema de um banco de dados relacional, gera e valida consultas SQL e recupera os registros solicitados.

## Escopo atual

- Receber requisições estruturadas em JSON.
- Interpretar os parâmetros recebidos.
- Relacionar os parâmetros às tabelas e colunas do banco.
- Gerar e validar consultas SQL.
- Executar consultas de leitura no MySQL.
- Retornar os registros recuperados.

A conversão de linguagem natural para JSON, a criação de gráficos e a interface visual não fazem parte do agente.

## Tecnologias previstas

- Python
- Ollama para execução local dos modelos de linguagem
- MySQL

As bibliotecas e os modelos serão definidos e avaliados durante o desenvolvimento.

## Primeira etapa

A primeira etapa implementa somente a comunicação entre Python e o Ollama. A conexão com o MySQL e o processamento das requisições serão adicionados gradualmente.

## Requisitos

- Python 3.10 ou superior
- Ollama instalado
- Pelo menos um modelo baixado no Ollama

## Preparação

```bash
python -m venv .venv
```

No Windows:

```powershell
.venv\Scripts\activate
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

Baixe um modelo no Ollama, por exemplo:

```bash
ollama pull qwen3.5:4b
```

Defina o modelo que será utilizado:

No PowerShell:

```powershell
$env:OLLAMA_MODEL="qwen3.5:4b"
```

Execute:

```bash
python -m src.main
```

O nome do modelo é configurável. Isso permitirá testar diferentes modelos sem alterar o código do agente.

## Execução local

O programa utiliza o serviço local do Ollama em `http://localhost:11434`. O código não implementa chamadas a APIs de IA na nuvem. O download inicial dos modelos exige internet; depois de instalados, podem ser executados localmente.

## Documentação

As decisões de arquitetura, os critérios de avaliação dos modelos, os testes e os resultados serão registrados em `docs/` conforme o desenvolvimento avançar.

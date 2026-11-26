# Agente Inteligente Local

Projeto de Trabalho de Conclusão de Curso em Ciência da Computação (UFJ).

O objetivo é desenvolver um agente local em Python que recebe requisições estruturadas em JSON, interpreta seus parâmetros, realiza o mapeamento semântico com o esquema de um banco de dados relacional, gera e valida consultas SQL e recupera os registros solicitados.

## Contrato obrigatório do JSON de entrada

O agente **não possui um modelo de tabelas específico fixado no código**.
Ele consulta o esquema do banco MySQL configurado em tempo de execução e
interpreta uma requisição estruturada pelo contrato genérico.

O contrato fica no arquivo
[`schemas/requisicao.schema.json`](schemas/requisicao.schema.json)
e é documentado em
[`docs/contrato_requisicao.md`](docs/contrato_requisicao.md).

```json
{
  "entidade": "filmes",
  "campos": ["título do filme"],
  "filtros": {},
  "agrupamento": [],
  "agregacoes": []
}
```

**Qualquer JSON fora dessa estrutura é rejeitado antes de conectar ao banco
ou chamar o modelo local.** O mesmo padrão vale para pedidos colados na janela ou no terminal,
lidos de arquivo e enviados à função Python. Você pode usar qualquer nome de
arquivo, como `pedido.json`, e reutilizá-lo para consultas diferentes.

Após instalar `python -m pip install -r requirements.txt` e configurar MySQL/Ollama:

```powershell
python -m src.main --arquivo pedido.json
```

## Escopo atual

- Receber requisições estruturadas em JSON.
- Interpretar os parâmetros recebidos.
- Relacionar os parâmetros às tabelas e colunas do banco.
- Gerar e validar consultas SQL.
- Executar consultas de leitura no MySQL.
- Retornar os registros recuperados.

A interface Tkinter recebe a requisição JSON e apresenta a SQL, os parâmetros,
os registros, a interpretação e as métricas em abas. A conversão de linguagem
natural para JSON e a criação de gráficos continuam fora do escopo.

## Como o agente consulta o banco

O agente lê as tabelas, colunas e chaves estrangeiras do MySQL configurado.
O Ollama interpreta o pedido com esses metadados e gera um SELECT parametrizado.
O agente confere campos, filtros, junções e agrupamentos antes de executar a
consulta. A interface gráfica e o terminal usam esse mesmo fluxo.

Para investigar a geração, defina `AGENTE_DEPURAR_SQL=1` no arquivo `.env`.
Esse modo exibe também as respostas brutas do modelo, incluindo parâmetros.

Veja a [configuração do MySQL e do Ollama](docs/configuracao-local.md).

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

Na janela, preencha o modelo de requisição ou importe um JSON com **Ctrl+O**.
**Validar** confere o contrato. **Ctrl+Enter** executa a consulta.
Durante a execução, a tela identifica a etapa em andamento e mostra o tempo decorrido.

Na janela de resultados, **Voltar à requisição** recupera o último pedido para edição.
**Nova consulta** abre o modelo inicial. A pesquisa, a ordenação e a paginação
operam sobre os registros já recuperados. **Exportar resultados** salva todos os
registros em CSV ou JSON, inclusive quando há um filtro visual ativo.

As abas **Consulta SQL**, **Resultados** e **Interpretação** apresentam a
consulta, os dados e as relações usadas. **Detalhes técnicos** reúne tempos,
tokens e tentativas.

A instalação com `python -m pip install -r requirements.txt` inclui CustomTkinter
para os componentes arredondados e Pillow para os ícones. O Python precisa ter
suporte a Tk (no Windows, o instalador oferece o componente Tcl/Tk). Para colar o JSON no
terminal, execute `python -m src.main --cli`. Com `--arquivo`, o processamento
também permanece no terminal. [Ver capturas das janelas](docs/interface/README.md)

O nome do modelo é configurável. Isso permitirá testar diferentes modelos sem alterar o código do agente.

## Execução local

O programa utiliza o serviço local do Ollama em `http://localhost:11434`. O código não implementa chamadas a APIs de IA na nuvem. O download inicial dos modelos exige internet; depois de instalados, podem ser executados localmente.

## Documentação

As decisões de arquitetura, os critérios de avaliação dos modelos, os testes e os resultados serão registrados em `docs/` conforme o desenvolvimento avançar.

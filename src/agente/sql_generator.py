"""Geração e validação inicial de consultas SQL."""

import json
import re
from typing import Any

import sqlglot
from sqlglot import exp

from src.agente.ollama_client import OllamaModelClient
from src.agente.esquema_geracao_sql import ESQUEMA_GERACAO_SQL


def _estrutura_relevante(interpretacao: dict, estrutura: dict) -> dict:
    """Reduz somente o contexto do modelo, nunca o esquema do validador.

    Seleciona tabelas referenciadas pela interpretação e pelas FKs
    necessárias, independentemente dos nomes do banco.
    """
    tabelas = estrutura.get("tabelas", {})
    if not isinstance(tabelas, dict) or not tabelas:
        return estrutura

    nomes = {nome.casefold(): nome for nome in tabelas}
    usadas = set()

    def incluir_referencias(valor):
        if isinstance(valor, str):
            for nome, _ in re.findall(
                r"(?<![A-Za-z_0-9])([A-Za-z_][A-Za-z_0-9]*)\.([A-Za-z_][A-Za-z_0-9]*)",
                valor,
            ):
                real = nomes.get(nome.casefold())
                if real:
                    usadas.add(real)
        elif isinstance(valor, dict):
            for parte in valor.values():
                incluir_referencias(parte)
        elif isinstance(valor, list):
            for parte in valor:
                incluir_referencias(parte)

    for nome in interpretacao.get("tabelas_identificadas", []):
        if isinstance(nome, str) and nome.casefold() in nomes:
            usadas.add(nomes[nome.casefold()])

    for chave in (
        "campos_solicitados", "filtros", "relacionamentos_necessarios",
        "agrupamento", "agregacoes",
    ):
        incluir_referencias(interpretacao.get(chave, []))

    if not usadas or len(usadas) == len(tabelas):
        return estrutura

    relacionamentos = []
    for relacao in estrutura.get("relacionamentos", []):
        origem = relacao.get("origem", "").split(".", 1)[0]
        destino = relacao.get("destino", "").split(".", 1)[0]
        if origem in usadas and destino in usadas:
            relacionamentos.append(relacao)

    return {
        "banco": estrutura.get("banco"),
        "tabelas": {nome: dados for nome, dados in tabelas.items() if nome in usadas},
        "relacionamentos": relacionamentos,
    }



def _remover_where_true_redundante(
    consulta: str, parametros: list, interpretacao: dict
) -> str:
    """Normaliza exclusivamente WHERE TRUE final, sem filtros solicitados.

    Não modifica outras expressões WHERE nem consultas parametrizadas.
    A consulta resultante ainda passa integralmente pelo validador SQL.
    """
    if parametros or interpretacao.get("filtros"):
        return consulta
    return re.sub(
        r"\s+WHERE\s+TRUE\s*;?\s*$",
        "",
        consulta,
        flags=re.IGNORECASE,
    )


class SQLGenerationError(RuntimeError):
    """Erro durante a geração ou validação da consulta SQL."""


class SQLGenerator:
    """Gera consultas SQL com auxílio do modelo local."""

    def __init__(self, modelo: OllamaModelClient) -> None:
        self.modelo = modelo

    def generate(
        self,
        interpretacao: dict[str, Any],
        estrutura: dict[str, Any],
    ) -> dict[str, Any]:
        """Gera, valida e tenta corrigir automaticamente a consulta SQL."""

        max_tentativas = 3
        estrutura_prompt = _estrutura_relevante(interpretacao, estrutura)

        prompt = self._build_initial_prompt(
            interpretacao,
            estrutura_prompt,
        )

        ultimo_erro = ""
        resposta_anterior = ""

        for tentativa in range(1, max_tentativas + 1):

            resultado = self.modelo.generate(
                prompt=prompt,
                max_tokens=700,
                json_schema=ESQUEMA_GERACAO_SQL,
            )

            print(
                f"\nRESPOSTA BRUTA DO MODELO - TENTATIVA {tentativa}"
            )
            print(resultado.content)

            try:
                resposta = self._parse_model_response(
                    resultado.content
                )

                consulta = resposta.get("consulta_sql")
                parametros = resposta.get("parametros")

                if not isinstance(consulta, str) or not consulta.strip():
                    raise SQLGenerationError(
                        "A resposta não contém uma consulta SQL válida."
                    )

                if not isinstance(parametros, list):
                    raise SQLGenerationError(
                        "Os parâmetros da consulta devem ser uma lista."
                    )

                consulta = _remover_where_true_redundante(
                    consulta, parametros, interpretacao
                )

                self._validate_query(
                    consulta,
                    parametros,
                    estrutura,
                    interpretacao,
                )

                print(
                    f"\nConsulta aprovada na tentativa {tentativa}."
                )

                return {
                    "consulta_sql": consulta.strip().rstrip(";"),
                    "parametros": parametros,
                    "tentativas_sql": tentativa,
                }

            except json.JSONDecodeError:
                ultimo_erro = (
                    "O modelo não retornou um JSON válido "
                    "para a consulta SQL."
                )

            except SQLGenerationError as erro:
                ultimo_erro = str(erro)

            if tentativa == max_tentativas:
                break

            print(
                f"\nConsulta rejeitada na tentativa {tentativa}: "
                f"{ultimo_erro}"
            )
            print("Solicitando correção ao modelo local...")

            # Não realimentar explicações longas ou malformadas ao modelo.
            resposta_anterior = (
                resultado.content if ultimo_erro !=
                "O modelo não retornou um JSON válido para a consulta SQL."
                else ""
            )

            prompt = self._build_repair_prompt(
                interpretacao=interpretacao,
                estrutura=estrutura_prompt,
                consulta_anterior=resposta_anterior,
                erro=ultimo_erro,
            )

        raise SQLGenerationError(
            f"A consulta não foi aprovada após {max_tentativas} "
            f"tentativas. Último erro: {ultimo_erro}"
        )

    @staticmethod
    def _parse_model_response(conteudo: str) -> dict[str, Any]:
        """Interpreta o JSON retornado pelo modelo."""

        conteudo = conteudo.strip()

        # Remove cercas Markdown, se o modelo as utilizar.
        if conteudo.startswith("```"):
            linhas = conteudo.splitlines()

            linhas = linhas[1:]

            if linhas and linhas[-1].strip() == "```":
                linhas = linhas[:-1]

            conteudo = "\n".join(linhas).strip()

        resposta = json.loads(conteudo)

        if not isinstance(resposta, dict):
            raise SQLGenerationError(
                "A resposta do modelo não é um objeto JSON."
            )

        return resposta

    @staticmethod
    def _build_initial_prompt(
        interpretacao: dict[str, Any],
        estrutura: dict[str, Any],
    ) -> str:
        """Monta o prompt inicial para geração da consulta."""

        return f"""
Você é um componente especializado em gerar consultas SQL para MySQL.

Sua tarefa é transformar a interpretação estruturada em uma consulta SQL
válida, utilizando exclusivamente as tabelas, colunas e relacionamentos
disponíveis na estrutura do banco de dados.

REGRAS OBRIGATÓRIAS:

1. Gere somente consultas SELECT.
2. Utilize apenas tabelas e colunas existentes no esquema informado.
3. Utilize os relacionamentos fornecidos para construir os JOINs.
4. Identifique as colunas com o nome completo da tabela correspondente.
5. NÃO utilize aliases para tabelas.
6. NÃO abrevie nomes de tabelas.
7. Aliases para colunas são permitidos, utilizando AS.
8. Quando houver nomes de colunas repetidos entre tabelas, utilize
   aliases distintos para evitar ambiguidades no resultado.
9. Utilize marcadores %s para os valores dos filtros.
10. Os valores dos filtros devem ser enviados separadamente na lista
    parametros, respeitando a ordem dos marcadores %s.
11. Não insira valores diretamente na consulta SQL.
12. Para filtros por ano, utilize YEAR(coluna) = %s.
13. Quando houver funções de agregação, como AVG, SUM ou COUNT,
    inclua todas as colunas selecionadas que não estejam agregadas
    no GROUP BY.
14. O GROUP BY deve utilizar os nomes completos das tabelas.
15. Não invente tabelas, colunas ou relacionamentos.
16. Não gere comentários SQL nem múltiplas instruções.
17. Não utilize SELECT *.
18. Não acrescente agrupamentos extras e preserve as agregações solicitadas.
19. Se a interpretação tiver filtros vazios, NÃO escreva WHERE, nem WHERE TRUE.
20. Se filtros estiverem vazios, parametros deve ser [].

FORMATO OBRIGATÓRIO DA RESPOSTA:

Retorne exclusivamente um objeto JSON com as propriedades:
- consulta_sql: contendo a consulta SQL.
- parametros: contendo uma lista com os valores dos filtros.

Não inclua explicações, comentários ou blocos Markdown.

INTERPRETAÇÃO:
{json.dumps(interpretacao, ensure_ascii=False, indent=2)}

ESTRUTURA DO BANCO:
{json.dumps(estrutura, ensure_ascii=False, indent=2)}
"""

    @staticmethod
    def _build_repair_prompt(
        interpretacao: dict[str, Any],
        estrutura: dict[str, Any],
        consulta_anterior: str,
        erro: str,
    ) -> str:
        """Monta um prompt para corrigir uma consulta rejeitada."""

        return f"""
A consulta SQL gerada anteriormente foi rejeitada pela validação.

Você deve corrigir o problema identificado e gerar uma nova consulta.

ERRO ENCONTRADO:
{erro}

RESPOSTA ANTERIOR:
{consulta_anterior}

REGRAS PARA A CORREÇÃO:

1. Gere somente uma consulta SELECT válida para MySQL.
2. Utilize exclusivamente as tabelas, colunas e relacionamentos informados.
3. Preserve os filtros e os campos solicitados na interpretação.
4. Utilize JOINs de acordo com os relacionamentos do banco.
5. NÃO utilize aliases para tabelas.
6. NÃO abrevie nomes de tabelas.
7. Sempre identifique as colunas pelo nome completo da tabela.
8. Aliases para colunas são permitidos, utilizando AS.
9. Utilize marcadores %s para os valores dos filtros.
10. Retorne os valores dos filtros na lista parametros,
    respeitando a ordem correta.
11. Quando houver funções de agregação e colunas não agregadas,
    inclua as colunas não agregadas no GROUP BY.
12. Não gere comentários SQL nem múltiplas instruções.
13. Não utilize SELECT *.
14. A lista de campos em campos_solicitados deve ser respeitada
    exatamente na projeção do SELECT.
15. Não substitua campos solicitados por IDs, chaves estrangeiras
    ou outras colunas, mesmo que representem a mesma entidade.
16. Para toda coluna solicitada, selecione a própria coluna,
    sem substituí-la por uma chave estrangeira ou identificador.
17. Quando houver uma agregação solicitada, utilize a função e
    a coluna exatas indicadas na interpretação.
18. Todos os filtros da interpretação devem aparecer na cláusula WHERE.
19. Preserve exatamente os campos, operadores e valores dos filtros.
20. Não remova, substitua ou acrescente filtros que não foram solicitados.
21. Utilize um marcador %s para cada valor de filtro.
22. Respeite a ordem dos parâmetros conforme a ordem das condições SQL.
23. Para o operador ANO_IGUAL, utilize YEAR(campo) = %s.
24. Preserve exatamente os relacionamentos necessários nos JOINs.
25. Não omita, substitua ou acrescente relacionamentos nas condições ON.
26. Preserve as funções e os campos exatos de cada agregação.
27. O GROUP BY deve conter exatamente os campos de agrupamento solicitados.
28. Não acrescente GROUP BY a consultas sem agregação ou agrupamento solicitado.
29. Se filtros estiver vazio, não use WHERE, nem WHERE TRUE, e retorne parametros [].

Retorne exclusivamente um objeto JSON contendo:
- consulta_sql
- parametros

Não inclua explicações nem blocos Markdown.

INTERPRETAÇÃO:
{json.dumps(interpretacao, ensure_ascii=False, indent=2)}

ESTRUTURA DO BANCO:
{json.dumps(estrutura, ensure_ascii=False, indent=2)}
"""

    @staticmethod
    def _validate_query(
        consulta: str,
        parametros: list[Any],
        estrutura: dict[str, Any],
        interpretacao: dict[str, Any],

    ) -> None:
        """Valida a sintaxe, as tabelas, as colunas e as agregações."""

        consulta = consulta.strip()

        # Remove um eventual ponto e vírgula final.
        if consulta.endswith(";"):
            consulta = consulta[:-1].strip()

        # Não permite múltiplas instruções.
        if ";" in consulta:
            raise SQLGenerationError(
                "A consulta contém múltiplas instruções SQL."
            )

        # Não permite comentários SQL.
        if re.search(r"--|/\*|\*/|#", consulta):
            raise SQLGenerationError(
                "Comentários SQL não são permitidos."
            )

        # Confere os parâmetros.
        quantidade_parametros = consulta.count("%s")

        if quantidade_parametros != len(parametros):
            raise SQLGenerationError(
                "A quantidade de parâmetros não corresponde "
                "à quantidade de marcadores %s."
            )

        for valor in parametros:
            if not isinstance(
                valor,
                (str, int, float, bool, type(None)),
            ):
                raise SQLGenerationError(
                    "Foi encontrado um parâmetro com tipo não permitido."
                )

        # Substitui os marcadores para permitir a análise sintática.
        consulta_analise = consulta.replace("%s", "NULL")

        try:
            comandos = sqlglot.parse(
                consulta_analise,
                read="mysql",
            )
        except Exception as exc:
            raise SQLGenerationError(
                "Não foi possível analisar a sintaxe da consulta SQL."
            ) from exc

        if len(comandos) != 1 or comandos[0] is None:
            raise SQLGenerationError(
                "A consulta deve conter somente uma instrução SQL."
            )

        arvore = comandos[0]

        if not isinstance(arvore, exp.Select):
            raise SQLGenerationError(
                "Somente consultas SELECT são permitidas."
            )

        # Recupera as tabelas disponíveis no banco.
        tabelas_disponiveis = estrutura["tabelas"]

        # Cria um índice sem distinção entre maiúsculas e minúsculas.
        esquema_tabelas = {
            nome.casefold(): nome
            for nome in tabelas_disponiveis
        }

        colunas_por_tabela = {
            nome: {
                coluna["nome"].casefold()
                for coluna in dados["colunas"]
            }
            for nome, dados in tabelas_disponiveis.items()
        }

        # Identifica as tabelas utilizadas e seus aliases.
        tabelas_utilizadas = set()
        aliases = {}

        for tabela in arvore.find_all(exp.Table):

            nome_informado = tabela.name
            nome_real = esquema_tabelas.get(
                nome_informado.casefold()
            )

            if nome_real is None:
                raise SQLGenerationError(
                    f"Tabela não existente no esquema: {nome_informado}."
                )

            tabelas_utilizadas.add(nome_real)

            # Permite referência pelo próprio nome da tabela.
            aliases[nome_real.casefold()] = nome_real

            # Registra o nome de referência informado pelo SQLGlot.
            nome_referencia = tabela.alias_or_name

            if nome_referencia:
                aliases[nome_referencia.casefold()] = nome_real

            # Registra explicitamente o alias, quando existir.
            alias_expr = tabela.args.get("alias")

            if isinstance(alias_expr, exp.TableAlias):
                alias_nome = alias_expr.this.name

                if alias_nome:
                    aliases[alias_nome.casefold()] = nome_real

        if not tabelas_utilizadas:
            raise SQLGenerationError(
                "A consulta não identifica nenhuma tabela."
            )

        # Verifica se todas as colunas pertencem ao esquema.
        for coluna in arvore.find_all(exp.Column):

            if coluna.name == "*":
                continue

            tabela_referenciada = coluna.table

            if not tabela_referenciada:
                raise SQLGenerationError(
                    f"Coluna sem identificação da tabela: {coluna.name}."
                )

            tabela_real = aliases.get(
                tabela_referenciada.casefold()
            )

            if tabela_real is None:
                raise SQLGenerationError(
                    f"Tabela não identificada para a coluna: "
                    f"{tabela_referenciada}. "
                    f"Referências reconhecidas: {sorted(aliases.keys())}."
                )

            if coluna.name.casefold() not in colunas_por_tabela[tabela_real]:
                raise SQLGenerationError(
                    f"Coluna não existente: {tabela_real}.{coluna.name}."
                )

        # Valida se a consulta retorna exatamente os campos solicitados.

        def extrair_assinatura(expressao: exp.Expression) -> tuple:
            """Identifica tabela, coluna e função de agregação."""

            if isinstance(expressao, exp.Alias):
                expressao = expressao.this

            agregacao = None

            if isinstance(expressao, exp.AggFunc):
                agregacao = expressao.key.upper()

                colunas = list(expressao.find_all(exp.Column))

                if len(colunas) != 1:
                    raise SQLGenerationError(
                        "Não foi possível identificar o campo "
                        "da expressão de agregação."
                    )

                coluna = colunas[0]

            elif isinstance(expressao, exp.Column):
                coluna = expressao

            else:
                raise SQLGenerationError(
                    "A consulta contém uma expressão não reconhecida "
                    "na lista de campos retornados."
                )

            tabela = coluna.table
            nome_coluna = coluna.name

            tabela_real = aliases.get(tabela.casefold())

            if tabela_real is None:
                raise SQLGenerationError(
                    f"Tabela não identificada na projeção: {tabela}."
                )

            return (
                tabela_real.casefold(),
                nome_coluna.casefold(),
                agregacao,
            )

        campos_esperados = set()

        for campo in interpretacao.get("campos_solicitados", []):

            try:
                expressao = sqlglot.parse_one(
                    f"SELECT {campo}",
                    read="mysql",
                ).expressions[0]

                assinatura = extrair_assinatura(expressao)

                campos_esperados.add(assinatura)

            except SQLGenerationError:
                raise

            except Exception as exc:
                raise SQLGenerationError(
                    f"Campo solicitado inválido na interpretação: {campo}."
                ) from exc

        campos_encontrados = {
            extrair_assinatura(projecao)
            for projecao in arvore.expressions
        }

        campos_faltantes = campos_esperados - campos_encontrados
        campos_extras = campos_encontrados - campos_esperados

        if campos_faltantes or campos_extras:

            detalhes = []

            if campos_faltantes:
                detalhes.append(
                    "Campos solicitados ausentes na consulta: "
                    f"{sorted(campos_faltantes)}"
                )

            if campos_extras:
                detalhes.append(
                    "Campos não solicitados encontrados na consulta: "
                    f"{sorted(campos_extras)}"
                )

            raise SQLGenerationError("; ".join(detalhes))

        # Valida se os filtros da consulta correspondem à interpretação.

        def separar_condicoes(expressao: exp.Expression) -> list:
            """Separa condições ligadas por AND."""

            if isinstance(expressao, exp.And):
                return (
                    separar_condicoes(expressao.this)
                    + separar_condicoes(expressao.expression)
                )

            return [expressao]

        def extrair_filtro(condicao: exp.Expression) -> tuple:
            """Extrai campo, operador e valor de uma condição SQL."""

            operadores = {
                exp.EQ: "=",
                exp.NEQ: "!=",
                exp.GT: ">",
                exp.GTE: ">=",
                exp.LT: "<",
                exp.LTE: "<=",
            }

            operador = next(
                (
                    simbolo
                    for classe, simbolo in operadores.items()
                    if isinstance(condicao, classe)
                ),
                None,
            )

            if operador is None:
                raise SQLGenerationError(
                    "A consulta contém um operador de filtro "
                    "ainda não suportado pelo validador."
                )

            esquerda = condicao.this
            direita = condicao.expression

            # Identifica filtros por ano: YEAR(campo) = %s.

            ano_igual = (
                isinstance(esquerda, exp.Func)
                and esquerda.sql_name().upper() == "YEAR"
                and operador == "="
            )

            if ano_igual:
                colunas = list(esquerda.find_all(exp.Column))

                if len(colunas) != 1:
                    raise SQLGenerationError(
                        "Não foi possível identificar a coluna "
                        "utilizada no filtro por ano."
                    )

                coluna = colunas[0]
                operador = "ANO_IGUAL"

            elif isinstance(esquerda, exp.Column):
                coluna = esquerda

            else:
                raise SQLGenerationError(
                    "Não foi possível identificar o campo "
                    "utilizado em uma condição SQL."
                )

            tabela_real = aliases.get(coluna.table.casefold())

            if tabela_real is None:
                raise SQLGenerationError(
                    f"Tabela não identificada no filtro: {coluna.table}."
                )

            if not isinstance(direita, exp.Null):
                raise SQLGenerationError(
                    "Os valores dos filtros devem utilizar "
                    "parâmetros %s, não valores inseridos diretamente."
                )

            return (
                f"{tabela_real}.{coluna.name}".casefold(),
                operador,
            )

        filtros_esperados = [
            (
                filtro["campo"].casefold(),
                filtro["operador"].upper()
                if filtro["operador"] == "ANO_IGUAL"
                else filtro["operador"],
                filtro["valor"],
            )
            for filtro in interpretacao.get("filtros", [])
        ]

        where = arvore.args.get("where")

        if where is None:
            filtros_encontrados = []
        else:
            condicoes = separar_condicoes(where.this)

            if len(condicoes) != len(parametros):
                raise SQLGenerationError(
                    "A quantidade de condições da consulta não "
                    "corresponde à quantidade de parâmetros informados."
                )

            filtros_encontrados = []

            for indice, condicao in enumerate(condicoes):
                campo, operador = extrair_filtro(condicao)

                filtros_encontrados.append(
                    (
                        campo,
                        operador,
                        parametros[indice],
                    )
                )

        filtros_pendentes = list(filtros_esperados)

        for filtro in filtros_encontrados:
            if filtro in filtros_pendentes:
                filtros_pendentes.remove(filtro)

        filtros_extras = list(filtros_encontrados)

        for filtro in filtros_esperados:
            if filtro in filtros_extras:
                filtros_extras.remove(filtro)

        if filtros_pendentes or filtros_extras:
            detalhes = []

            if filtros_pendentes:
                detalhes.append(
                    f"Filtros solicitados ausentes ou incorretos: "
                    f"{filtros_pendentes}"
                )

            if filtros_extras:
                detalhes.append(
                    f"Filtros não solicitados encontrados: "
                    f"{filtros_extras}"
                )

            raise SQLGenerationError("; ".join(detalhes))

        # Verifica a estrutura das agregações e do GROUP BY.
        projecoes = arvore.expressions

        colunas_nao_agregadas = set()
        possui_agregacao = False

        for projecao in projecoes:

            contem_agregacao = any(
                isinstance(no, exp.AggFunc)
                for no in projecao.walk()
            )

            if contem_agregacao:
                possui_agregacao = True

            else:
                for coluna in projecao.find_all(exp.Column):

                    tabela_real = aliases.get(
                        coluna.table.casefold()
                    )

                    colunas_nao_agregadas.add(
                        (tabela_real, coluna.name.casefold())
                    )

        if possui_agregacao and colunas_nao_agregadas:

            agrupamento = arvore.args.get("group")

            if agrupamento is None:
                raise SQLGenerationError(
                    "A consulta possui funções de agregação e colunas "
                    "não agregadas, mas não contém GROUP BY."
                )

            colunas_agrupadas = set()

            for expressao in agrupamento.expressions:

                for coluna in expressao.find_all(exp.Column):

                    tabela_real = aliases.get(
                        coluna.table.casefold()
                    )

                    colunas_agrupadas.add(
                        (tabela_real, coluna.name.casefold())
                    )

            colunas_faltantes = (
                colunas_nao_agregadas - colunas_agrupadas
            )

            if colunas_faltantes:
                raise SQLGenerationError(
                    "O GROUP BY não contempla todas as colunas "
                    "selecionadas fora das funções de agregação: "
                    f"{sorted(colunas_faltantes)}."
                )

        # Verifica se os JOINs correspondem aos relacionamentos esperados.
        def normalizar_relacionamento(origem: str, destino: str) -> frozenset:
            return frozenset((origem.casefold(), destino.casefold()))

        def extrair_relacionamentos(lista: Any) -> set[frozenset]:
            if not isinstance(lista, list):
                raise SQLGenerationError(
                    "Os relacionamentos devem ser informados em uma lista."
                )

            relacionamentos = set()

            for item in lista:
                if not isinstance(item, dict):
                    raise SQLGenerationError(
                        "Relacionamento com estrutura inválida."
                    )

                origem = item.get("origem")
                destino = item.get("destino")

                if (
                    not isinstance(origem, str)
                    or not isinstance(destino, str)
                    or len(origem.split(".")) != 2
                    or len(destino.split(".")) != 2
                    or not all(origem.split("."))
                    or not all(destino.split("."))
                ):
                    raise SQLGenerationError(
                        "Relacionamento com colunas inválidas."
                    )

                relacionamentos.add(
                    normalizar_relacionamento(origem, destino)
                )

            return relacionamentos

        esperados = extrair_relacionamentos(
            interpretacao.get("relacionamentos_necessarios", [])
        )
        permitidos = extrair_relacionamentos(
            estrutura.get("relacionamentos", [])
        )

        if not esperados.issubset(permitidos):
            raise SQLGenerationError(
                "A interpretação contém relacionamentos inexistentes no banco."
            )

        encontrados = set()

        def analisar_on(condicao: exp.Expression) -> None:
            if isinstance(condicao, exp.Paren):
                analisar_on(condicao.this)
                return

            if isinstance(condicao, exp.And):
                analisar_on(condicao.this)
                analisar_on(condicao.expression)
                return

            if not isinstance(condicao, exp.EQ):
                raise SQLGenerationError(
                    "A condição ON contém uma expressão não suportada."
                )

            esquerda, direita = condicao.this, condicao.expression

            if not (
                isinstance(esquerda, exp.Column)
                and isinstance(direita, exp.Column)
            ):
                raise SQLGenerationError(
                    "JOIN deve comparar duas colunas qualificadas."
                )

            if not esquerda.table or not direita.table:
                raise SQLGenerationError(
                    "Coluna do JOIN sem identificação da tabela."
                )

            tabela_esquerda = aliases.get(esquerda.table.casefold())
            tabela_direita = aliases.get(direita.table.casefold())

            if not tabela_esquerda or not tabela_direita:
                raise SQLGenerationError(
                    "O JOIN usa uma tabela não reconhecida."
                )

            encontrados.add(
                normalizar_relacionamento(
                    f"{tabela_esquerda}.{esquerda.name}",
                    f"{tabela_direita}.{direita.name}",
                )
            )

        for join in arvore.find_all(exp.Join):
            condicao_on = join.args.get("on")

            if condicao_on is None:
                raise SQLGenerationError(
                    "JOIN sem condição ON não é permitido."
                )

            analisar_on(condicao_on)

        faltantes = esperados - encontrados
        extras = encontrados - esperados

        if faltantes or extras:
            raise SQLGenerationError(
                "Os relacionamentos JOIN divergem da interpretação. "
                f"Ausentes: {sorted(map(sorted, faltantes))}. "
                f"Adicionais: {sorted(map(sorted, extras))}."
            )

        # Validação semântica completa do agrupamento.
        # Sem agrupamento explícito, as colunas não agregadas da
        # projeção definem o agrupamento esperado quando há agregação.
        def assinatura_coluna(expressao: exp.Expression) -> str:
            if not isinstance(expressao, exp.Column):
                raise SQLGenerationError(
                    "GROUP BY deve utilizar apenas colunas qualificadas."
                )

            if not expressao.table:
                raise SQLGenerationError(
                    "Coluna do GROUP BY sem identificação da tabela."
                )

            tabela = aliases.get(expressao.table.casefold())
            if tabela is None:
                raise SQLGenerationError(
                    "Tabela não identificada no GROUP BY."
                )

            return f"{tabela}.{expressao.name}".casefold()

        agrupamento_sql = arvore.args.get("group")
        colunas_agrupamento_sql = []

        if agrupamento_sql is not None:
            colunas_agrupamento_sql = [
                assinatura_coluna(item)
                for item in agrupamento_sql.expressions
            ]

        if len(colunas_agrupamento_sql) != len(set(colunas_agrupamento_sql)):
            raise SQLGenerationError(
                "GROUP BY contém colunas repetidas."
            )

        agrupamento_interpretado = interpretacao.get("agrupamento")
        if agrupamento_interpretado is not None:
            if not isinstance(agrupamento_interpretado, list):
                raise SQLGenerationError(
                    "O agrupamento da interpretação deve ser uma lista."
                )
            colunas_esperadas_group = []
            for campo in agrupamento_interpretado:
                if not isinstance(campo, str):
                    raise SQLGenerationError(
                        "Agrupamento inválido na interpretação."
                    )
                try:
                    coluna = sqlglot.parse_one(
                        f"SELECT {campo}", read="mysql"
                    ).expressions[0]
                except Exception as exc:
                    raise SQLGenerationError(
                        "Agrupamento inválido na interpretação."
                    ) from exc
                colunas_esperadas_group.append(assinatura_coluna(coluna))
        elif possui_agregacao:
            colunas_esperadas_group = [
                f"{tabela}.{coluna}".casefold()
                for tabela, coluna in colunas_nao_agregadas
            ]
        else:
            colunas_esperadas_group = []

        # Uma agregação global válida não precisa de GROUP BY.
        # Uma consulta sem agregação também não deve agrupar implicitamente.
        if set(colunas_agrupamento_sql) != set(colunas_esperadas_group):
            raise SQLGenerationError(
                "GROUP BY diferente do agrupamento solicitado. "
                f"Esperado: {sorted(set(colunas_esperadas_group))}. "
                f"Encontrado: {sorted(set(colunas_agrupamento_sql))}."
            )

        # Confere os detalhes das agregações explicitadas no JSON original
        # quando foram preservados na interpretação.
        agregacoes_esperadas = interpretacao.get("agregacoes")
        if agregacoes_esperadas is not None:
            if not isinstance(agregacoes_esperadas, list):
                raise SQLGenerationError(
                    "A lista de agregações da interpretação é inválida."
                )

            assinaturas_esperadas = set()
            for item in agregacoes_esperadas:
                if not isinstance(item, dict):
                    raise SQLGenerationError(
                        "Agregação inválida na interpretação."
                    )
                funcao, campo = item.get("funcao"), item.get("campo")
                if not isinstance(funcao, str) or not isinstance(campo, str):
                    raise SQLGenerationError(
                        "Função ou campo de agregação inválido."
                    )
                try:
                    projecao = sqlglot.parse_one(
                        f"SELECT {funcao}({campo})", read="mysql"
                    ).expressions[0]
                    assinatura = extrair_assinatura(projecao)
                except SQLGenerationError:
                    raise
                except Exception as exc:
                    raise SQLGenerationError(
                        "Agregação inválida na interpretação."
                    ) from exc
                if assinatura[2] is None:
                    raise SQLGenerationError(
                        "Função de agregação não reconhecida."
                    )
                assinaturas_esperadas.add(assinatura)

            assinaturas_encontradas = {
                assinatura for assinatura in campos_encontrados
                if assinatura[2] is not None
            }
            if assinaturas_encontradas != assinaturas_esperadas:
                raise SQLGenerationError(
                    "As agregações SQL não correspondem às solicitadas."
                )

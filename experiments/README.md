# Catálogo piloto de experimentos

Este catálogo serve para validar o **executor**, não constitui ainda a bateria
experimental definitiva do TCC.

## Identificação das rodadas

Cada execução do comando experimental recebe um `rodada_id` aleatório único
(UUID sem hífens), também registrado nas falhas. Dentro da rodada, cada linha
recebe `cenario` e `repeticao`. Assim, duas invocações separadas com
`--repeticoes 2` não se confundem.

Logs anteriores a essa alteração não possuem `rodada_id`; não os misture aos
experimentos oficiais sem identificação adicional.

## Cenários iniciais

| ID | Tipo | Referência |
|---|---|---|
| cenario_01 | Seleção e filtros com JOIN | 3 medições de Jataí em 2025, já verificadas |
| cenario_02 | Agregação AVG com dois JOINs e GROUP BY | Rio Claro/Jataí, média de 21,10 m³/s, já verificada |
| cenario_03 | Seleção e filtro em rios | Conferida no MySQL Workbench |
| cenario_04 | JOIN entre indicadores e municípios | Conferida no MySQL Workbench |

O arquivo `experiments/cenarios_piloto.json` contém as requisições.
As referências dos cenários 03 e 04 foram adicionadas a partir de resultados
consultados diretamente no MySQL Workbench. Antes da avaliação definitiva,
reconfirme todas as referências após congelar os dados do banco.

As referências 01 e 02 são baseadas no banco experimental local observado.
Antes dos experimentos finais, congele a versão dos dados e valide
independentemente as consultas de referência.

## Validação sem executar modelos

```powershell
python -m src.executar_experimentos --arquivo experiments/cenarios_piloto.json --validar
```

A validação confirma apenas o formato e a presença de referência;
não comprova que os resultados esperados estejam corretos.

## Execução piloto (opcional)

```powershell
python -m src.executar_experimentos --arquivo experiments/cenarios_piloto.json --repeticoes 1
```

As execuções são acrescentadas a `experiments/results/execucoes.jsonl`,
que não deve ser versionado. O campo `status=sucesso` indica execução sem
falha técnica. O campo `avaliacao.correto` indica coincidência com a
referência, quando ela existe.

Nos quatro cenários piloto, `colunas_referencia` associa a expressão física
ao nome da coluna no gabarito. Pode identificar uma coluna ou uma agregação,
como `AVG(medicoes.vazao_m3_s)`. O avaliador resolve aliases de tabelas e
de saída e confere os valores e a multiplicidade das linhas. A comparação
ignora a ordem quando `ordem_importa` é falso. Obtenha o gabarito por uma
consulta independente na mesma versão dos dados. Somente a requisição segue
para o modelo.

O registro identifica a última tentativa com `sql_sintaticamente_valida`
(`null` quando a análise sintática não ocorreu), `sql_aprovada` e
`consulta_executada`. Uma execução bem-sucedida tem `resultado` igual a
`correto`, `divergente` ou `sem_referencia`. Uma falha técnica tem
`etapa_falha`, contadores de tentativas e tempos das etapas alcançadas.
O JSONL guarda esses indicadores sem o texto do pedido, do SQL, da exceção
ou dos registros do banco. Linhas anteriores à mudança podem omitir os campos novos.

## Ampliação gradual: cenários 05 a 14

O arquivo `experiments/cenarios_expansao_05_14.json` contém **dez cenários
novos**, sem `resultado_esperado` até que cada resultado seja verificado de
forma independente no MySQL. A ausência dessas referências não significa que
a execução esteja incorreta: ela ficará **sem avaliação**.

| Cenário | Categoria |
|---|---|
| 05 | Projeção em municípios com filtro |
| 06 | Projeção em municípios sem filtro |
| 07 | Medições com filtros por município e ano |
| 08 | Rios sem filtro |
| 09 | Relacionamento entre rios e município de referência |
| 10 | Indicadores filtrados por município |
| 11 | Medições com dois JOINs e três filtros |
| 12 | Média global do nível da água |
| 13 | Vazão máxima |
| 14 | Média da vazão agrupada por rio |

### Conferência da estrutura (sem rodar o modelo)

```powershell
python -m src.executar_experimentos --arquivo experiments/cenarios_expansao_05_14.json --validar
```

Esperado: 10 cenários válidos, 0 com referência, 10 pendentes.

### Referências: primeiros cenários a conferir no Workbench

Estas SQLs são **candidatas de referência**, preparadas para conferência no
banco, e não valores esperados já verificados.

Cenário 05:

```sql
SELECT municipios.nome, municipios.uf, municipios.regiao
FROM municipios
WHERE municipios.nome = 'Jataí';
```

Cenário 06:

```sql
SELECT municipios.nome, municipios.uf, municipios.regiao
FROM municipios;
```

Cenário 07:

```sql
SELECT medicoes.data_medicao, medicoes.vazao_m3_s, medicoes.nivel_m
FROM medicoes INNER JOIN municipios
  ON medicoes.municipio_id = municipios.id
WHERE municipios.nome = 'Jataí'
  AND YEAR(medicoes.data_medicao) = 2025;
```

Após consultar e verificar os resultados, registre as referências no JSON.
Não use a resposta do agente como fonte da referência. Antes da bateria
definitiva, fixe uma versão dos dados e documente os resultados oficiais.

**Nota metodológica:** consultas sem `ORDER BY` são avaliadas sem considerar
a ordem das linhas. Os casos 05 a 14 ainda são candidatos experimentais:
alguns podem revelar limitações no interpretador ou no validador e precisar
ser ajustados ou classificados em categorias específicas antes da aplicação
a todos os modelos.

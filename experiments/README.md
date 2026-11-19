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
| cenario_04 | JOIN entre indicadores e municípios | Pendente de conferência manual |

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

**Atenção:** a comparação utiliza nomes exatos das colunas de saída.
Aliases SQL diferentes podem produzir registros semanticamente
equivalentes marcados como diferentes. Antes da bateria definitiva,
defina e documente uma convenção de aliases ou amplie a avaliação
sem criar equivalências ambíguas.

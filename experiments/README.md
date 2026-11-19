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

**Aliases SQL:** nos cenários 03 e 04, `colunas_referencia`
associa cada coluna de origem (por exemplo, `rios.nome`) ao nome do
campo no resultado de referência (`nome`). O avaliador lê a expressão
SELECT com SQLGlot e considera equivalentes aliases distintos somente
quando referem-se à mesma coluna de origem. Não aceita automaticamente
colunas extras, expressões diferentes ou valores divergentes.

O mapeamento é específico do **avaliador experimental**; não é
fornecido ao modelo na geração de SQL. A precisão final ainda depende
de confirmar que as referências do banco estão corretas.

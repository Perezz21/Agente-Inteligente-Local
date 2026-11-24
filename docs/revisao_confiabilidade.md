# Confiabilidade das consultas em um esquema MySQL desconhecido

## A. Diagnóstico inicial

No Comércio Integrado, o autor relatou cinco consultas aprovadas na primeira tentativa de SQL e três falhas de interpretação em oito pedidos. Nos três casos, o agente informou que a coluna `id` não existia. Reproduzi o defeito com várias tabelas que tinham uma coluna chamada `id`. O validador comparava o texto devolvido pelo modelo diretamente com referências qualificadas. Descartava assim uma informação que o próprio usuário já havia dado em `tabela.id`. O contrato de saída aceitava qualquer texto em `filtros[].campo`. A segunda tentativa recebia o erro sem identificar as alternativas. A causa de o Ollama ter produzido a abreviação naquela máquina continua indeterminada.

Também reproduzi a aceitação de planos desconectados e de uma condição `ON` que citava apenas tabelas anteriores. O avaliador podia rejeitar dados corretos quando a SQL usava um alias de tabela, ou considerar iguais códigos textuais como `001` e `1`. Duas colunas chamadas `nome` também podiam passar pela validação e disputar uma única chave no dicionário retornado ao usuário.

## B. Modificações e justificativas

| Arquivos | Mudança e motivo |
|---|---|
| `src/agente/validacao_mapeamento.py`, `fluxo.py`, `esquema_interpretacao.py` | Uma abreviação pode ser qualificada pelo identificador físico da requisição ou por evidência no catálogo. Uma coluna comercial que corresponda a “número” entra na verificação antes de aceitar a chave interna. A segunda tentativa recebe a dúvida específica. A chave original, o operador, o valor e o tipo atravessam o mapeamento. |
| `src/agente/relacionamentos.py`, `sql_generator.py`, `projecao_sql.py` | O plano procura ligações entre as tabelas necessárias, inclui intermediárias e verifica caminhos alternativos e FKs compostas. Cada `ON` precisa ligar a nova tabela. A SQL também é conferida quanto a projeções repetidas, colisões de nomes de saída, parâmetros, agregações e subtotais. |
| `src/agente/avaliacao.py`, `registro_metricas.py`, `src/executar_experimentos.py` | A avaliação identifica a origem da projeção mesmo com aliases e compara valores, tipos e multiplicidade. O registro distingue análise sintática, aprovação, execução e concordância com o gabarito. Uma falha informa a etapa alcançada. O JSONL registra contagens e tempos, sem SQL, parâmetros, linhas ou texto da exceção. |
| `experiments/README.md`, `cenarios_exemplo.json`, `cenarios_piloto.json` | Documentei os indicadores e associei as colunas físicas aos nomes usados nos gabaritos existentes. Nenhum resultado do agente foi usado para elaborar gabaritos. |
| `tests/test_resolucao_catalogo.py`, `test_avaliacao_etapas.py` e quatro arquivos de teste existentes | Acrescentei regressões e ajustei exemplos antigos para fornecer um catálogo visível e distinguir colunas homônimas na saída. |

## C. Verificações executadas

| Verificação | Resultado |
|---|---|
| Suíte antes das mudanças | 154 aprovados. |
| Suíte final com SQLGlot 26.0.0 e 29.0.1 | 190 aprovados e zero falhas em cada versão. São 36 casos novos. O comando foi `python -m unittest discover -s tests -p "test_*.py" -v`. |
| Relacionamentos e agregações | Casos com uma a quatro tabelas, caminhos concorrentes ou ausentes, tabelas intermediárias, chaves compostas e as cinco funções `AVG`, `SUM`, `MIN`, `MAX`, `COUNT`, globais e agrupadas. Um SELECT com três JOINs foi executado em SQLite em memória com modelo simulado. As três linhas esperadas, inclusive a repetida, foram conferidas com os dados da fixture. |
| Catálogos dos arquivos SQL fornecidos | No Sakila, validei o plano e a SQL de filme com idioma. No banco ambiental, validei medições por município e média por rio e município. As interpretações foram fornecidas à validação. Nenhuma dessas três conferências mediu acerto do Ollama ou execução no servidor MySQL. |

## D. Generalização e utilidade dos cenários

Em outro computador, o agente lê as tabelas, colunas e FKs do MySQL configurado. O fluxo normal recebe a requisição v1.0 e o catálogo descoberto. Os arquivos em `experiments/` são opcionais e servem para repetir perguntas com respostas conhecidas. Por exemplo, o caso de filme e idioma permite detectar uma regressão no Sakila. Seus nomes de tabelas e seus resultados não ajudam o agente a interpretar um banco de vendas. O mesmo código de resolução foi exercitado com nomes e relacionamentos de três domínios, contando o esquema sintético.

## E. Riscos e limitações

O conector implementado atende MySQL. Um esquema com códigos opacos, FKs ausentes ou dois caminhos plausíveis pode exigir uma pergunta mais precisa. A resolução atual também tem limites para autojunções e para dois papéis da mesma tabela na mesma consulta. A associação de vocabulário de negócio a uma coluna ainda depende do modelo. O contrato v1.0 exige referências físicas em `agrupamento` e `agregacoes`, o que exige conhecimento do esquema nesses campos. Aceitar descrições livres ali exigiria definir como tratar ambiguidades e preservar a compatibilidade dos clientes.

## F. Conclusão para o TCC

O protótipo implementa o ciclo de consulta local e somente leitura para MySQL. Para sustentar a conclusão experimental, falta medir a correção dos resultados desta revisão com o modelo e os bancos reais. Neste ambiente não havia MySQL nem Ollama configurados. Os próximos casos decisivos são as três falhas do pedido 101 no Comércio Integrado, uma cadeia com pelo menos três JOINs e agregações nos dois domínios. Cada execução precisa de uma consulta de referência independente sobre os mesmos dados e do registro de tentativas, tempos e concordância. Isso permite distinguir uma recusa segura, uma falha técnica e uma resposta aceita com dados incorretos.

## G. Controle de versão

Branch de trabalho `testes-att`, a partir de `db83fd85b21f96a2aee776a29708c4847719ac77`. O commit que contém este relatório reúne código e testes. O contrato público usado foi `schemas/requisicao_v1.schema.json`. O trabalho não envolveu merge, mudanças nas dependências nem escrita nos bancos do usuário.

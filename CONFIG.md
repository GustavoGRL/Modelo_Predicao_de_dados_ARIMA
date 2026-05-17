# Documentação De Configuração
Este documento descreve os campos efetivamente usados pelo projeto no arquivo `config/config.yami`.

## Arquivo Base
Use este arquivo como referência principal:

- `config/config.yami`

O sistema suporta duas fontes de dados:
- `fonte_dados.tipo: local`: arquivo CSV local fornecido pelo usuário.
- `fonte_dados.tipo: binance`: dados em tempo real da API da Binance (criptomoedas).

## Exemplo Completo
```yaml
projeto:
  nome: "modelo_predicao_arima"
  descricao: "Treinamento ARIMA para análise de tendências"
  versao: "2.0.0"

execucao:
  modo: "treino"
  iniciar_dashboard_automaticamente: true

dashboard:
  porta: 8004
  caminho_estado: "output/estado_treinamento.json"
  caminho_historico: "output/histórico_rodadas.csv"

fonte_dados:
  tipo: "local"

dados_locais:
  caminho: "data/input/pedicure_trends.csv"
  tipo_arquivo: "csv"
  coluna_tempo: "Time"
  delimitador: ","
  pular_linhas: 0

dados_binance:
  symbol: "BTCUSDT"
  interval: "1h"
  limit: 720
  timeout: 15

processamento:
  remover_duplicados: true
  estrategia_valores_faltantes: "remove"
  normalizar_nomes_colunas: true

dados:
  tendencias:
    - pedicure

divisao:
  porcentagem_avaliacao: 20

treinamento:
  n_execucoes: 1000
  execucoes_por_rodada: 7
  top_k: 30
  mostrar_graficos: false
  semente_aleatoria: null

modelo:
  tipo: "arima"
  intervalo_p: [0, 30]
  intervalo_d: [0, 2]
  intervalo_q: [0, 30]
  max_tentativas: 40

teste:
  ordem_fixa: [18, 2, 18]

saida:
  pasta: "output"
  arquivo_resultados: "output/resultados_treinamento.txt"
  salvar_relatorio: true
```

## Blocos Do YAML
## `projeto`
- `nome`: nome do projeto.
- `descricao`: descrição curta do objetivo.
- `versao`: versão do projeto/configuração.

## `execucao`
- `modo`: `treino` ou `teste`.
- `iniciar_dashboard_automaticamente`: abre o dashboard ao iniciar o processo.

## `dashboard`
- `porta`: porta HTTP do painel.
- `caminho_estado`: JSON lido pelo dashboard.
- `caminho_historico`: CSV com evolução por rodada.

## `fonte_dados`
- `tipo`: fonte de dados para treinamento. Valores aceitos:
  - `local`: arquivo CSV local fornecido pelo usuário.
  - `binance`: dados em tempo real da API da Binance (criptomoedas).

## `dados_locais`
- `caminho`: caminho do CSV relativo ao projeto.
- `tipo_arquivo`: deve ser `csv`.
- `coluna_tempo`: coluna temporal original (ex.: `Time`).
- `delimitador`: separador do CSV.
- `pular_linhas`: linhas de cabeçalho extras para ignorar.

Requisitos mínimos do arquivo:
- 1 coluna temporal;
- 1 ou mais colunas numéricas para previsão.

## `dados_binance`
Configuração para buscar dados da API da Binance:
- `symbol`: par de moedas (ex.: `BTCUSDT`, `ETHUSDT`).
- `interval`: intervalo de tempo dos candles. Valores aceitos: `1m`, `3m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `6h`, `8h`, `12h`, `1d`, `3d`, `1w`, `1M`.
- `limit`: quantidade de candles a buscar (máximo 1000).
- `timeout`: timeout da requisição em segundos.

Os dados da Binance são retornados como uma série temporal com a coluna `btc_close` (preço de fechamento).

## `processamento`
- `remover_duplicados`: remove datas repetidas no índice temporal.
- `estrategia_valores_faltantes`: `remove`, `fill_zero` ou `keep`.
- `normalizar_nomes_colunas`: padroniza nomes (minúsculas e `_`).

## `dados`
- `tendencias`: colunas que serão treinadas.

Se não informar, o sistema tenta usar todas as colunas de valor disponíveis.

## `divisao`
- `porcentagem_avaliacao`: porcentagem dos dados usados para avaliação (0-100). O restante será automaticamente usado para treino.

O sistema divide os dados sequencialmente:
- Os primeiros registros (100% - `porcentagem_avaliacao`) são usados para treino.
- Os últimos `porcentagem_avaliacao`% dos registros são usados para avaliação.

Exemplo: com 1000 registros e `porcentagem_avaliacao: 20`:
- Treino: 800 primeiros registros (80%).
- Avaliação: 200 últimos registros (20%).

## `treinamento`
- `n_execucoes`: total de simulações testadas.
- `execucoes_por_rodada`: quantidade executada em paralelo em cada rodada.
- `top_k`: quantidade de melhores modelos mantidos.
- `mostrar_graficos`: campo de compatibilidade.
- `semente_aleatoria`: reprodutibilidade (`null` desativa).

## `modelo`
- `tipo`: modelo utilizado (`arima`).
- `intervalo_p`, `intervalo_d`, `intervalo_q`: espaço de busca dos parâmetros.
- `max_tentativas`: limite de tentativas internas para ajustar um modelo válido.

## `teste`
- `ordem_fixa`: ordem ARIMA usada quando `execucao.modo = teste`.

## `saida`
- `pasta`: pasta base de saída.
- `arquivo_resultados`: arquivo texto final com ranking.
- `salvar_relatorio`: habilita/desabilita o relatório final.


## Modo Teste Com Ordem Fixa
Para validar um ARIMA específico:

1. defina `execucao.modo: "teste"`;
2. configure `teste.ordem_fixa`, por exemplo `[2, 1, 2]`;
3. execute `python scripts/iniciar_pesquisa.py`.

Nesse modo, o sistema executa uma simulação por tendência usando exatamente a ordem informada.

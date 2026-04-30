# Documentação de Configuração

Este documento descreve os campos do arquivo `config/config.yami`.

## Ordem de carregamento

1. Configuração base (`config/config.yami`)
2. Override opcional de experimento (`config/experiments/*.yaml`)
3. Variáveis de ambiente (ex.: token da API)

## data_source.type

Descrição:
Define a origem dos dados.

Tipo:
`string`

Obrigatório:
Sim

Valores aceitos:
- `local`
- `api`
- `google_trends`

Exemplo:

```yaml
data_source:
  type: "local"
```

## local_data.path

Descrição:
Caminho do arquivo quando `data_source.type = "local"`.

Tipo:
`string`

Obrigatório:
Sim quando `data_source.type = "local"`.

Exemplo:

```yaml
local_data:
  path: "data/input/pedicure_trends.csv"
```

## api_data.url

Descrição:
Endpoint para busca de dados por requisição HTTP.

Tipo:
`string`

Obrigatório:
Sim quando `data_source.type = "api"`.

Exemplo:

```yaml
api_data:
  url: "https://api.exemplo.com/dados"
```

## google_trends.keywords

Descrição:
Lista de termos para consulta no Google Trends via `pytrends`.

Tipo:
`list[string]`

Obrigatório:
Sim quando `data_source.type = "google_trends"`.

Valores aceitos:
De 1 até 5 termos.

Exemplo:

```yaml
google_trends:
  keywords:
    - "pedicure"
```

## google_trends.hl / google_trends.tz / google_trends.geo / google_trends.gprop

Descrição:
Parâmetros da consulta Trends.

Observações:
- Use `hl: "pt-BR"` (país em maiúsculo).
- `tz` em minutos (ex.: `360`).
- `geo: "BR"` para Brasil ou `""` para global.
- `gprop`: `""`, `images`, `news`, `youtube`, `froogle`.

## training.n_threads

Descrição:
Quantidade de threads/processos para execução.

Tipo:
`integer`

Obrigatório:
Não

Valor padrão:
`4`

Valores aceitos:
Inteiro `>= 1`

Observações:
Valores altos podem reduzir o tempo de execução, mas aumentam consumo de CPU.

## training.n_runs

Descrição:
Número total de execuções/tentativas do modelo.

Tipo:
`integer`

Obrigatório:
Não

Valor padrão:
`500`

Valores aceitos:
Inteiro `>= 1`

## model.p_range / model.d_range / model.q_range

Descrição:
Intervalos para geração aleatória dos parâmetros do ARIMA.

Tipo:
`list[2]`

Exemplo:

```yaml
model:
  p_range: [0, 30]
  d_range: [0, 2]
  q_range: [0, 30]
```

## output.resultados_txt

Descrição:
Arquivo de saída com ranking dos melhores resultados.

Tipo:
`string`

Exemplo:

```yaml
output:
  resultados_txt: "output/resultados_treinamento.txt"
```

## Boas práticas adotadas

- Campos agrupados por responsabilidade (`data_source`, `training`, `model`, `output`).
- Valores aceitos descritos no YAML e aqui.
- Segredos fora do YAML (`token_env` + variável de ambiente).
- Arquivo de exemplo versionável (`config/config.example.yaml`).
- Configurações de experimento separadas (`config/experiments/`).

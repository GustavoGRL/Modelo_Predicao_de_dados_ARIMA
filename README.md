# Predição de Tendências com ARIMA
Sistema em Python para treinamento, comparação e monitoramento de modelos ARIMA aplicados a séries temporais. O projeto automatiza a busca de combinações de parâmetros e exibe o progresso em dashboard web com Flask + Plotly.

## Visão Geral
O projeto recebe uma base temporal (CSV local), separa dados em treino e avaliação e executa várias simulações ARIMA para identificar os melhores modelos por menor erro de previsão.

O fluxo é orientado por configuração YAML (`config/config.yami`) e executado pelo script `scripts/iniciar_pesquisa.py`.

## O Que É ARIMA?
ARIMA é um modelo clássico para séries temporais, representado por `ARIMA(p, d, q)`:

- `AR` (AutoRegressive): usa valores passados da própria série.
- `I` (Integrated): aplica diferenciação para reduzir tendência/não estacionaridade.
- `MA` (Moving Average): modela o erro com base em erros passados.
- `p`: quantidade de termos autoregressivos.
- `d`: quantidade de diferenciações.
- `q`: quantidade de termos de média móvel.

Em termos práticos, o ARIMA tenta prever o próximo comportamento da série olhando o histórico, compensando tendência e considerando o padrão dos erros.

Neste projeto:
- o ajuste é feito com `statsmodels` (`statsmodels.tsa.arima.model.ARIMA`);
- os modelos são comparados principalmente por erro absoluto médio (`mean(abs(real - previsao))`);
- também são calculados `MAPE` e `sMAPE` para análise complementar.

## Objetivo Do Projeto
Automatizar a busca por bons parâmetros ARIMA sem que o usuário precise testar manualmente dezenas ou centenas de combinações.

## Principais Funcionalidades
- carregamento de dados locais em CSV;
- pré-processamento temporal e limpeza de dados;
- seleção de uma ou mais tendências (colunas) para treino;
- divisão temporal em treino e avaliação via datas do YAML;
- busca automática de parâmetros ARIMA no modo `treino`;
- modo `teste` com ordem fixa (`ordem_fixa`);
- ranking dos melhores resultados (`top_k`);
- geração de relatório em texto;
- dashboard em tempo real com estado, top 5, progresso, histórico e logs.

## Modelo De Avaliação
O sistema separa os dados em duas janelas temporais definidas no YAML:

- treino: tudo até `divisao.fim_treino`;
- avaliação: intervalo entre `divisao.inicio_avaliacao` e `divisao.fim_avaliacao`.

Para cada simulação:
- o modelo ARIMA é ajustado com a janela de treino;
- são geradas previsões para o tamanho da janela de avaliação;
- as previsões são comparadas com os valores reais da avaliação.

Métricas:
- principal: erro absoluto médio (`mean(abs(real - previsao))`);
- complementares: `MAPE` e `sMAPE`.

O ranking final prioriza os menores erros e mantém os melhores resultados conforme `treinamento.top_k`.

## Como Instalar
No diretório raiz:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Como Executar O Treinamento
1. Ajuste `config/config.yami`.
2. Execute:

```bash
python scripts/iniciar_pesquisa.py
```

O modo de execução vem de `execucao.modo`:
- `treino`: múltiplas simulações;
- `teste`: 1 execução com `teste.ordem_fixa`.

## Como Visualizar Resultados
Durante a execução:
- se `execucao.iniciar_dashboard_automaticamente: true`, o dashboard abre automaticamente;
- caso contrário, rode manualmente:

```bash
python -m src.view.visualizador_dash
```

URL padrão:
- `http://127.0.0.1:8004`

Arquivos gerados:
- `output/estado_treinamento.json`: estado corrente para o dashboard;
- `output/histórico_rodadas.csv`: evolução por rodada;
- `output/resultados_treinamento.txt`: ranking final.

## Dashboard
O dashboard lê o estado e mostra:
- status da execução;
- modo de execução;
- rodada atual e total;
- execuções concluídas;
- melhor erro e melhor parâmetro ARIMA;
- tendência em treino;
- top 5 modelos;
- histórico do melhor erro por rodada;
- período de treino/avaliação;
- logs da execução.

Esses dados são alimentados por `GerenciadorResultados`, que consolida e persiste JSON/CSV durante o treinamento.

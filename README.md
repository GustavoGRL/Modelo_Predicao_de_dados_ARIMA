# Predição de Tendências com ARIMA
Sistema em Python para treinamento, comparação e monitoramento de modelos ARIMA aplicados a séries temporais. O projeto automatiza a busca de combinações de parâmetros e exibe o progresso em dashboard web com Flask + Plotly.

## Visão Geral
O projeto recebe dados temporais de duas fontes: arquivo CSV local ou API da Binance (criptomoedas). Separa os dados em treino e avaliação e executa várias simulações ARIMA para identificar os melhores modelos por menor erro de previsão.

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
- busca de dados em tempo real da API da Binance (criptomoedas);
- pré-processamento temporal e limpeza de dados;
- seleção de uma ou mais tendências (colunas) para treino;
- divisão temporal em treino e avaliação via porcentagem de avaliação;
- busca automática de parâmetros ARIMA no modo `treino`;
- modo `teste` com ordem fixa (`ordem_fixa`);
- ranking dos melhores resultados (`top_k`);
- geração de relatório em texto;
- dashboard em tempo real com estado, top 5, progresso, histórico e logs.

## Modelo De Avaliação
O sistema separa os dados usando apenas a porcentagem de avaliação definida no YAML:

- avaliação: `divisao.porcentagem_avaliacao`% dos últimos registros;
- treino: o restante dos registros (100% - porcentagem de avaliação).

Para cada simulação:
- o modelo ARIMA é ajustado com a janela de treino;
- são geradas previsões para o tamanho da janela de avaliação;
- as previsões são comparadas com os valores reais da avaliação.

Métricas:
- principal: erro absoluto médio (`mean(abs(real - previsao))`);
- complementares: `MAPE` e `sMAPE`.

O ranking final prioriza os menores erros e mantém os melhores resultados conforme `treinamento.top_k`.

Exemplo: com 1000 registros e `porcentagem_avaliacao: 20`:
- Treino: 800 primeiros registros (80%).
- Avaliação: 200 últimos registros (20%).

## Como Instalar
No diretório raiz:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Fontes De Dados
O sistema suporta duas fontes de dados:

### 1. Arquivo CSV Local
- Configure `fonte_dados.tipo: "local"`
- Especifique o caminho do arquivo em `dados_locais.caminho`
- O arquivo deve conter uma coluna temporal e uma ou mais colunas numéricas

### 2. API da Binance (Criptomoedas)
- Configure `fonte_dados.tipo: "binance"`
- Especifique os parâmetros em `dados_binance`:
  - `symbol`: Par de moedas (ex.: "BTCUSDT", "ETHUSDT")
  - `interval`: Intervalo dos candles (ex.: "1h", "4h", "1d")
  - `limit`: Quantidade de candles (máximo 1000)
  - `timeout`: Timeout da requisição em segundos

Os dados da Binance são automaticamente convertidos para o formato do sistema, com a coluna `btc_close` representando o preço de fechamento.

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

## Modo Demo de 7 Dias
O sistema agora inclui um modo de demonstração que executa o treinamento ARIMA uma vez por dia durante 7 dias, com memória de parâmetros contínua entre execuções.

### Funcionamento
1. **Busca de dados**: Em cada dia, o sistema busca os últimos 30 dias de dados de BTC (ou outra fonte configurada).
2. **Divisão treino/avaliação**: 
   - Primeiros 28 dias = treino
   - Últimos 2 dias = avaliação
3. **Teste de parâmetros**:
   - Parâmetros aleatórios normalmente
   - Parâmetros herdados do dia anterior (reavaliados)
4. **Classificação de resultados**:
   - **Destaques do dia**: Melhores parâmetros considerando apenas a execução atual
   - **Consolidados 2 dias**: Parâmetros herdados reavaliados com média entre resultado anterior e atual
   - **Candidatos próximo dia**: Combinação dos melhores consolidados e destaques
5. **Memória contínua**: Os resultados são salvos em `output/memoria_parametros.json` para uso no próximo dia.

### Regras importantes
- Um parâmetro novo aleatório pode ser destaque do dia, mas só vira consolidado no próximo ciclo, quando for testado novamente.
- A métrica principal para ordenação é o sMAPE (menor é melhor).
- Se sMAPE for None, usa MAPE. Se MAPE também for None, usa erro absoluto.
- Parâmetros duplicados são removidos pela tupla (p, d, q).

### Como executar
```bash
python scripts/executar_demo_7_dias.py --config config/config.yami --dias 7 --intervalo-horas 24 --sem-espera-inicial
```

### Opções disponíveis
- `--config`: Caminho para o arquivo de configuração (padrão: config/config.yami)
- `--dias`: Número total de dias para executar (padrão: 7)
- `--intervalo-horas`: Intervalo entre execuções em horas (padrão: 24)
- `--sem-espera-inicial`: Executar imediatamente o primeiro ciclo sem esperar
- `--modo`: Modo de execução: treino ou teste (padrão: treino)
- `--sem-dashboard`: Não iniciar o dashboard automaticamente

### Exemplos
```bash
# Demo padrão de 7 dias
python scripts/executar_demo_7_dias.py --config config/config.yami --dias 7 --intervalo-horas 24

# Demo de 3 dias com intervalo de 12 horas
python scripts/executar_demo_7_dias.py --config config/config.yami --dias 3 --intervalo-horas 12 --sem-espera-inicial

# Demo sem dashboard automático
python scripts/executar_demo_7_dias.py --config config/config.yami --modo treino --sem-dashboard
```

### Logs e monitoramento
- Logs da demo: `output/demo_7_dias.log`
- Estado do treinamento: `output/estado_treinamento.json`
- Memória de parâmetros: `output/memoria_parametros.json`

### Dashboard atualizado
O dashboard agora inclui novas seções:
- **Memória de Parâmetros**: Configuração e status da memória
- **Destaques do Dia**: Top 30 melhores parâmetros da execução atual
- **Consolidados 2 Dias**: Parâmetros com média entre dois dias consecutivos
- **Candidatos Próximo Dia**: Parâmetros selecionados para o próximo ciclo

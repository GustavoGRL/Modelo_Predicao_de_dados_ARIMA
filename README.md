# Predição de Tendências com ARIMA

Projeto com arquitetura orientada a classes, configuração central via YAML e execução única por `iniciar_pesquisa.py`.

## Estrutura Atual

- `src/arima_training/`
  - `arima_model.py`: classe `ARIMAModel` para gerar parâmetros aleatórios e ajustar o ARIMA.
  - `training_manager.py`: classe `TrainingManager` para orquestrar treino, seleção de melhores, gráficos e saída em texto.
  - `data_loader.py`: suporte para fonte local, API HTTP e Google Trends (`pytrends`).
- `iniciar_pesquisa.py`: ponto único de entrada do sistema.
- `config/config.yami`: configuração principal.
- `config/experiments/*.yaml`: overrides de experimento.
- `data/input/pedicure_trends.csv`: exemplo de base local.
- `output/resultados_treinamento.txt`: resultados finais.

## Como Executar

No diretório raiz do projeto:

```bash
python iniciar_pesquisa.py --modo parallel
python iniciar_pesquisa.py --modo individual
python iniciar_pesquisa.py --modo test
python iniciar_pesquisa.py --modo parallel --experiment config/experiments/google_trends_basico.yaml
```

## Configuração

Edite `config/config.yami` para controlar:

- fonte de dados (`data_source.type`): `local`, `api`, `google_trends`;
- número de threads (`training.n_threads`);
- número de execuções (`training.n_runs`);
- execuções por rodada (`training.runs_per_round`);
- número máximo de trends simultâneas (`training.max_trends_simultaneas`);
- intervalos de parâmetros ARIMA (`model.p_range`, `model.d_range`, `model.q_range`);
- ordem fixa para teste (`test.fixed_order`).

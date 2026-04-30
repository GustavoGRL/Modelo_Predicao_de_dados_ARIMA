import random

import numpy as np
from statsmodels.tsa.arima.model import ARIMA


class ARIMAModel:
    """Classe responsável por gerar parâmetros e aplicar o ARIMA."""

    def __init__(self, p_range, q_range, d_range, max_retries=40):
        self.p_range = tuple(p_range)
        self.q_range = tuple(q_range)
        self.d_range = tuple(d_range)
        self.max_retries = max_retries

    def gerar_parametros_aleatorios(self):
        p = random.randint(self.p_range[0], self.p_range[1])
        d = random.randint(self.d_range[0], self.d_range[1])
        q = random.randint(self.q_range[0], self.q_range[1])
        return p, d, q

    def aplicar_modelo(self, serie_treino, steps, ordem_fixa=None):
        ultima_excecao = None
        tentativas = self.max_retries if ordem_fixa is None else 1

        for _ in range(tentativas):
            try:
                ordem = tuple(ordem_fixa) if ordem_fixa else self.gerar_parametros_aleatorios()
                model = ARIMA(serie_treino, order=ordem)
                model_analise = model.fit()
                forecast = model_analise.forecast(steps=steps)
                return np.array(forecast, dtype=float), list(ordem)
            except (ValueError, np.linalg.LinAlgError) as exc:
                ultima_excecao = exc

        raise RuntimeError(
            f"Falha ao ajustar ARIMA após {tentativas} tentativa(s)."
        ) from ultima_excecao

    @staticmethod
    def calcular_media_erro_absoluto(previsoes, reais):
        previsoes = np.array(previsoes, dtype=float)
        reais = np.array(reais, dtype=float)
        return float(np.mean(np.abs(reais - previsoes)))


def executar_simulacao_uma_vez(serie_treino, serie_avaliacao, model_config, ordem_fixa=None):
    random_seed = model_config.get("random_seed")
    if random_seed is not None:
        random.seed(int(random_seed))
        np.random.seed(int(random_seed))

    modelo = ARIMAModel(
        p_range=model_config["p_range"],
        q_range=model_config["q_range"],
        d_range=model_config["d_range"],
        max_retries=model_config.get("max_retries", 40),
    )
    previsoes, parametros = modelo.aplicar_modelo(
        serie_treino, steps=len(serie_avaliacao), ordem_fixa=ordem_fixa
    )
    media_erro = modelo.calcular_media_erro_absoluto(previsoes, serie_avaliacao.values)
    return {"erro": media_erro, "parametros": parametros, "previsoes": previsoes.tolist()}

import random
import warnings

import numpy as np
from statsmodels.tools.sm_exceptions import ConvergenceWarning, ValueWarning
from statsmodels.tsa.arima.model import ARIMA

MAX_TENTATIVAS_PADRAO = 40


class ModeloArima:
    """Classe responsável por gerar parâmetros e aplicar o ARIMA."""

    def __init__(self, intervalo_p, intervalo_q, intervalo_d, max_tentativas=MAX_TENTATIVAS_PADRAO):
        self.intervalo_p = tuple(intervalo_p)
        self.intervalo_q = tuple(intervalo_q)
        self.intervalo_d = tuple(intervalo_d)
        self.max_tentativas = max_tentativas

    def gerar_parametros_aleatorios(self):
        p = random.randint(self.intervalo_p[0], self.intervalo_p[1])
        d = random.randint(self.intervalo_d[0], self.intervalo_d[1])
        q = random.randint(self.intervalo_q[0], self.intervalo_q[1])
        return p, d, q

    def aplicar_modelo(self, serie_treino, passos_previsao, ordem_fixa):
        ultima_excecao = None
        tentativas = self.max_tentativas if ordem_fixa is None else 1

        for aux in range(tentativas):
            try:

                ordem = tuple(ordem_fixa) if ordem_fixa else self.gerar_parametros_aleatorios()
                model = ARIMA(serie_treino, order=ordem)

                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=ConvergenceWarning)
                    warnings.filterwarnings("ignore", category=ValueWarning)
                    warnings.filterwarnings("ignore", category=UserWarning)

                    modelo_ajustado = model.fit()

                previsao = modelo_ajustado.forecast(steps=passos_previsao)

                coeficientes_modelo = [
                    float(valor) for valor in np.array(modelo_ajustado.params, dtype=float).tolist()
                ]


                return np.array(previsao, dtype=float), list(ordem), coeficientes_modelo
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

    @staticmethod
    def calcular_mape(previsoes, reais):
        previsoes = np.array(previsoes, dtype=float)
        reais = np.array(reais, dtype=float)

        mascara = np.abs(reais) > 1e-8
        if not np.any(mascara):
            return None

        return float(
            np.mean(np.abs((reais[mascara] - previsoes[mascara]) / reais[mascara])) * 100
        )

    @staticmethod
    def calcular_smape(previsoes, reais):
        previsoes = np.array(previsoes, dtype=float)
        reais = np.array(reais, dtype=float)

        denominador = np.abs(reais) + np.abs(previsoes)
        mascara = denominador > 1e-8
        if not np.any(mascara):
            return None

        return float(
            np.mean((2 * np.abs(reais[mascara] - previsoes[mascara]) / denominador[mascara]))
            * 100
        )


def executar_simulacao_unica(serie_treino, serie_avaliacao, configuracao_modelo, ordem_fixa=None):

    semente_aleatoria = configuracao_modelo.get("semente_aleatoria")

    if semente_aleatoria is not None:
        random.seed(int(semente_aleatoria))
        np.random.seed(int(semente_aleatoria))

    modelo = ModeloArima(
        intervalo_p=configuracao_modelo["intervalo_p"],
        intervalo_q=configuracao_modelo["intervalo_q"],
        intervalo_d=configuracao_modelo["intervalo_d"],
        max_tentativas=configuracao_modelo.get("max_tentativas", MAX_TENTATIVAS_PADRAO),
    )
    previsoes, parametros, coeficientes_modelo = modelo.aplicar_modelo(
        serie_treino, passos_previsao=len(serie_avaliacao), ordem_fixa=ordem_fixa
    )
    media_erro = modelo.calcular_media_erro_absoluto(previsoes, serie_avaliacao.values)
    mape = modelo.calcular_mape(previsoes, serie_avaliacao.values)
    smape = modelo.calcular_smape(previsoes, serie_avaliacao.values)

    return {
        "erro": media_erro,
        "mape": mape,
        "smape": smape,
        "parametros": parametros,
        "previsoes": previsoes.tolist(),
        "coeficientes_modelo": coeficientes_modelo,
    }


# Alias de compatibilidade para integrações existentes
ARIMAModel = ModeloArima
executar_simulacao_uma_vez = executar_simulacao_unica

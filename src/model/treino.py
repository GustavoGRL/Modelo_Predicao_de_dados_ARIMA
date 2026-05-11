from concurrent.futures import ProcessPoolExecutor, as_completed

from .arima_modelo import executar_simulacao_unica
from .carregar_dados import CarregadorDados
from .gerenciador_configuracao import GerenciadorConfiguracao
from .gerenciador_resultados import GerenciadorResultados


class GerenciadorTreinamento:
    """Orquestra o fluxo de treinamento e monitoramento das tendências."""

    MODO_PADRAO = "treino"
    MODOS_VALIDOS = {
        "treino": "treino",
        "teste": "teste",
    }

    def __init__(self, caminho_configuracao):
        self.gerenciador_configuracao = GerenciadorConfiguracao(
            caminho_configuracao=caminho_configuracao,
        )
        self.configuracao = self.gerenciador_configuracao.carregar_configuracao()
        self.raiz_projeto = self.gerenciador_configuracao.raiz_projeto
        self.carregador_dados = CarregadorDados()
        self.gerenciador_resultados = GerenciadorResultados(
            gerenciador_configuracao=self.gerenciador_configuracao,
        )

    def carregar_base(self):
        """Carrega os dados brutos e aplica o pré-processamento configurado."""
        dados = self._carregar_dados_por_fonte()
        return self.carregador_dados.aplicar_preprocessamento(
            dados,
            self.configuracao.get("processamento", {}),
        )

    def executar(self, modo="treino"):
        """Executa o treinamento para todas as tendências configuradas."""
        modo_normalizado = self._normalizar_modo(modo)
        dados = self.carregar_base()
        trends_configuradas = self._obter_trends_configuradas(dados)

        resultados_finais = {}
        caminho_estado, caminho_historico = (
            self.gerenciador_resultados.criar_caminhos_monitoramento(
                self.configuracao["saida"]
            )
        )
        self.gerenciador_resultados.inicializar_historico_csv(caminho_historico)

        # As tendências são processadas uma por vez. O paralelismo acontece dentro
        # de cada rodada, executando todas as tentativas em processos separados.
        for trend in trends_configuradas:
            resultados_finais[trend] = self._treinar_trend(
                trend,
                dados[trend],
                modo_normalizado,
                caminho_estado,
                caminho_historico,
            )

        self.gerenciador_resultados.salvar_resultados_txt(
            resultados_finais=resultados_finais,
            modo=modo_normalizado,
            configuracao_saida=self.configuracao["saida"],
        )
        return resultados_finais

    def _carregar_dados_por_fonte(self):
        """Carrega dados fornecidos pelo usuário a partir de arquivo local."""
        tipo_fonte = self.configuracao["fonte_dados"]["tipo"]

        if tipo_fonte != "local":
            raise ValueError(
                "Apenas fonte_dados.tipo='local' é suportado. "
                "Forneça um arquivo CSV local em dados_locais.caminho."
            )

        return self.carregador_dados.carregar_dados_locais(
            configuracao_dados_locais=self.configuracao["dados_locais"],
            raiz_projeto=self.raiz_projeto,
        )

    def _obter_trends_configuradas(self, dados):
        """Normaliza e valida a lista de tendências que será treinada."""
        trends_configuradas = self.configuracao.get("dados", {}).get("tendencias")
        if not trends_configuradas:
            trends_configuradas = list(dados.columns)

        trends_configuradas = [
            self.carregador_dados.normalizar_nome_coluna(trend)
            for trend in trends_configuradas
        ]
        trends_invalidas = [
            trend for trend in trends_configuradas if trend not in dados.columns
        ]
        if trends_invalidas:
            raise ValueError(
                f"Trends não encontradas na base carregada: {trends_invalidas}"
            )

        return trends_configuradas

    @classmethod
    def _normalizar_modo(cls, modo):
        """Converte aliases de modo para os nomes internos padronizados."""
        if modo not in cls.MODOS_VALIDOS:
            raise ValueError("Modo inválido. Valores aceitos: treino, teste.")
        return cls.MODOS_VALIDOS[modo]

    def _dividir_serie(self, serie):
        """Separa a série em janela de treino e janela de avaliação."""
        configuracao_divisao = self.configuracao["divisao"]
        serie_treino = serie[serie.index <= configuracao_divisao["fim_treino"]]
        serie_avaliacao = serie[
            (serie.index >= configuracao_divisao["inicio_avaliacao"])
            & (serie.index <= configuracao_divisao["fim_avaliacao"])
        ]

        if serie_treino.empty or serie_avaliacao.empty:
            raise ValueError(
                "Séries de treino/avaliação vazias. Verifique as datas no config."
            )

        return serie_treino, serie_avaliacao

    def _obter_parametros_execucao(self, modo, configuracao_treino):
        """Define quantidade de execuções e ordem fixa conforme o modo escolhido."""
        if modo == "teste":
            return {
                "execucoes": 1,
                "execucoes_por_rodada": 1,
                "ordem_fixa": self.configuracao["teste"]["ordem_fixa"],
            }

        return {
            "execucoes": int(configuracao_treino["n_execucoes"]),
            "execucoes_por_rodada": int(configuracao_treino["execucoes_por_rodada"]),
            "ordem_fixa": None,
        }

    @staticmethod
    def _criar_configuracao_execucao(configuracao_modelo, configuracao_treino, concluido, indice):
        """Cria a configuração usada em uma simulação individual."""
        configuracao_execucao = dict(configuracao_modelo)
        base_seed = configuracao_treino.get("semente_aleatoria")

        if base_seed is not None:
            configuracao_execucao["semente_aleatoria"] = int(base_seed) + concluido + indice

        return configuracao_execucao

    def _executar_rodada(
        self,
        treino,
        avaliacao,
        configuracao_modelo,
        configuracao_treino,
        ordem_fixa,
        quantidade_execucoes,
        concluido,
    ):
        """Executa todas as simulações de uma rodada e retorna resultados e falhas."""
        resultados_rodada = []
        erros_rodada = []
        falhas_rodada = 0
        mensagens_falha = []
        max_workers = max(1, int(quantidade_execucoes))

        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futuros = []
            for indice in range(quantidade_execucoes):
                configuracao_execucao = self._criar_configuracao_execucao(
                    configuracao_modelo=configuracao_modelo,
                    configuracao_treino=configuracao_treino,
                    concluido=concluido,
                    indice=indice,
                )
                futuros.append(
                    executor.submit(
                        executar_simulacao_unica,
                        treino,
                        avaliacao,
                        configuracao_execucao,
                        ordem_fixa,
                    )
                )

            for futuro in as_completed(futuros):
                try:
                    resultado = futuro.result()
                    resultados_rodada.append(resultado)
                    erros_rodada.append(float(resultado["erro"]))
                except Exception as erro:
                    falhas_rodada += 1
                    mensagens_falha.append(str(erro))

        return resultados_rodada, erros_rodada, falhas_rodada, mensagens_falha

    def _treinar_trend(self, nome_trend, serie, modo, caminho_estado, caminho_historico):
        """Executa todas as rodadas de treino para uma tendência específica."""
        treino, avaliacao = self._dividir_serie(serie)
        configuracao_treino = self.configuracao["treinamento"]
        configuracao_modelo = dict(self.configuracao["modelo"])
        configuracao_modelo["semente_aleatoria"] = configuracao_treino.get("semente_aleatoria")

        parametros_execucao = self._obter_parametros_execucao(modo, configuracao_treino)
        execucoes = parametros_execucao["execucoes"]
        execucoes_por_rodada = parametros_execucao["execucoes_por_rodada"]
        ordem_fixa = parametros_execucao["ordem_fixa"]

        melhores = []
        concluidas = 0
        melhor_erro_anterior = None
        total_rodadas = max(
            1,
            (execucoes + execucoes_por_rodada - 1) // execucoes_por_rodada,
        )
        estado = self.gerenciador_resultados.inicializar_estado(
            nome_tendencia=nome_trend,
            modo=modo,
            total_rodadas=total_rodadas,
            total_execucoes=execucoes,
            treino=treino,
            avaliacao=avaliacao,
            configuracao_treino=configuracao_treino,
            configuracao_modelo=configuracao_modelo,
        )

        self.gerenciador_resultados.registrar_log(
            estado,
            f"Execução iniciada para tendência: {nome_trend} no modo {modo}.",
        )

        self.gerenciador_resultados.salvar_estado_json(caminho_estado, estado)

        for rodada in range(total_rodadas):
            quantidade_execucoes = min(execucoes_por_rodada, execucoes - concluidas)
            if quantidade_execucoes <= 0:
                break

            numero_rodada = rodada + 1
            estado["rodada_atual"] = numero_rodada

            self.gerenciador_resultados.registrar_log(
                estado,
                f"Rodada {numero_rodada}/{total_rodadas} iniciada com {quantidade_execucoes} tentativa(s) em paralelo.",
            )

            self.gerenciador_resultados.salvar_estado_json(caminho_estado, estado)

            (
                resultados_rodada,
                erros_rodada,
                falhas_rodada,
                mensagens_falha,
            ) = self._executar_rodada(
                treino=treino,
                avaliacao=avaliacao,
                configuracao_modelo=configuracao_modelo,
                configuracao_treino=configuracao_treino,
                ordem_fixa=ordem_fixa,
                quantidade_execucoes=quantidade_execucoes,
                concluido=concluidas,
            )

            for mensagem_falha in mensagens_falha:
                self.gerenciador_resultados.registrar_log(
                    estado,
                    f"Falha em simulação da rodada: {mensagem_falha}",
                )

            melhores.extend(resultados_rodada)
            melhores = sorted(melhores, key=lambda item: item["erro"])[
                : int(configuracao_treino["top_k"])
            ]
            concluidas += quantidade_execucoes

            resumo_rodada, melhor_erro_anterior = (
                self.gerenciador_resultados.atualizar_estado_apos_rodada(
                estado=estado,
                melhores=melhores,
                rodada_atual=numero_rodada,
                total_rodadas=total_rodadas,
                concluidas=concluidas,
                total_execucoes=execucoes,
                erros_rodada=erros_rodada,
                testados=quantidade_execucoes,
                falhas=falhas_rodada,
                melhor_anterior=melhor_erro_anterior,
            ))
            self.gerenciador_resultados.anexar_historico_csv(
                caminho_historico=caminho_historico,
                nome_trend=nome_trend,
                resumo_rodada=resumo_rodada,
                melhor_erro_geral=estado["melhor_erro"],
            )

            self.gerenciador_resultados.registrar_log(
                estado,
                f"Rodada {numero_rodada} finalizada: válidos={resumo_rodada['validos']}, falhas={falhas_rodada}.",
            )

            self.gerenciador_resultados.salvar_estado_json(caminho_estado, estado)

        estado["status"] = "concluido"
        self.gerenciador_resultados.registrar_log(estado, "Treinamento concluído.")
        self.gerenciador_resultados.salvar_estado_json(caminho_estado, estado)
        return melhores

from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import timedelta

from .arima_modelo import executar_simulacao_unica
from .carregar_dados import CarregadorDados
from .gerenciador_configuracao import GerenciadorConfiguracao
from .gerenciador_resultados import GerenciadorResultados
from .gerenciador_memoria_parametros import GerenciadorMemoriaParametros


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
        caminho_estado = self.gerenciador_resultados.criar_caminhos_monitoramento(
            self.configuracao["saida"]
        )

        # As tendências são processadas uma por vez. O paralelismo acontece dentro
        # de cada rodada, executando todas as tentativas em processos separados.
        for trend in trends_configuradas:
            resultados_finais[trend] = self._treinar_trend(
                trend,
                dados[trend],
                modo_normalizado,
                caminho_estado,
            )

        self.gerenciador_resultados.salvar_resultados_txt(
            resultados_finais=resultados_finais,
            modo=modo_normalizado,
            configuracao_saida=self.configuracao["saida"],
        )
        return resultados_finais

    def _carregar_dados_por_fonte(self):
        """Carrega dados fornecidos pelo usuário a partir da fonte configurada."""
        tipo_fonte = self.configuracao["fonte_dados"]["tipo"]

        if tipo_fonte == "local":
            return self.carregador_dados.carregar_dados_locais(
                configuracao_dados_locais=self.configuracao["dados_locais"],
                raiz_projeto=self.raiz_projeto,
            )
        elif tipo_fonte == "binance":
            configuracao_binance = self.configuracao["dados_binance"]
            return self.carregador_dados.carregar_dados_binance(
                symbol=configuracao_binance.get("symbol", "BTCUSDT"),
                interval=configuracao_binance.get("interval", "1h"),
                limit=int(configuracao_binance.get("limit", 720)),
                timeout=int(configuracao_binance.get("timeout", 15)),
            )
        else:
            raise ValueError(
                f"Fonte de dados inválida: '{tipo_fonte}'. "
                "Valores aceitos: local, binance."
            )

    def _obter_trends_configuradas(self, dados):
        """Normaliza e valida a lista de tendências que será treinada."""
        trends_configuradas = self.configuracao.get("dados", {}).get("tendencias")
        
        # Se não houver tendências configuradas, usar todas as colunas disponíveis
        if not trends_configuradas:
            trends_configuradas = list(dados.columns)
        
        # Normalizar nomes das tendências
        trends_configuradas = [
            self.carregador_dados.normalizar_nome_coluna(trend)
            for trend in trends_configuradas
        ]
        
        # Para dados da Binance, se a coluna 'btc_close' estiver presente,
        # permitir que seja usada mesmo se não estiver explicitamente configurada
        tipo_fonte = self.configuracao["fonte_dados"]["tipo"]
        if tipo_fonte == "binance" and "btc_close" in dados.columns:
            # Se 'btc_close' não estiver na lista de tendências configuradas, adicioná-la
            if "btc_close" not in trends_configuradas:
                trends_configuradas.append("btc_close")
        
        # Validar se as tendências configuradas existem nos dados
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
        # Verificar se avaliação dinâmica está habilitada
        avaliacao_dinamica = self.configuracao.get("avaliacao_dinamica", {})
        if avaliacao_dinamica.get("habilitada", False):
            return self._dividir_serie_dinamica(serie, avaliacao_dinamica)
        else:
            return self._dividir_serie_porcentagem(serie)
    
    def _dividir_serie_porcentagem(self, serie):
        """Separa a série usando porcentagem de avaliação configurada."""
        configuracao_divisao = self.configuracao["divisao"]
        porcentagem_avaliacao = float(configuracao_divisao["porcentagem_avaliacao"])
        
        # Calcular o número total de registros
        total_registros = len(serie)
        
        # Calcular quantos registros serão usados para avaliação
        registros_avaliacao = int(total_registros * (porcentagem_avaliacao / 100))
        
        # O restante dos registros será usado para treino
        registros_treino = total_registros - registros_avaliacao
        
        # Verificar se temos registros suficientes
        if registros_treino <= 0:
            raise ValueError(
                f"Porcentagem de avaliação ({porcentagem_avaliacao}%) resulta em 0 registros para treino. "
                f"Diminua a porcentagem de avaliação ou use mais dados."
            )
        
        if registros_avaliacao <= 0:
            raise ValueError(
                f"Porcentagem de avaliação ({porcentagem_avaliacao}%) resulta em 0 registros para avaliação. "
                f"Aumente a porcentagem de avaliação ou use mais dados."
            )
        
        # Verificar se a porcentagem de avaliação não ultrapassa 100%
        if porcentagem_avaliacao > 100:
            raise ValueError(
                f"Porcentagem de avaliação ({porcentagem_avaliacao}%) não pode ultrapassar 100%."
            )
        
        # Dividir a série: os primeiros registros são para treino, os seguintes para avaliação
        serie_treino = serie.iloc[:registros_treino]
        serie_avaliacao = serie.iloc[registros_treino:registros_treino + registros_avaliacao]
        
        if serie_treino.empty or serie_avaliacao.empty:
            raise ValueError(
                "Séries de treino/avaliação vazias. Verifique a porcentagem de avaliação no config."
            )

        return serie_treino, serie_avaliacao
    
    def _dividir_serie_dinamica(self, serie, configuracao_avaliacao):
        """Separa a série usando os últimos N dias para avaliação."""
        # Ordenar a série pelo índice temporal
        serie = serie.sort_index()
        
        # Obter datas de início e fim
        data_final = serie.index.max()
        avaliacao_dias = int(configuracao_avaliacao.get("avaliacao_dias", 2))
        
        # Calcular início do período de avaliação
        inicio_avaliacao = data_final - timedelta(days=avaliacao_dias)
        
        # Separar treino e avaliação
        serie_treino = serie[serie.index < inicio_avaliacao]
        serie_avaliacao = serie[serie.index >= inicio_avaliacao]
        
        # Validar se temos dados suficientes
        if serie_treino.empty:
            raise ValueError(
                f"Série de treino vazia. Não há dados antes de {inicio_avaliacao}."
            )
        
        if serie_avaliacao.empty:
            raise ValueError(
                f"Série de avaliação vazia. Não há dados a partir de {inicio_avaliacao}."
            )
        
        # Validar janela histórica mínima
        janela_historica_dias = int(configuracao_avaliacao.get("janela_historica_dias", 30))
        dias_totais = (data_final - serie.index.min()).days
        
        if dias_totais < janela_historica_dias:
            raise ValueError(
                f"Dados insuficientes: {dias_totais} dias disponíveis, "
                f"mas janela histórica requer {janela_historica_dias} dias."
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

    def _executar_parametros_herdados(
        self,
        treino,
        avaliacao,
        configuracao_modelo,
        parametros_herdados,
    ):
        """Executa simulações com parâmetros herdados do dia anterior."""
        resultados_herdados = []
        erros_herdados = []
        falhas_herdados = 0
        mensagens_falha = []
        
        for params in parametros_herdados:
            try:
                configuracao_execucao = dict(configuracao_modelo)
                resultado = executar_simulacao_unica(
                    treino,
                    avaliacao,
                    configuracao_execucao,
                    ordem_fixa=params,
                )
                resultado["origem"] = "herdado"
                resultados_herdados.append(resultado)
                erros_herdados.append(float(resultado["erro"]))
            except Exception as erro:
                falhas_herdados += 1
                mensagens_falha.append(str(erro))
        
        return resultados_herdados, erros_herdados, falhas_herdados, mensagens_falha

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
                    resultado["origem"] = "aleatorio"
                    resultados_rodada.append(resultado)
                    erros_rodada.append(float(resultado["erro"]))
                except Exception as erro:
                    falhas_rodada += 1
                    mensagens_falha.append(str(erro))

        return resultados_rodada, erros_rodada, falhas_rodada, mensagens_falha

    def _treinar_trend(self, nome_trend, serie, modo, caminho_estado):
        """Executa todas as rodadas de treino para uma tendência específica."""
        treino, avaliacao = self._dividir_serie(serie)
        configuracao_treino = self.configuracao["treinamento"]
        configuracao_modelo = dict(self.configuracao["modelo"])
        configuracao_modelo["semente_aleatoria"] = configuracao_treino.get("semente_aleatoria")

        # Verificar se memória de parâmetros está habilitada
        config_memoria = self.configuracao.get("memoria_parametros", {})
        memoria_habilitada = config_memoria.get("habilitada", False)
        
        # Inicializar gerenciador de memória se habilitado
        if memoria_habilitada:
            gerenciador_memoria = GerenciadorMemoriaParametros(
                caminho_memoria=config_memoria.get("caminho", "output/memoria_parametros.json"),
                raiz_projeto=self.raiz_projeto,
            )
            memoria_anterior = gerenciador_memoria.carregar_memoria()
            parametros_herdados = gerenciador_memoria.obter_parametros_herdados(memoria_anterior)
        else:
            gerenciador_memoria = None
            memoria_anterior = None
            parametros_herdados = []

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
            configuracao_divisao=self.configuracao["divisao"],
        )

        self.gerenciador_resultados.registrar_log(
            estado,
            f"Execução iniciada para tendência: {nome_trend} no modo {modo}.",
        )

        self.gerenciador_resultados.salvar_estado_json(caminho_estado, estado)

        # Executar parâmetros herdados primeiro (se houver)
        resultados_herdados = []
        erros_herdados = []
        falhas_herdados = 0
        
        if parametros_herdados:
            self.gerenciador_resultados.registrar_log(
                estado,
                f"Testando {len(parametros_herdados)} parâmetros herdados do dia anterior.",
            )
            
            (
                resultados_herdados,
                erros_herdados,
                falhas_herdados,
                mensagens_falha_herdados,
            ) = self._executar_parametros_herdados(
                treino=treino,
                avaliacao=avaliacao,
                configuracao_modelo=configuracao_modelo,
                parametros_herdados=parametros_herdados,
            )
            
            for mensagem_falha in mensagens_falha_herdados:
                self.gerenciador_resultados.registrar_log(
                    estado,
                    f"Falha em simulação herdada: {mensagem_falha}",
                )
            
            melhores.extend(resultados_herdados)
            melhores = sorted(melhores, key=lambda item: item["erro"])[
                : int(configuracao_treino["top_k"])
            ]
            
            self.gerenciador_resultados.registrar_log(
                estado,
                f"Parâmetros herdados testados: {len(resultados_herdados)} válidos, {falhas_herdados} falhas.",
            )
        
        # Executar rodadas normais com parâmetros aleatórios
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


            self.gerenciador_resultados.registrar_log(
                estado,
                f"Rodada {numero_rodada} finalizada: válidos={resumo_rodada['validos']}, falhas={falhas_rodada}.",
            )

            self.gerenciador_resultados.salvar_estado_json(caminho_estado, estado)

        estado["status"] = "concluido"
        self.gerenciador_resultados.registrar_log(estado, "Treinamento concluído.")
        
        # Se memória de parâmetros estiver habilitada, processar destaques e consolidados
        if memoria_habilitada and gerenciador_memoria:
            # Juntar todos os resultados (herdados + aleatórios)
            todos_resultados = resultados_herdados + melhores
            
            # Criar destaques do dia
            quantidade_destaques = config_memoria.get("quantidade_destaques_dia", 30)
            destaques_dia = gerenciador_memoria.criar_destaques_dia(
                todos_resultados,
                limite=quantidade_destaques
            )
            
            # Criar consolidados de 2 dias
            quantidade_consolidados = config_memoria.get("quantidade_consolidados", 30)
            consolidados_2dias = gerenciador_memoria.criar_consolidados(
                todos_resultados,
                memoria_anterior,
                limite=quantidade_consolidados,
                metrica_principal=config_memoria.get("metrica_principal", "smape")
            )
            
            # Criar candidatos para o próximo dia
            quantidade_candidatos = config_memoria.get("quantidade_candidatos_proximo_dia", 30)
            quantidade_consolidados_prox = config_memoria.get("quantidade_consolidados_para_proximo_dia", 15)
            quantidade_destaques_prox = config_memoria.get("quantidade_destaques_para_proximo_dia", 15)
            
            candidatos_proximo_dia = gerenciador_memoria.criar_candidatos_proximo_dia(
                destaques_dia,
                consolidados_2dias,
                limite_total=quantidade_candidatos,
                limite_consolidados=quantidade_consolidados_prox,
                limite_destaques=quantidade_destaques_prox
            )
            
            # Obter informações da fonte de dados
            simbolo = ""
            intervalo = ""
            if self.configuracao["fonte_dados"]["tipo"] == "binance":
                simbolo = self.configuracao["dados_binance"].get("symbol", "BTCUSDT")
                intervalo = self.configuracao["dados_binance"].get("interval", "1h")
            
            # Montar memória final
            configuracao_avaliacao = self.configuracao.get("avaliacao_dinamica", {})
            memoria_final = gerenciador_memoria.montar_memoria_final(
                simbolo=simbolo,
                intervalo=intervalo,
                janela_historica_dias=configuracao_avaliacao.get("janela_historica_dias", 30),
                avaliacao_dias=configuracao_avaliacao.get("avaliacao_dias", 2),
                destaques_dia=destaques_dia,
                consolidados_2dias=consolidados_2dias,
                candidatos_proximo_dia=candidatos_proximo_dia
            )
            
            # Salvar memória
            gerenciador_memoria.salvar_memoria(memoria_final)
            
            # Adicionar campos ao estado do dashboard
            estado["memoria_parametros"] = {
                "habilitada": True,
                "arquivo": str(gerenciador_memoria.caminho_memoria),
                "data_memoria_anterior": memoria_anterior.get("data_execucao", ""),
                "quantidade_herdados_testados": len(parametros_herdados),
                "quantidade_destaques_dia": len(destaques_dia),
                "quantidade_consolidados": len(consolidados_2dias)
            }
            estado["destaques_dia"] = destaques_dia
            estado["consolidados_2dias"] = consolidados_2dias
            estado["candidatos_proximo_dia"] = candidatos_proximo_dia
            
            self.gerenciador_resultados.registrar_log(
                estado,
                f"Memória de parâmetros salva com {len(candidatos_proximo_dia)} candidatos para o próximo dia.",
            )
        else:
            # Adicionar campos vazios para compatibilidade com o dashboard
            estado["memoria_parametros"] = {
                "habilitada": False,
                "arquivo": "",
                "data_memoria_anterior": "",
                "quantidade_herdados_testados": 0,
                "quantidade_destaques_dia": 0,
                "quantidade_consolidados": 0
            }
            estado["destaques_dia"] = []
            estado["consolidados_2dias"] = []
            estado["candidatos_proximo_dia"] = []
        
        self.gerenciador_resultados.salvar_estado_json(caminho_estado, estado)
        return melhores

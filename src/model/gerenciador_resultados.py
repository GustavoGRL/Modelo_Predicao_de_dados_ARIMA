from datetime import datetime
import json
from pathlib import Path
from threading import Lock


class GerenciadorResultados:
    """Centraliza a criação e atualização dos arquivos de saída do treinamento."""

    def __init__(self, gerenciador_configuracao):
        self.gerenciador_configuracao = gerenciador_configuracao
        self._monitoramento_lock = Lock()

    def criar_caminhos_monitoramento(self, configuracao_saida):
        """Resolve os caminhos fixos usados pelo view para monitoramento."""
        pasta_saida = Path(
            self.gerenciador_configuracao.resolver_caminho(
                configuracao_saida.get("pasta", "output")
            )
        )
        pasta_saida.mkdir(parents=True, exist_ok=True)

        caminho_estado = pasta_saida / "estado_treinamento.json"
        return caminho_estado

    @staticmethod
    def registrar_log(estado, mensagem):
        """Adiciona uma mensagem com timestamp ao buffer de logs do estado."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        estado["logs"].append(f"[{timestamp}] {mensagem}")
        estado["logs"] = estado["logs"][-100:]

    @staticmethod
    def _serializar_serie(serie):
        """Converte uma série temporal em estrutura simples para JSON."""
        return {
            "datas": [str(data) for data in serie.index.tolist()],
            "valores": [float(valor) for valor in serie.values.tolist()],
        }

    @staticmethod
    def _criar_resumo_periodos(treino, avaliacao):
        """Monta os metadados dos períodos usados no treinamento."""
        total_registros = len(treino) + len(avaliacao)
        porcentagem_treino = (len(treino) / total_registros) * 100 if total_registros > 0 else 0
        porcentagem_avaliacao = (len(avaliacao) / total_registros) * 100 if total_registros > 0 else 0
        
        return {
            "inicio_treino": str(treino.index.min()),
            "fim_treino": str(treino.index.max()),
            "inicio_avaliacao": str(avaliacao.index.min()),
            "fim_avaliacao": str(avaliacao.index.max()),
            "qtd_treino": int(len(treino)),
            "qtd_avaliacao": int(len(avaliacao)),
            "porcentagem_treino": round(porcentagem_treino, 2),
            "porcentagem_avaliacao": round(porcentagem_avaliacao, 2),
            "total_registros": int(total_registros),
        }

    @staticmethod
    def _criar_resumo_configuracao(configuracao_treino, configuracao_modelo):
        """Resume as configurações principais exibidas no view."""
        return {
            "execucoes_por_rodada": int(configuracao_treino.get("execucoes_por_rodada", 1)),
            "top_k": int(configuracao_treino.get("top_k", 5)),
            "semente_aleatoria": configuracao_treino.get("semente_aleatoria"),
            "intervalo_p": configuracao_modelo.get("intervalo_p"),
            "intervalo_d": configuracao_modelo.get("intervalo_d"),
            "intervalo_q": configuracao_modelo.get("intervalo_q"),
            "max_tentativas": configuracao_modelo.get("max_tentativas"),
        }

    def inicializar_estado(
        self,
        nome_tendencia,
        modo,
        total_rodadas,
        total_execucoes,
        treino,
        avaliacao,
        configuracao_treino,
        configuracao_modelo,
        configuracao_divisao,
    ):
        """Cria a estrutura inicial do arquivo de estado consumido pelo view."""
        return {
            "trend": nome_tendencia,
            "status": "rodando",
            "modo": modo,
            "rodada_atual": 0,
            "total_rodadas": total_rodadas,
            "execucoes_concluidas": 0,
            "execucoes_total": total_execucoes,
            "progresso_percentual": 0.0,
            "melhor_erro": None,
            "melhor_parametro": None,
            "configuracao_execucao": self._criar_resumo_configuracao(
                configuracao_treino,
                configuracao_modelo,
            ),
            "configuracao_divisao": {
                "porcentagem_treino": float(configuracao_divisao.get("porcentagem_treino", 80)),
                "porcentagem_avaliacao": float(configuracao_divisao.get("porcentagem_avaliacao", 20)),
            },
            "periodos": self._criar_resumo_periodos(treino, avaliacao),
            "treino": self._serializar_serie(treino),
            "avaliacao_real": self._serializar_serie(avaliacao),
            "resumo_rodada": {},
            "melhores": [],
            "historico_melhor_erro": [],
            "erros_rodada_atual": [],
            "logs": [],
        }

    def salvar_estado_json(self, caminho_estado, estado):
        """Persiste o estado atual do treinamento em JSON."""
        with self._monitoramento_lock:
            caminho_estado.write_text(
                json.dumps(estado, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )



    @staticmethod
    def _criar_melhores_para_dashboard(melhores):
        """Seleciona e formata os cinco melhores indivíduos para o view."""
        top_5 = melhores[:5]
        return [
            {
                "rank": indice + 1,
                "erro": float(item["erro"]),
                "mape": item.get("mape"),
                "smape": item.get("smape"),
                "parametros": item["parametros"],
                "previsoes": item["previsoes"],
                "coeficientes_modelo": item.get("coeficientes_modelo"),
            }
            for indice, item in enumerate(top_5)
        ]

    def atualizar_estado_apos_rodada(
        self,
        estado,
        melhores,
        rodada_atual,
        total_rodadas,
        concluidas,
        total_execucoes,
        erros_rodada,
        testados,
        falhas,
        melhor_anterior,
    ):
        """Atualiza métricas, ranking e progresso após o término de uma rodada."""
        melhor_erro_rodada = min(erros_rodada) if erros_rodada else None
        erro_medio_rodada = (sum(erros_rodada) / len(erros_rodada)) if erros_rodada else None
        pior_erro_rodada = max(erros_rodada) if erros_rodada else None
        melhor_atual = melhores[0]["erro"] if melhores else None
        novo_melhor_geral = (
            melhor_atual is not None
            and (melhor_anterior is None or melhor_atual < melhor_anterior)
        )

        estado["rodada_atual"] = rodada_atual
        estado["total_rodadas"] = total_rodadas
        estado["execucoes_concluidas"] = concluidas
        estado["execucoes_total"] = total_execucoes
        estado["progresso_percentual"] = (concluidas / total_execucoes) * 100
        estado["melhor_erro"] = melhor_atual
        estado["melhor_parametro"] = melhores[0]["parametros"] if melhores else None
        estado["resumo_rodada"] = {
            "rodada_atual": rodada_atual,
            "testados": testados,
            "validos": len(erros_rodada),
            "falhas": falhas,
            "melhor_erro_rodada": melhor_erro_rodada,
            "erro_medio_rodada": erro_medio_rodada,
            "pior_erro_rodada": pior_erro_rodada,
            "novo_melhor_geral": bool(novo_melhor_geral),
        }
        estado["erros_rodada_atual"] = erros_rodada
        estado["melhores"] = self._criar_melhores_para_dashboard(melhores)

        if melhor_atual is not None:
            estado["historico_melhor_erro"].append(
                {"rodada": rodada_atual, "erro": float(melhor_atual)}
            )

        return estado["resumo_rodada"], melhor_atual

    def salvar_resultados_txt(self, resultados_finais, modo, configuracao_saida):
        """Gera o relatório final em texto, se a saída estiver habilitada."""
        if not configuracao_saida.get("salvar_relatorio", True):
            return

        pasta_saida = Path(
            self.gerenciador_configuracao.resolver_caminho(
                configuracao_saida.get("pasta", "output")
            )
        )
        pasta_saida.mkdir(parents=True, exist_ok=True)

        arquivo_saida = Path(
            self.gerenciador_configuracao.resolver_caminho(
                configuracao_saida["arquivo_resultados"]
            )
        )
        arquivo_saida.parent.mkdir(parents=True, exist_ok=True)

        linhas = [f"Modo de execução: {modo}", ""]
        for tendencia, melhores in resultados_finais.items():
            linhas.append(f"Tendência: {tendencia}")
            for indice, item in enumerate(melhores, start=1):
                linhas.append(
                    f"  {indice:02d} | erro={item['erro']:.6f} | parametros={tuple(item['parametros'])}"
                )
            linhas.append("")

        arquivo_saida.write_text("\n".join(linhas), encoding="utf-8")

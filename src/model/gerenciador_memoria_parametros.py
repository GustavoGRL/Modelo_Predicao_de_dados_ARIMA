from datetime import datetime
import json
from pathlib import Path
from typing import Dict, List, Optional, Any


class GerenciadorMemoriaParametros:
    """Gerencia a memória de parâmetros entre execuções diárias."""

    def __init__(self, caminho_memoria: str, raiz_projeto: Path):
        self.caminho_memoria = Path(caminho_memoria)
        if not self.caminho_memoria.is_absolute():
            self.caminho_memoria = raiz_projeto / self.caminho_memoria
        self.raiz_projeto = raiz_projeto

    def carregar_memoria(self) -> Dict[str, Any]:
        """Carrega a memória de parâmetros do arquivo JSON, se existir."""
        if not self.caminho_memoria.exists():
            return self._criar_memoria_vazia()

        try:
            with self.caminho_memoria.open("r", encoding="utf-8") as arquivo:
                memoria = json.load(arquivo)
            return memoria
        except (json.JSONDecodeError, OSError) as erro:
            print(f"Erro ao carregar memória de parâmetros: {erro}")
            return self._criar_memoria_vazia()

    def salvar_memoria(self, memoria: Dict[str, Any]) -> None:
        """Salva a memória de parâmetros no arquivo JSON."""
        self.caminho_memoria.parent.mkdir(parents=True, exist_ok=True)
        with self.caminho_memoria.open("w", encoding="utf-8") as arquivo:
            json.dump(memoria, arquivo, ensure_ascii=False, indent=2)

    def obter_parametros_herdados(self, memoria: Dict[str, Any]) -> List[List[int]]:
        """Extrai os parâmetros herdados do dia anterior."""
        candidatos = memoria.get("candidatos_proximo_dia", [])
        parametros_herdados = []
        
        for candidato in candidatos:
            if "parametros" in candidato:
                params = candidato["parametros"]
                if isinstance(params, list) and len(params) == 3:
                    parametros_herdados.append([int(p) for p in params])
        
        return parametros_herdados

    def criar_destaques_dia(
        self, 
        resultados: List[Dict[str, Any]], 
        limite: int = 30
    ) -> List[Dict[str, Any]]:
        """Cria a lista de destaques do dia a partir dos resultados atuais."""
        if not resultados:
            return []

        # Ordenar por erro (métrica principal)
        resultados_ordenados = sorted(resultados, key=lambda x: x.get("erro", float("inf")))
        
        destaques = []
        for i, resultado in enumerate(resultados_ordenados[:limite], start=1):
            destaque = {
                "rank": i,
                "parametros": resultado.get("parametros", []),
                "erro": resultado.get("erro"),
                "mape": resultado.get("mape"),
                "smape": resultado.get("smape"),
                "origem": resultado.get("origem", "aleatorio")
            }
            destaques.append(destaque)
        
        return destaques

    def criar_consolidados(
        self,
        resultados_atuais: List[Dict[str, Any]],
        memoria_anterior: Dict[str, Any],
        limite: int = 30,
        metrica_principal: str = "smape"
    ) -> List[Dict[str, Any]]:
        """Cria a lista de resultados consolidados entre ontem e hoje."""
        candidatos_anteriores = memoria_anterior.get("candidatos_proximo_dia", [])
        if not candidatos_anteriores:
            return []

        # Mapear resultados atuais por parâmetros
        resultados_por_parametros = {}
        for resultado in resultados_atuais:
            params = tuple(resultado.get("parametros", []))
            if len(params) == 3:
                resultados_por_parametros[params] = resultado

        consolidados = []
        for candidato in candidatos_anteriores:
            params = tuple(candidato.get("parametros", []))
            if len(params) != 3:
                continue

            if params in resultados_por_parametros:
                resultado_atual = resultados_por_parametros[params]
                
                # Obter métricas anteriores
                smape_anterior = candidato.get("smape")
                mape_anterior = candidato.get("mape")
                erro_anterior = candidato.get("erro")
                rank_anterior = candidato.get("rank")
                
                # Obter métricas atuais
                smape_atual = resultado_atual.get("smape")
                mape_atual = resultado_atual.get("mape")
                erro_atual = resultado_atual.get("erro")
                rank_atual = resultado_atual.get("rank_consolidado", 0)
                
                # Calcular médias
                smape_medio = self._calcular_media(smape_anterior, smape_atual)
                mape_medio = self._calcular_media(mape_anterior, mape_atual)
                erro_medio = self._calcular_media(erro_anterior, erro_atual)
                
                consolidado = {
                    "rank": len(consolidados) + 1,
                    "parametros": list(params),
                    "smape_anterior": smape_anterior,
                    "smape_atual": smape_atual,
                    "smape_medio_2dias": smape_medio,
                    "mape_anterior": mape_anterior,
                    "mape_atual": mape_atual,
                    "mape_medio_2dias": mape_medio,
                    "erro_anterior": erro_anterior,
                    "erro_atual": erro_atual,
                    "erro_medio_2dias": erro_medio,
                    "rank_anterior": rank_anterior,
                    "rank_atual": rank_atual,
                    "origem": "herdado"
                }
                consolidados.append(consolidado)

        # Ordenar consolidados pela métrica principal
        consolidados_ordenados = sorted(
            consolidados,
            key=lambda x: self._obter_metrica_principal(x, metrica_principal)
        )
        
        # Reatribuir ranks
        for i, consolidado in enumerate(consolidados_ordenados[:limite], start=1):
            consolidado["rank"] = i
        
        return consolidados_ordenados[:limite]

    def criar_candidatos_proximo_dia(
        self,
        destaques_dia: List[Dict[str, Any]],
        consolidados_2dias: List[Dict[str, Any]],
        limite_total: int = 30,
        limite_consolidados: int = 15,
        limite_destaques: int = 15
    ) -> List[Dict[str, Any]]:
        """Cria a lista de candidatos para o próximo dia."""
        candidatos = []
        parametros_unicos = set()
        
        # Adicionar consolidados (prioridade)
        for consolidado in consolidados_2dias[:limite_consolidados]:
            params = tuple(consolidado.get("parametros", []))
            if params not in parametros_unicos and len(params) == 3:
                candidato = {
                    "parametros": list(params),
                    "erro": consolidado.get("erro_atual"),
                    "mape": consolidado.get("mape_atual"),
                    "smape": consolidado.get("smape_atual"),
                    "rank": consolidado.get("rank"),
                    "origem": "consolidado"
                }
                candidatos.append(candidato)
                parametros_unicos.add(params)
        
        # Adicionar destaques do dia
        for destaque in destaques_dia[:limite_destaques]:
            params = tuple(destaque.get("parametros", []))
            if params not in parametros_unicos and len(params) == 3:
                candidato = {
                    "parametros": list(params),
                    "erro": destaque.get("erro"),
                    "mape": destaque.get("mape"),
                    "smape": destaque.get("smape"),
                    "rank": destaque.get("rank"),
                    "origem": "destaque"
                }
                candidatos.append(candidato)
                parametros_unicos.add(params)
        
        return candidatos[:limite_total]

    def montar_memoria_final(
        self,
        simbolo: str,
        intervalo: str,
        janela_historica_dias: int,
        avaliacao_dias: int,
        destaques_dia: List[Dict[str, Any]],
        consolidados_2dias: List[Dict[str, Any]],
        candidatos_proximo_dia: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Monta a estrutura final da memória de parâmetros."""
        return {
            "data_execucao": datetime.now().strftime("%Y-%m-%d"),
            "simbolo": simbolo,
            "intervalo": intervalo,
            "janela_historica_dias": janela_historica_dias,
            "avaliacao_dias": avaliacao_dias,
            "destaques_dia": destaques_dia,
            "consolidados_2dias": consolidados_2dias,
            "candidatos_proximo_dia": candidatos_proximo_dia
        }

    def _criar_memoria_vazia(self) -> Dict[str, Any]:
        """Cria uma memória vazia para a primeira execução."""
        return {
            "data_execucao": datetime.now().strftime("%Y-%m-%d"),
            "simbolo": "",
            "intervalo": "",
            "janela_historica_dias": 0,
            "avaliacao_dias": 0,
            "destaques_dia": [],
            "consolidados_2dias": [],
            "candidatos_proximo_dia": []
        }

    @staticmethod
    def _calcular_media(valor1: Optional[float], valor2: Optional[float]) -> Optional[float]:
        """Calcula a média entre dois valores, tratando valores None."""
        if valor1 is None and valor2 is None:
            return None
        elif valor1 is None:
            return valor2
        elif valor2 is None:
            return valor1
        else:
            return (valor1 + valor2) / 2

    @staticmethod
    def _obter_metrica_principal(
        item: Dict[str, Any], 
        metrica_principal: str
    ) -> float:
        """Obtém a métrica principal de um item, com fallback."""
        if metrica_principal == "smape":
            valor_smape = item.get("smape_medio_2dias")
            if valor_smape is not None:
                return valor_smape
            # Se smape é None, tentar mape
            valor_mape = item.get("mape_medio_2dias")
            if valor_mape is not None:
                return valor_mape
        
        if metrica_principal == "mape":
            valor_mape = item.get("mape_medio_2dias")
            if valor_mape is not None:
                return valor_mape
        
        # Fallback para erro absoluto
        valor_erro = item.get("erro_medio_2dias")
        if valor_erro is not None:
            return valor_erro
        
        return float("inf")
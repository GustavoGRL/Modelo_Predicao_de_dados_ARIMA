from pathlib import Path

import yaml


class GerenciadorConfiguracao:
    """Carrega, mescla e valida a configuração da aplicação."""

    TIPOS_FONTE_VALIDOS = {"local", "binance"}
    CAMPOS_RAIZ_OBRIGATORIOS = ("fonte_dados", "treinamento", "modelo", "saida", "divisao")

    def __init__(self, caminho_configuracao):
        self.caminho_configuracao = Path(caminho_configuracao)
        self.raiz_projeto = self.caminho_configuracao.parent.parent

    def carregar_configuracao(self):
        configuracao_base = self._carregar_yaml(self.caminho_configuracao)

        self.validar_configuracao(configuracao_base)
        return configuracao_base

    def validar_configuracao(self, configuracao):
        self._validar_campos_raiz(configuracao)
        self._validar_bloco_treinamento(configuracao)
        self._validar_bloco_fonte_dados(configuracao)
        self._validar_bloco_divisao(configuracao)

    def resolver_caminho(self, caminho_relativo):
        return str((self.raiz_projeto / caminho_relativo).resolve())

    def _validar_campos_raiz(self, configuracao):
        for campo in self.CAMPOS_RAIZ_OBRIGATORIOS:
            if campo not in configuracao:
                raise ValueError(f"Campo obrigatório ausente no config: '{campo}'.")

    @staticmethod
    def _validar_bloco_treinamento(configuracao):
        bloco_treinamento = configuracao["treinamento"]
        n_execucoes = int(bloco_treinamento.get("n_execucoes", 1))
        execucoes_por_rodada = int(bloco_treinamento.get("execucoes_por_rodada", 1))
        top_k = int(bloco_treinamento.get("top_k", 1))

        if n_execucoes < 1:
            raise ValueError("treinamento.n_execucoes deve ser maior ou igual a 1.")
        if execucoes_por_rodada < 1:
            raise ValueError("treinamento.execucoes_por_rodada deve ser maior ou igual a 1.")
        if top_k < 1:
            raise ValueError("treinamento.top_k deve ser maior ou igual a 1.")

    def _validar_bloco_fonte_dados(self, configuracao):
        bloco_fonte_dados = configuracao["fonte_dados"]
        tipo_fonte = bloco_fonte_dados.get("tipo")
        if tipo_fonte not in self.TIPOS_FONTE_VALIDOS:
            raise ValueError(
                f"Campo inválido: fonte_dados.tipo = '{tipo_fonte}'. "
                "Valores aceitos: local, binance."
            )

        if tipo_fonte == "local":
            self._validar_fonte_local(configuracao)
        elif tipo_fonte == "binance":
            self._validar_fonte_binance(configuracao)

    @staticmethod
    def _validar_bloco_divisao(configuracao):
        """Valida a porcentagem de avaliação (o restante será usado para treino)."""
        if "divisao" not in configuracao:
            raise ValueError("Campo obrigatório ausente: 'divisao'.")

        bloco_divisao = configuracao["divisao"]
        
        # Verificar se o campo de porcentagem de avaliação existe
        if "porcentagem_avaliacao" not in bloco_divisao:
            raise ValueError("Campo obrigatório ausente: divisao.porcentagem_avaliacao.")
        
        # Validar valor da porcentagem de avaliação
        porcentagem_avaliacao = float(bloco_divisao["porcentagem_avaliacao"])
        
        if porcentagem_avaliacao <= 0 or porcentagem_avaliacao > 100:
            raise ValueError("divisao.porcentagem_avaliacao deve estar entre 0 e 100.")
        
        # Verificar se a porcentagem de avaliação não ultrapassa 100%
        if porcentagem_avaliacao > 100:
            raise ValueError(
                f"A porcentagem de avaliação ({porcentagem_avaliacao}%) não pode ultrapassar 100%."
            )

    @staticmethod
    def _validar_fonte_local(configuracao):
        if "dados_locais" not in configuracao:
            raise ValueError(
                "Campo obrigatório ausente: 'dados_locais' para fonte_dados.tipo = 'local'."
            )

        bloco_local = configuracao["dados_locais"]
        caminho_dados = bloco_local.get("caminho")
        if not caminho_dados:
            raise ValueError("Campo obrigatório ausente: dados_locais.caminho.")

        tipo_arquivo = str(bloco_local.get("tipo_arquivo", "")).lower()
        if tipo_arquivo != "csv":
            raise ValueError("dados_locais.tipo_arquivo deve ser 'csv'.")

    @staticmethod
    def _validar_fonte_binance(configuracao):
        if "dados_binance" not in configuracao:
            raise ValueError(
                "Campo obrigatório ausente: 'dados_binance' para fonte_dados.tipo = 'binance'."
            )

        bloco_binance = configuracao["dados_binance"]
        
        # Validar campos obrigatórios
        symbol = bloco_binance.get("symbol")
        if not symbol:
            raise ValueError("Campo obrigatório ausente: dados_binance.symbol.")
        
        interval = bloco_binance.get("interval")
        if not interval:
            raise ValueError("Campo obrigatório ausente: dados_binance.interval.")
        
        limit = bloco_binance.get("limit")
        if limit is None:
            raise ValueError("Campo obrigatório ausente: dados_binance.limit.")
        
        # Validar valores
        try:
            limit_int = int(limit)
            if limit_int <= 0:
                raise ValueError("dados_binance.limit deve ser maior que 0.")
        except (ValueError, TypeError):
            raise ValueError("dados_binance.limit deve ser um número inteiro.")
        
        # Validar intervalos comuns da Binance
        intervalos_validos = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"]
        if interval not in intervalos_validos:
            raise ValueError(
                f"Intervalo inválido: dados_binance.interval = '{interval}'. "
                f"Valores aceitos: {', '.join(intervalos_validos)}"
            )

    @staticmethod
    def _carregar_yaml(caminho_arquivo):

        # Carrega YAML
        with Path(caminho_arquivo).open("r", encoding="utf-8") as arquivo:
            configuracao = yaml.safe_load(arquivo)
        if not isinstance(configuracao, dict):
            raise ValueError(f"Arquivo de configuração inválido: {caminho_arquivo}")
        return configuracao

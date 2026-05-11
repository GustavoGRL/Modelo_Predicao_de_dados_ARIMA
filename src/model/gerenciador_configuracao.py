from pathlib import Path

import yaml


class GerenciadorConfiguracao:
    """Carrega, mescla e valida a configuração da aplicação."""

    TIPOS_FONTE_VALIDOS = {"local"}
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
                "Valor aceito: local."
            )

        self._validar_fonte_local(configuracao)

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
    def _carregar_yaml(caminho_arquivo):

        # Carrega YAML
        with Path(caminho_arquivo).open("r", encoding="utf-8") as arquivo:
            configuracao = yaml.safe_load(arquivo)
        if not isinstance(configuracao, dict):
            raise ValueError(f"Arquivo de configuração inválido: {caminho_arquivo}")
        return configuracao

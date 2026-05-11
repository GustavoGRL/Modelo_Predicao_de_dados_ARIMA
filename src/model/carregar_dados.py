from pathlib import Path

import pandas as pd


class CarregadorDados:
    @staticmethod
    def normalizar_nome_coluna(nome_coluna):
        nome_normalizado = str(nome_coluna).strip()
        if ":" in nome_normalizado:
            nome_normalizado = nome_normalizado.split(":", maxsplit=1)[0]
        return nome_normalizado.replace(" ", "_").replace("-", "_").lower()

    @classmethod
    def normalizar_nomes_colunas(cls, dados):
        dados.columns = [cls.normalizar_nome_coluna(coluna) for coluna in dados.columns]
        return dados

    @classmethod
    def carregar_dados_csv_temporais(
        cls,
        caminho_arquivo,
        coluna_tempo="time",
        delimitador=",",
        pular_linhas=0,
    ):
        caminho = Path(caminho_arquivo)
        if not caminho.exists():
            raise FileNotFoundError(f"Arquivo de dados não encontrado: {caminho}")


        dados = pd.read_csv(caminho, delimiter=delimitador, skiprows=pular_linhas)
        if len(dados.columns) < 2:
            raise ValueError("O arquivo CSV precisa ter pelo menos duas colunas.")

        mapeamento_colunas = {
            coluna: cls.normalizar_nome_coluna(coluna) for coluna in dados.columns
        }
        dados = dados.rename(columns=mapeamento_colunas)

        coluna_tempo_normalizada = cls.normalizar_nome_coluna(coluna_tempo)
        if coluna_tempo_normalizada not in dados.columns:
            raise ValueError(
                f"Coluna temporal '{coluna_tempo}' não encontrada no CSV. "
                f"Colunas encontradas: {list(dados.columns)}"
            )

        dados[coluna_tempo_normalizada] = pd.to_datetime(
            dados[coluna_tempo_normalizada],
            errors="coerce",
        )
        dados = (
            dados
            .dropna(subset=[coluna_tempo_normalizada])
            .set_index(coluna_tempo_normalizada)
            .sort_index()
        )

        colunas_valor = [coluna for coluna in dados.columns]
        if not colunas_valor:
            raise ValueError(
                "O CSV deve conter ao menos uma coluna de dados para predição além da coluna temporal."
            )

        if isinstance(dados.index, pd.DatetimeIndex) and len(dados.index) >= 3:
            frequencia = pd.infer_freq(dados.index)
            if frequencia:
                dados = dados.asfreq(frequencia)
        return dados

    @classmethod
    def carregar_dados_locais(cls, configuracao_dados_locais, raiz_projeto):
        tipo_arquivo = str(configuracao_dados_locais.get("tipo_arquivo", "")).lower()
        if tipo_arquivo != "csv":
            raise ValueError("A fonte local aceita somente arquivos .csv (dados_locais.tipo_arquivo=csv).")

        caminho_arquivo = Path(raiz_projeto) / configuracao_dados_locais["caminho"]
        return cls.carregar_dados_csv_temporais(
            caminho_arquivo=caminho_arquivo,
            coluna_tempo=configuracao_dados_locais.get("coluna_tempo", "time"),
            delimitador=configuracao_dados_locais.get("delimitador", ","),
            pular_linhas=configuracao_dados_locais.get("pular_linhas", 0),
        )

    @classmethod
    def aplicar_preprocessamento(cls, dados, configuracao_processamento):
        if configuracao_processamento.get("remover_duplicados", False):
            dados = dados[~dados.index.duplicated(keep="first")]

        estrategia_valores_faltantes = configuracao_processamento.get(
            "estrategia_valores_faltantes", "remove"
        )
        if estrategia_valores_faltantes == "remove":
            dados = dados.dropna()
        elif estrategia_valores_faltantes == "fill_zero":
            dados = dados.fillna(0)
        elif estrategia_valores_faltantes == "keep":
            pass
        else:
            raise ValueError(
                f"Estratégia inválida para estrategia_valores_faltantes: '{estrategia_valores_faltantes}'. "
                "Valores aceitos: remove, fill_zero, keep."
            )

        if configuracao_processamento.get("normalizar_nomes_colunas", True):
            dados = cls.normalizar_nomes_colunas(dados)
        return dados


# Alias de compatibilidade para integrações existentes
carregar_dados_trends = CarregadorDados.carregar_dados_csv_temporais
normalizar_colunas = CarregadorDados.normalizar_nomes_colunas
carregar_dados_local = CarregadorDados.carregar_dados_locais

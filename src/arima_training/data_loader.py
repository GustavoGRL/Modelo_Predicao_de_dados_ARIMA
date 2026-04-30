from pathlib import Path

import pandas as pd
import requests


def carregar_dados_trends(caminho_arquivo, delimiter=",", skiprows=1):
    caminho = Path(caminho_arquivo)
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo de dados não encontrado: {caminho}")

    df = pd.read_csv(caminho, delimiter=delimiter, skiprows=skiprows)
    if len(df.columns) < 2:
        raise ValueError("O arquivo CSV precisa ter pelo menos duas colunas.")

    df.columns = ["Semana", *[str(col) for col in df.columns[1:]]]
    df["Semana"] = pd.to_datetime(df["Semana"], errors="coerce")
    df = df.dropna(subset=["Semana"])
    df = df.set_index("Semana")
    return df


def normalizar_nome_coluna(name):
    value = str(name).strip()
    if ":" in value:
        value = value.split(":", maxsplit=1)[0]
    value = value.replace(" ", "_").replace("-", "_").lower()
    return value


def normalizar_colunas(df):
    normalized_cols = [normalizar_nome_coluna(col) for col in df.columns]
    df.columns = normalized_cols
    return df


def carregar_dados_local(local_data_cfg, project_root):
    caminho = Path(project_root) / local_data_cfg["path"]
    file_type = str(local_data_cfg.get("file_type", "csv")).lower()

    if file_type == "csv":
        return carregar_dados_trends(
            caminho_arquivo=caminho,
            delimiter=local_data_cfg.get("delimiter", ","),
            skiprows=local_data_cfg.get("skiprows", 1),
        )
    if file_type == "xlsx":
        df = pd.read_excel(caminho)
    elif file_type == "json":
        df = pd.read_json(caminho)
    else:
        raise ValueError(
            f"Formato local inválido: '{file_type}'. Valores aceitos: csv, xlsx, json."
        )

    if "Semana" not in df.columns:
        raise ValueError("Coluna 'Semana' obrigatória não encontrada no arquivo local.")
    df["Semana"] = pd.to_datetime(df["Semana"], errors="coerce")
    df = df.dropna(subset=["Semana"]).set_index("Semana")
    return df


def buscar_google_trends(
    palavras_chave,
    periodo="today 5-y",
    geo="BR",
    idioma="pt-BR",
    timezone=360,
    gprop="",
):
    try:
        from pytrends.request import TrendReq
    except ImportError as exc:
        raise ImportError(
            "Biblioteca 'pytrends' não encontrada. Instale com: pip install pytrends"
        ) from exc

    if isinstance(palavras_chave, str):
        palavras_chave = [palavras_chave]
    if not isinstance(palavras_chave, list) or not palavras_chave:
        raise ValueError("google_trends.keywords deve ser string ou lista não vazia.")
    if len(palavras_chave) > 5:
        raise ValueError("Google Trends permite no máximo 5 palavras-chave por consulta.")

    if any((not isinstance(k, str) or not k.strip()) for k in palavras_chave):
        raise ValueError("Todas as palavras-chave devem ser textos válidos.")

    pytrends = TrendReq(hl=idioma, tz=int(timezone))
    pytrends.build_payload(
        kw_list=palavras_chave,
        timeframe=periodo,
        geo=geo,
        gprop=gprop,
    )
    dados = pytrends.interest_over_time()
    if dados.empty:
        return None
    return dados.drop(columns=["isPartial"], errors="ignore")


def carregar_dados_google_trends(google_cfg):
    dados = buscar_google_trends(
        palavras_chave=google_cfg["keywords"],
        periodo=google_cfg.get("timeframe", "today 5-y"),
        geo=google_cfg.get("geo", "BR"),
        idioma=google_cfg.get("hl", "pt-BR"),
        timezone=google_cfg.get("tz", 360),
        gprop=google_cfg.get("gprop", ""),
    )
    if dados is None:
        raise ValueError("Nenhum dado encontrado no Google Trends para as palavras-chave.")
    return dados


def carregar_dados_api(api_cfg, api_token=None):
    method = str(api_cfg.get("method", "GET")).upper()
    if method not in {"GET", "POST"}:
        raise ValueError(
            f"Método HTTP inválido: '{method}'. Valores aceitos: GET, POST."
        )

    headers = {}
    if api_token:
        auth_header = api_cfg.get("auth_header_name", "Authorization")
        if api_cfg.get("auth_use_bearer", True):
            headers[auth_header] = f"Bearer {api_token}"
        else:
            headers[auth_header] = api_token

    response = requests.request(
        method=method,
        url=api_cfg["url"],
        timeout=int(api_cfg.get("timeout_seconds", 30)),
        headers=headers,
    )
    response.raise_for_status()

    response_format = str(api_cfg.get("response_format", "csv")).lower()
    if response_format == "csv":
        from io import StringIO

        df = pd.read_csv(StringIO(response.text), delimiter=api_cfg.get("delimiter", ","))
    elif response_format == "json":
        json_payload = response.json()
        if isinstance(json_payload, dict):
            rows = json_payload.get("data", json_payload)
            df = pd.DataFrame(rows)
        else:
            df = pd.DataFrame(json_payload)
    else:
        raise ValueError(
            f"Formato de resposta inválido: '{response_format}'. Valores aceitos: csv, json."
        )

    if "Semana" not in df.columns:
        raise ValueError("A resposta da API deve conter a coluna 'Semana'.")
    df["Semana"] = pd.to_datetime(df["Semana"], errors="coerce")
    df = df.dropna(subset=["Semana"]).set_index("Semana")
    return df


def aplicar_preprocessamento(df, processing_cfg):
    if processing_cfg.get("remove_duplicates", False):
        df = df[~df.index.duplicated(keep="first")]

    strategy = processing_cfg.get("missing_values_strategy", "remove")
    if strategy == "remove":
        df = df.dropna()
    elif strategy == "fill_zero":
        df = df.fillna(0)
    elif strategy == "keep":
        pass
    else:
        raise ValueError(
            f"Estratégia inválida para missing_values_strategy: '{strategy}'. "
            "Valores aceitos: remove, fill_zero, keep."
        )

    if processing_cfg.get("normalize_column_names", True):
        df = normalizar_colunas(df)

    return df

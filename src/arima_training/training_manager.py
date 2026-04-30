from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import os
from pathlib import Path

import matplotlib.pyplot as plt
import yaml

from .arima_model import executar_simulacao_uma_vez
from .data_loader import (
    aplicar_preprocessamento,
    carregar_dados_api,
    carregar_dados_google_trends,
    carregar_dados_local,
    normalizar_nome_coluna,
)


class TrainingManager:
    """Classe responsável por orquestrar o treinamento de trends com ARIMA."""

    def __init__(self, config_path, experiment_path=None):
        self.config_path = Path(config_path)
        self.experiment_path = Path(experiment_path) if experiment_path else None
        self.config = self._load_config_with_experiment()
        self.project_root = self.config_path.parent.parent
        self._validar_config()

    def _load_yaml(self, path):
        with Path(path).open("r", encoding="utf-8") as file:
            config = yaml.safe_load(file)
        if not isinstance(config, dict):
            raise ValueError(f"Arquivo de configuração inválido: {path}")
        return config

    def _merge_dict(self, base, override):
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_dict(base[key], value)
            else:
                base[key] = value
        return base

    def _load_config_with_experiment(self):
        base = self._load_yaml(self.config_path)
        if self.experiment_path:
            override = self._load_yaml(self.experiment_path)
            return self._merge_dict(base, override)
        return base

    def _validar_config(self):
        required_root = ["data_source", "training", "model", "output", "split"]
        for field in required_root:
            if field not in self.config:
                raise ValueError(f"Campo obrigatório ausente no config: '{field}'.")

        source_type = self.config["data_source"].get("type")
        if source_type not in {"local", "api", "google_trends"}:
            raise ValueError(
                f"Campo inválido: data_source.type = '{source_type}'. "
                "Valores aceitos: local, api, google_trends."
            )

        n_threads = int(self.config["training"].get("n_threads", 1))
        n_runs = int(self.config["training"].get("n_runs", 1))
        if n_threads < 1:
            raise ValueError("training.n_threads deve ser maior ou igual a 1.")
        if n_runs < 1:
            raise ValueError("training.n_runs deve ser maior ou igual a 1.")

        top_k = int(self.config["training"].get("top_k", 1))
        if top_k < 1:
            raise ValueError("training.top_k deve ser maior ou igual a 1.")

        if source_type == "local" and "local_data" not in self.config:
            raise ValueError("Campo obrigatório ausente: 'local_data' para data_source.type = 'local'.")
        if source_type == "api" and "api_data" not in self.config:
            raise ValueError("Campo obrigatório ausente: 'api_data' para data_source.type = 'api'.")
        if source_type == "google_trends" and "google_trends" not in self.config:
            raise ValueError(
                "Campo obrigatório ausente: 'google_trends' para data_source.type = 'google_trends'."
            )

    def _resolve_path(self, relative_path):
        return str((self.project_root / relative_path).resolve())

    def carregar_base(self):
        source_type = self.config["data_source"]["type"]
        if source_type == "local":
            df = carregar_dados_local(
                local_data_cfg=self.config["local_data"],
                project_root=self.project_root,
            )
        else:
            if source_type == "api":
                api_cfg = self.config["api_data"]
                token_env = api_cfg.get("token_env")
                token = os.getenv(token_env) if token_env else None
                df = carregar_dados_api(api_cfg=api_cfg, api_token=token)
            else:
                df = carregar_dados_google_trends(self.config["google_trends"])

        return aplicar_preprocessamento(df, self.config.get("processing", {}))

    def executar(self, modo="parallel"):
        dados = self.carregar_base()
        training_cfg = self.config["training"]
        trends = self.config.get("data", {}).get("trends")
        if not trends:
            trends = list(dados.columns)
        trends = [normalizar_nome_coluna(trend) for trend in trends]
        trends_invalidas = [trend for trend in trends if trend not in dados.columns]
        if trends_invalidas:
            raise ValueError(f"Trends não encontradas na base carregada: {trends_invalidas}")

        max_trends = int(training_cfg.get("max_trends_simultaneas", 1))
        resultados_finais = {}

        with ThreadPoolExecutor(max_workers=max_trends) as executor:
            futuros = {
                executor.submit(self._treinar_trend, trend, dados[trend], modo): trend
                for trend in trends
            }
            for futuro in as_completed(futuros):
                trend = futuros[futuro]
                resultados_finais[trend] = futuro.result()

        self._salvar_resultados_txt(resultados_finais, modo=modo)
        return resultados_finais

    def _split_series(self, serie):
        split_cfg = self.config["split"]
        treino = serie[serie.index <= split_cfg["train_end"]]
        avaliacao = serie[
            (serie.index >= split_cfg["eval_start"]) & (serie.index <= split_cfg["eval_end"])
        ]
        if treino.empty or avaliacao.empty:
            raise ValueError("Séries de treino/avaliação vazias. Verifique as datas no config.")
        return treino, avaliacao

    def _treinar_trend(self, trend_name, serie, modo):
        treino, avaliacao = self._split_series(serie)
        training_cfg = self.config["training"]
        model_cfg = dict(self.config["model"])
        model_cfg["random_seed"] = training_cfg.get("random_seed")

        if modo == "test":
            execucoes = 1
            execucoes_por_rodada = 1
            ordem_fixa = self.config["test"]["fixed_order"]
        elif modo == "individual":
            execucoes = int(training_cfg["n_runs"])
            execucoes_por_rodada = 1
            ordem_fixa = None
        else:
            execucoes = int(training_cfg["n_runs"])
            execucoes_por_rodada = int(training_cfg["runs_per_round"])
            ordem_fixa = None

        melhores = []
        concluido = 0
        total_rodadas = max(1, (execucoes + execucoes_por_rodada - 1) // execucoes_por_rodada)
        max_workers = int(training_cfg.get("n_threads", 1))

        for rodada in range(total_rodadas):
            qtd_execucoes = min(execucoes_por_rodada, execucoes - concluido)
            if qtd_execucoes <= 0:
                break

            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                futuros = []
                for idx in range(qtd_execucoes):
                    cfg_exec = dict(model_cfg)
                    base_seed = training_cfg.get("random_seed")
                    if base_seed is not None:
                        cfg_exec["random_seed"] = int(base_seed) + concluido + idx

                    futuros.append(
                        executor.submit(
                            executar_simulacao_uma_vez,
                            treino,
                            avaliacao,
                            cfg_exec,
                            ordem_fixa,
                        )
                    )

                for futuro in as_completed(futuros):
                    resultado = futuro.result()
                    melhores.append(resultado)

            melhores = sorted(melhores, key=lambda item: item["erro"])[: int(training_cfg["top_k"])]
            concluido += qtd_execucoes
            progresso = (concluido / execucoes) * 100
            print(f"[{trend_name}] Rodada {rodada + 1}/{total_rodadas} | Progresso: {progresso:.2f}%")

        if training_cfg.get("mostrar_graficos", True) and melhores:
            melhor = melhores[0]
            self._mostrar_grafico(treino, avaliacao, melhor["previsoes"], trend_name, melhor["erro"])

        return melhores

    def _mostrar_grafico(self, treino, avaliacao, previsoes, trend_name, erro):
        plt.figure(figsize=(10, 5))
        plt.plot(treino.index, treino.values, label="Dados de Treino", color="blue")
        plt.plot(avaliacao.index, avaliacao.values, label="Dados de Avaliação", color="green")
        plt.plot(avaliacao.index, previsoes, label="Previsão", color="red")
        plt.legend()
        plt.title(f"Trend: {trend_name} | Melhor erro: {erro:.6f}")
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.show()

    def _salvar_resultados_txt(self, resultados_finais, modo):
        output_cfg = self.config["output"]
        if not output_cfg.get("save_report", True):
            return

        output_dir = Path(self._resolve_path(output_cfg.get("path", "output")))
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = Path(self._resolve_path(output_cfg["resultados_txt"]))
        output_file.parent.mkdir(parents=True, exist_ok=True)

        linhas = [f"Modo de execução: {modo}", ""]
        for trend, melhores in resultados_finais.items():
            linhas.append(f"Trend: {trend}")
            for idx, item in enumerate(melhores, start=1):
                linhas.append(
                    f"  {idx:02d} | erro={item['erro']:.6f} | parametros={tuple(item['parametros'])}"
                )
            linhas.append("")

        output_file.write_text("\n".join(linhas), encoding="utf-8")

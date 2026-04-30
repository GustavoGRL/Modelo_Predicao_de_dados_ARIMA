import argparse
from pathlib import Path

from src.arima_training import TrainingManager


def main():
    parser = argparse.ArgumentParser(description="Inicia a pesquisa/treinamento ARIMA.")
    parser.add_argument(
        "--modo",
        choices=["parallel", "individual", "test"],
        default="parallel",
        help="Modo de execução do treinamento.",
    )
    parser.add_argument(
        "--config",
        default="config/config.yami",
        help="Caminho do arquivo principal de configuração.",
    )
    parser.add_argument(
        "--experiment",
        default=None,
        help="Caminho opcional para configuração de experimento (override).",
    )
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    experiment_path = Path(args.experiment).resolve() if args.experiment else None

    manager = TrainingManager(config_path=config_path, experiment_path=experiment_path)
    resultados = manager.executar(modo=args.modo)

    print("\nResultados por trend:")
    for trend, melhores in resultados.items():
        print(f"\nTrend: {trend}")
        for item in melhores:
            print(item)

    print("\nArquivo de saída salvo em output/resultados_treinamento.txt")


if __name__ == "__main__":
    main()

import argparse
import json
import subprocess
import sys
import time
import traceback
from pathlib import Path

import yaml

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from src.model.treino import GerenciadorTreinamento


def configurar_argumentos():
    """Configura os argumentos de linha de comando."""
    parser = argparse.ArgumentParser(
        description="Inicia o treinamento ARIMA com dashboard.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python scripts/iniciar_pesquisa.py
  python scripts/iniciar_pesquisa.py --config config/config.yami --modo treino
  python scripts/iniciar_pesquisa.py --sem-dashboard
        """,
    )
    
    parser.add_argument(
        "--config",
        type=str,
        default="config/config.yami",
        help="Caminho para o arquivo de configuração (padrão: config/config.yami)",
    )
    
    parser.add_argument(
        "--modo",
        type=str,
        choices=["treino", "teste"],
        default=None,
        help="Modo de execução: treino ou teste (sobrescreve config)",
    )
    
    parser.add_argument(
        "--sem-dashboard",
        action="store_true",
        help="Não iniciar o dashboard automaticamente",
    )
    
    return parser.parse_args()


def resolver_raiz_projeto():
    return RAIZ_PROJETO


def resolver_caminho_configuracao(caminho_config=None):
    """Resolve o caminho para o arquivo de configuração."""
    if caminho_config:
        caminho = Path(caminho_config)
        if caminho.is_absolute():
            return caminho.resolve()
        else:
            return (RAIZ_PROJETO / caminho).resolve()
    else:
        return (RAIZ_PROJETO / "config" / "config.yami").resolve()


def carregar_configuracao_execucao(caminho_configuracao):
    with Path(caminho_configuracao).open("r", encoding="utf-8") as arquivo:
        configuracao = yaml.safe_load(arquivo) or {}
    return configuracao


def salvar_estado_erro(raiz_projeto, configuracao, mensagem, detalhes=None):
    configuracao_dashboard = configuracao.get("dashboard") or configuracao.get("view", {})
    caminho_estado = Path(
        configuracao_dashboard.get("caminho_estado", "output/estado_treinamento.json")
    )
    pasta_saida = (
        caminho_estado.parent
        if caminho_estado.is_absolute()
        else (raiz_projeto / caminho_estado.parent).resolve()
    )
    pasta_saida.mkdir(parents=True, exist_ok=True)

    estado_erro = {
        "trend": "erro",
        "status": "erro",
        "modo": "-",
        "rodada_atual": 0,
        "total_rodadas": 0,
        "execucoes_concluidas": 0,
        "execucoes_total": 0,
        "progresso_percentual": 0.0,
        "melhor_erro": None,
        "melhor_parametro": None,
        "configuracao_execucao": {},
        "periodos": {},
        "treino": {"datas": [], "valores": []},
        "avaliacao_real": {"datas": [], "valores": []},
        "resumo_rodada": {},
        "melhores": [],
        "historico_melhor_erro": [],
        "erros_rodada_atual": [],
        "mensagem": mensagem,
        "logs": [mensagem] + ([detalhes] if detalhes else []),
    }

    arquivo_estado = (
        caminho_estado if caminho_estado.is_absolute() else (raiz_projeto / caminho_estado).resolve()
    )
    arquivo_estado.write_text(
        json.dumps(estado_erro, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def iniciar_visualizador(raiz_projeto, configuracao):
    configuracao_dashboard = configuracao.get("dashboard") or configuracao.get("view", {})
    porta_visualizador = int(configuracao_dashboard.get("porta", 8004))
    comando_visualizador = [
        sys.executable,
        "-m",
        "src.view.visualizador_dash",
    ]
    subprocess.Popen(
        comando_visualizador,
        cwd=str(raiz_projeto),
    )
    time.sleep(1.0)
    print(f"Dashboard disponível em: http://127.0.0.1:{porta_visualizador}")


def main():
    # Configurar argumentos
    args = configurar_argumentos()
    
    # Resolver caminhos
    raiz_projeto = resolver_raiz_projeto()
    caminho_configuracao = resolver_caminho_configuracao(args.config)
    
    if not caminho_configuracao.exists():
        print(f"Erro: Arquivo de configuração não encontrado: {caminho_configuracao}")
        sys.exit(1)
    
    # Carregar configuração
    configuracao = carregar_configuracao_execucao(caminho_configuracao)
    configuracao_execucao = configuracao.get("execucao", {})
    
    # Determinar modo de execução (argumento tem prioridade sobre config)
    if args.modo:
        modo_execucao = args.modo
    else:
        modo_execucao = str(configuracao_execucao.get("modo", "treino")).lower()
    
    # Determinar se deve iniciar dashboard
    if args.sem_dashboard:
        iniciar_dashboard = False
    else:
        iniciar_dashboard = bool(configuracao_execucao.get("iniciar_dashboard_automaticamente", True))

    if iniciar_dashboard:
        iniciar_visualizador(raiz_projeto=raiz_projeto, configuracao=configuracao)

    try:
        gerenciador_treinamento = GerenciadorTreinamento(
            caminho_configuracao=caminho_configuracao,
        )
        resultados = gerenciador_treinamento.executar(modo=modo_execucao)
    except Exception as erro:
        detalhes_erro = traceback.format_exc()
        salvar_estado_erro(
            raiz_projeto=raiz_projeto,
            configuracao=configuracao,
            mensagem=f"Falha ao iniciar ou executar o treinamento: {erro}",
            detalhes=detalhes_erro,
        )
        print(f"\nErro ao executar o treinamento: {erro}")
        raise SystemExit(1) from erro

    print("\nResultados por trend:")
    for tendencia, melhores in resultados.items():
        print(f"\nTendência: {tendencia}")
        for item in melhores:
            print(item)

    print("\nArquivo de saída salvo em output/resultados_treinamento.txt")


if __name__ == "__main__":
    main()

import json
import subprocess
import sys
import time
import traceback
import webbrowser
from pathlib import Path

import yaml

RAIZ_PROJETO = Path(__file__).resolve().parents[1]
if str(RAIZ_PROJETO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROJETO))

from src.model.treino import GerenciadorTreinamento


def resolver_raiz_projeto():
    return RAIZ_PROJETO


def resolver_caminho_configuracao():
    return (resolver_raiz_projeto() / "config" / "config.yami").resolve()


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
    webbrowser.open(f"http://127.0.0.1:{porta_visualizador}")


def main():
    raiz_projeto = resolver_raiz_projeto()
    caminho_configuracao = resolver_caminho_configuracao()
    configuracao = carregar_configuracao_execucao(caminho_configuracao)
    configuracao_execucao = configuracao.get("execucao", {})
    modo_execucao = str(configuracao_execucao.get("modo", "treino")).lower()
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

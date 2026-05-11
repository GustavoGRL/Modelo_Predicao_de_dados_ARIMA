from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from flask import Flask, Response, jsonify, request, send_file
from werkzeug.exceptions import HTTPException


# =====================================================================
# Constantes principais
# =====================================================================

RAIZ_PROJETO = Path(__file__).resolve().parents[2]

CAMINHOS_CONFIGURACAO_PADRAO = (
    RAIZ_PROJETO / "config" / "config.yaml",
    RAIZ_PROJETO / "config" / "config.yml",
)

PASTA_SAIDA_PADRAO = RAIZ_PROJETO / "output"

ARQUIVO_ESTADO_PADRAO = PASTA_SAIDA_PADRAO / "estado_treinamento.json"
ARQUIVO_HISTORICO_PADRAO = PASTA_SAIDA_PADRAO / "histórico_rodadas.csv"

# Mantive o nome igual ao seu código.
# Se o arquivo correto for "template_dashboard.html", altere aqui.
ARQUIVO_HTML_DASHBOARD = Path(__file__).with_name("teamplate_dashboard.html")
ARQUIVO_JS_DASHBOARD = Path(__file__).with_name("dashboard.js")

PORTA_PADRAO = 8004
HOST_PADRAO = "127.0.0.1"

CACHE_CONTROL_SEM_CACHE = "no-store, no-cache, must-revalidate, max-age=0"


# =====================================================================
# Configuração
# =====================================================================

@dataclass(frozen=True)
class ConfiguracaoDashboard:
    porta: int
    caminho_estado: Path
    caminho_historico: Path


def resolver_caminho_base(caminho: str | Path) -> Path:
    """Resolve caminho absoluto ou relativo à raiz do projeto."""
    caminho_path = Path(caminho)

    if caminho_path.is_absolute():
        return caminho_path

    return (RAIZ_PROJETO / caminho_path).resolve()


def carregar_yaml(caminho: Path) -> dict[str, Any]:
    """Carrega um arquivo YAML de forma segura."""
    with caminho.open("r", encoding="utf-8") as arquivo:
        dados = yaml.safe_load(arquivo) or {}

    if not isinstance(dados, dict):
        raise ValueError(
            f"Arquivo YAML inválido: {caminho}. "
            "O conteúdo principal precisa ser um dicionário."
        )

    return dados


def carregar_bloco_dashboard() -> dict[str, Any]:
    """
    Lê o bloco 'dashboard' do arquivo de configuração.

    Se não existir config.yaml/config.yml, retorna configuração vazia
    e o dashboard usa os caminhos padrão.
    """
    for caminho_configuracao in CAMINHOS_CONFIGURACAO_PADRAO:
        if not caminho_configuracao.is_file():
            continue

        dados = carregar_yaml(caminho_configuracao)
        bloco_dashboard = dados.get("dashboard", {})

        if bloco_dashboard is None:
            return {}

        if not isinstance(bloco_dashboard, dict):
            raise ValueError(
                f"O bloco 'dashboard' em {caminho_configuracao} precisa ser um dicionário."
            )

        return bloco_dashboard

    return {}


def obter_configuracao_dashboard() -> ConfiguracaoDashboard:
    """Monta a configuração final usada pelo servidor Flask."""
    try:
        configuracao = carregar_bloco_dashboard()
    except Exception:
        # Se o YAML estiver ruim, o servidor ainda sobe com os padrões.
        configuracao = {}

    porta = obter_inteiro(
        configuracao.get("porta"),
        padrao=PORTA_PADRAO,
    )

    caminho_estado = resolver_caminho_base(
        configuracao.get("caminho_estado", ARQUIVO_ESTADO_PADRAO)
    )

    caminho_historico = resolver_caminho_base(
        configuracao.get("caminho_historico", ARQUIVO_HISTORICO_PADRAO)
    )

    return ConfiguracaoDashboard(
        porta=porta,
        caminho_estado=caminho_estado,
        caminho_historico=caminho_historico,
    )


# =====================================================================
# Utilidades
# =====================================================================

def obter_inteiro(valor: Any, padrao: int) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return padrao


def obter_float(valor: Any) -> float | None:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(numero):
        return None

    return numero


def resposta_sem_cache(resposta: Response) -> Response:
    resposta.headers["Cache-Control"] = CACHE_CONTROL_SEM_CACHE
    return resposta


def resposta_texto(mensagem: str, status: int = 200) -> Response:
    resposta = Response(
        mensagem,
        status=status,
        mimetype="text/plain; charset=utf-8",
    )
    return resposta_sem_cache(resposta)


def resposta_json(dados: dict[str, Any], status: int = 200) -> Response:
    resposta = jsonify(normalizar_para_json(dados))
    resposta.status_code = status
    return resposta_sem_cache(resposta)


def normalizar_para_json(dado: Any) -> Any:
    """
    Garante que o payload seja seguro para JSON.

    Remove valores problemáticos como NaN, inf e -inf.
    """
    if isinstance(dado, dict):
        return {
            str(chave): normalizar_para_json(valor)
            for chave, valor in dado.items()
        }

    if isinstance(dado, list):
        return [normalizar_para_json(item) for item in dado]

    if isinstance(dado, tuple):
        return [normalizar_para_json(item) for item in dado]

    if isinstance(dado, float):
        return dado if math.isfinite(dado) else None

    if isinstance(dado, Path):
        return str(dado)

    return dado


def enviar_arquivo(caminho: Path, mimetype: str | None = None) -> Response:
    """Envia arquivo estático com validação simples e mensagens claras."""
    if not caminho.exists():
        return resposta_texto(
            f"Arquivo não encontrado: {caminho}",
            status=404,
        )

    if not caminho.is_file():
        return resposta_texto(
            f"O caminho existe, mas não é um arquivo: {caminho}",
            status=500,
        )

    resposta = send_file(caminho, mimetype=mimetype)
    return resposta_sem_cache(resposta)


# =====================================================================
# Estado do treinamento
# =====================================================================

def criar_estado_aguardando(caminho_estado: Path, caminho_historico: Path) -> dict[str, Any]:
    return {
        "status": "aguardando",
        "mensagem": "Aguardando arquivo de estado de treinamento...",
        "_arquivo_estado_esperado": str(caminho_estado),
        "_arquivo_historico_esperado": str(caminho_historico),
        "_pasta_estado": str(caminho_estado.parent),
    }


def criar_estado_erro(mensagem: str, caminho_estado: Path | None = None) -> dict[str, Any]:
    estado = {
        "status": "erro",
        "mensagem": mensagem,
    }

    if caminho_estado is not None:
        estado["_arquivo_estado"] = str(caminho_estado)

    return estado


def ler_estado_json(caminho_estado: Path) -> dict[str, Any]:
    """Lê e valida o estado salvo pelo treinamento."""
    conteudo = caminho_estado.read_text(encoding="utf-8")
    estado = json.loads(conteudo)

    if not isinstance(estado, dict):
        raise ValueError("O arquivo de estado precisa ter um objeto JSON na raiz.")

    return estado


def carregar_historico_csv(caminho_historico: Path) -> list[dict[str, int | float]]:
    """Lê o histórico CSV usado no gráfico de evolução."""
    if not caminho_historico.is_file():
        return []

    historico: list[dict[str, int | float]] = []

    with caminho_historico.open("r", encoding="utf-8", newline="") as arquivo:
        leitor = csv.DictReader(arquivo)

        for linha in leitor:
            try:
                rodada = int(linha["rodada"])
            except (KeyError, TypeError, ValueError):
                continue

            erro = obter_float(linha.get("melhor_erro_geral"))
            if erro is None:
                continue

            historico.append({
                "rodada": rodada,
                "erro": erro,
            })

    return historico


def normalizar_historico_melhor_erro(
    historico_estado: Any,
    caminho_historico: Path,
) -> list[dict[str, int | float]]:
    """
    Usa primeiro o histórico que já veio no JSON.
    Se não houver histórico válido no JSON, tenta ler o CSV.
    """
    if isinstance(historico_estado, list):
        historico_normalizado: list[dict[str, int | float]] = []

        for item in historico_estado:
            if not isinstance(item, dict):
                continue

            try:
                rodada = int(item["rodada"])
            except (KeyError, TypeError, ValueError):
                continue

            erro = obter_float(item.get("erro"))
            if erro is None:
                continue

            historico_normalizado.append({
                "rodada": rodada,
                "erro": erro,
            })

        if historico_normalizado:
            return historico_normalizado

    try:
        return carregar_historico_csv(caminho_historico)
    except (OSError, UnicodeDecodeError):
        return []


def carregar_estado_dashboard(
    caminho_estado: Path,
    caminho_historico: Path,
) -> dict[str, Any]:
    """
    Carrega o estado que será consumido pelo dashboard.
    Esta função nunca deve quebrar a API: em caso de erro, retorna status='erro'.
    """
    if not caminho_estado.is_file():
        return criar_estado_aguardando(caminho_estado, caminho_historico)

    try:
        estado = ler_estado_json(caminho_estado)
    except json.JSONDecodeError as erro:
        return criar_estado_erro(
            f"Arquivo de estado inválido. JSON malformado: {erro}",
            caminho_estado,
        )
    except OSError as erro:
        return criar_estado_erro(
            f"Não foi possível ler o arquivo de estado: {erro}",
            caminho_estado,
        )
    except Exception as erro:
        return criar_estado_erro(
            f"Falha ao processar o arquivo de estado: {type(erro).__name__}: {erro}",
            caminho_estado,
        )

    estado["historico_melhor_erro"] = normalizar_historico_melhor_erro(
        estado.get("historico_melhor_erro"),
        caminho_historico,
    )

    estado["_arquivo_estado"] = str(caminho_estado)
    estado["_arquivo_historico"] = str(caminho_historico)
    estado["_pasta_estado"] = str(caminho_estado.parent)

    return estado


# =====================================================================
# Aplicação Flask
# =====================================================================

def criar_app(configuracao: ConfiguracaoDashboard | None = None) -> Flask:
    configuracao = configuracao or obter_configuracao_dashboard()

    app = Flask(__name__)

    app.config["CAMINHO_ESTADO"] = configuracao.caminho_estado
    app.config["CAMINHO_HISTORICO"] = configuracao.caminho_historico

    @app.get("/")
    def pagina_principal() -> Response:
        return enviar_arquivo(
            ARQUIVO_HTML_DASHBOARD,
            mimetype="text/html",
        )

    @app.get("/dashboard.js")
    def javascript_dashboard() -> Response:
        return enviar_arquivo(
            ARQUIVO_JS_DASHBOARD,
            mimetype="application/javascript",
        )

    @app.get("/api/estado")
    def api_estado() -> Response:
        estado = carregar_estado_dashboard(
            caminho_estado=app.config["CAMINHO_ESTADO"],
            caminho_historico=app.config["CAMINHO_HISTORICO"],
        )
        return resposta_json(estado)

    @app.get("/api/health")
    def api_health() -> Response:
        return resposta_json({
            "status": "ok",
            "html": str(ARQUIVO_HTML_DASHBOARD),
            "html_existe": ARQUIVO_HTML_DASHBOARD.is_file(),
            "javascript": str(ARQUIVO_JS_DASHBOARD),
            "javascript_existe": ARQUIVO_JS_DASHBOARD.is_file(),
            "estado": str(app.config["CAMINHO_ESTADO"]),
            "estado_existe": Path(app.config["CAMINHO_ESTADO"]).is_file(),
            "historico": str(app.config["CAMINHO_HISTORICO"]),
            "historico_existe": Path(app.config["CAMINHO_HISTORICO"]).is_file(),
        })

    @app.errorhandler(Exception)
    def tratar_erro_global(erro: Exception) -> Response:
        """
        Evita transformar 404 em 500.

        Se o erro for HTTPException, preserva o status original.
        Se for erro inesperado, retorna 500.
        """
        if isinstance(erro, HTTPException):
            status_code = erro.code or 500
            mensagem = erro.description
        else:
            status_code = 500
            mensagem = f"{type(erro).__name__}: {erro}"

        if request.path.startswith("/api/"):
            return resposta_json(
                criar_estado_erro(f"Erro da aplicação: {mensagem}"),
                status=status_code,
            )

        return resposta_texto(
            f"Erro da aplicação: {mensagem}",
            status=status_code,
        )

    return app


def main() -> None:
    configuracao = obter_configuracao_dashboard()
    app = criar_app(configuracao)

    app.run(
        host=HOST_PADRAO,
        port=configuracao.porta,
        debug=False,
    )


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Script para executar o treinamento ARIMA uma vez por dia durante 7 dias.
Implementa a demonstração pública com memória de parâmetros contínua.
"""

import argparse
import json
import subprocess
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path


def configurar_argumentos():
    """Configura os argumentos de linha de comando."""
    parser = argparse.ArgumentParser(
        description="Executa o treinamento ARIMA uma vez por dia durante N dias.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python scripts/executar_demo_7_dias.py --config config/config.yami --dias 7 --intervalo-horas 24
  python scripts/executar_demo_7_dias.py --config config/config.yami --dias 3 --intervalo-horas 12 --sem-espera-inicial
  python scripts/executar_demo_7_dias.py --config config/config.yami --modo treino --sem-dashboard
        """,
    )
    
    parser.add_argument(
        "--config",
        type=str,
        default="config/config.yami",
        help="Caminho para o arquivo de configuração (padrão: config/config.yami)",
    )
    
    parser.add_argument(
        "--dias",
        type=int,
        default=7,
        help="Número total de dias para executar (padrão: 7)",
    )
    
    parser.add_argument(
        "--intervalo-horas",
        type=int,
        default=24,
        help="Intervalo entre execuções em horas (padrão: 24)",
    )
    
    parser.add_argument(
        "--sem-espera-inicial",
        action="store_true",
        help="Executar imediatamente o primeiro ciclo sem esperar",
    )
    
    parser.add_argument(
        "--modo",
        type=str,
        choices=["treino", "teste"],
        default="treino",
        help="Modo de execução: treino ou teste (padrão: treino)",
    )
    
    parser.add_argument(
        "--sem-dashboard",
        action="store_true",
        help="Não iniciar o dashboard automaticamente",
    )
    
    return parser.parse_args()


def configurar_logger(caminho_log):
    """Configura o logger para registrar execuções."""
    caminho_log.parent.mkdir(parents=True, exist_ok=True)
    
    def registrar_log(mensagem, nivel="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        linha_log = f"[{timestamp}] [{nivel}] {mensagem}"
        
        with caminho_log.open("a", encoding="utf-8") as arquivo_log:
            arquivo_log.write(linha_log + "\n")
        
        print(linha_log)
    
    return registrar_log


def executar_treinamento(config_path, modo, iniciar_dashboard):
    """Executa um ciclo de treinamento usando o script existente."""
    comando = [
        sys.executable,
        "scripts/iniciar_pesquisa.py",
        "--config", config_path,
        "--modo", modo,
    ]
    
    if not iniciar_dashboard:
        comando.append("--sem-dashboard")
    
    try:
        resultado = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            check=True,
        )
        return True, resultado.stdout, resultado.stderr
    except subprocess.CalledProcessError as erro:
        return False, erro.stdout, erro.stderr


def verificar_arquivos_saida(raiz_projeto, dia_atual, registrar_log):
    """Verifica se os arquivos de saída foram gerados corretamente."""
    caminho_estado = raiz_projeto / "output" / "estado_treinamento.json"
    caminho_memoria = raiz_projeto / "output" / "memoria_parametros.json"
    
    arquivos_gerados = []
    
    if caminho_estado.exists():
        try:
            with caminho_estado.open("r", encoding="utf-8") as arquivo:
                estado = json.load(arquivo)
                arquivos_gerados.append(f"estado_treinamento.json ({len(estado.get('melhores', []))} melhores)")
        except Exception as erro:
            registrar_log(f"Erro ao ler estado: {erro}", "WARNING")
    
    if caminho_memoria.exists():
        try:
            with caminho_memoria.open("r", encoding="utf-8") as arquivo:
                memoria = json.load(arquivo)
                arquivos_gerados.append(f"memoria_parametros.json ({len(memoria.get('candidatos_proximo_dia', []))} candidatos)")
        except Exception as erro:
            registrar_log(f"Erro ao ler memória: {erro}", "WARNING")
    
    if arquivos_gerados:
        registrar_log(f"Dia {dia_atual}: Arquivos gerados - {', '.join(arquivos_gerados)}")
    else:
        registrar_log(f"Dia {dia_atual}: Nenhum arquivo de saída gerado", "WARNING")
    
    return len(arquivos_gerados) > 0


def main():
    """Função principal do script de demonstração de 7 dias."""
    args = configurar_argumentos()
    
    # Resolver caminhos
    raiz_projeto = Path(__file__).resolve().parents[1]
    config_path = (raiz_projeto / args.config).resolve()
    
    if not config_path.exists():
        print(f"Erro: Arquivo de configuração não encontrado: {config_path}")
        sys.exit(1)
    
    # Configurar logger
    caminho_log = raiz_projeto / "output" / "demo_7_dias.log"
    registrar_log = configurar_logger(caminho_log)
    
    # Registrar início da demonstração
    registrar_log("=" * 60)
    registrar_log(f"Iniciando demonstração de {args.dias} dias")
    registrar_log(f"Configuração: {config_path}")
    registrar_log(f"Modo: {args.modo}")
    registrar_log(f"Intervalo: {args.intervalo_horas} horas")
    registrar_log(f"Espera inicial: {'Não' if args.sem_espera_inicial else 'Sim'}")
    registrar_log(f"Dashboard: {'Não' if args.sem_dashboard else 'Sim'}")
    registrar_log("=" * 60)
    
    # Verificar se memória de parâmetros está habilitada
    try:
        import yaml
        with config_path.open("r", encoding="utf-8") as arquivo:
            configuracao = yaml.safe_load(arquivo) or {}
        
        memoria_habilitada = configuracao.get("memoria_parametros", {}).get("habilitada", False)
        if not memoria_habilitada:
            registrar_log("AVISO: Memória de parâmetros não está habilitada na configuração", "WARNING")
            registrar_log("A demonstração funcionará, mas sem continuidade entre dias", "WARNING")
    except Exception as erro:
        registrar_log(f"Erro ao verificar configuração: {erro}", "WARNING")
        memoria_habilitada = False
    
    # Executar ciclos
    for dia in range(1, args.dias + 1):
        registrar_log(f"\n--- Dia {dia}/{args.dias} ---")
        registrar_log(f"Iniciando execução às {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Executar treinamento
        sucesso, stdout, stderr = executar_treinamento(
            str(config_path),
            args.modo,
            not args.sem_dashboard,
        )
        
        if sucesso:
            registrar_log(f"Dia {dia}: Treinamento concluído com sucesso")
            
            # Verificar arquivos gerados
            arquivos_ok = verificar_arquivos_saida(raiz_projeto, dia, registrar_log)
            
            if not arquivos_ok:
                registrar_log(f"Dia {dia}: AVISO - Arquivos de saída podem não ter sido gerados corretamente", "WARNING")
        else:
            registrar_log(f"Dia {dia}: ERRO no treinamento", "ERROR")
            registrar_log(f"Stdout: {stdout[:500]}", "ERROR")
            registrar_log(f"Stderr: {stderr[:500]}", "ERROR")
        
        # Aguardar próximo ciclo (exceto após o último dia)
        if dia < args.dias:
            if dia == 1 and args.sem_espera_inicial:
                registrar_log("Pulando espera inicial conforme solicitado")
            else:
                proxima_execucao = datetime.now() + timedelta(hours=args.intervalo_horas)
                registrar_log(f"Aguardando {args.intervalo_horas} horas até {proxima_execucao.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Aguardar intervalo
                time.sleep(args.intervalo_horas * 3600)
    
    # Registrar conclusão
    registrar_log("\n" + "=" * 60)
    registrar_log(f"Demonstração de {args.dias} dias concluída com sucesso")
    registrar_log(f"Logs salvos em: {caminho_log}")
    registrar_log("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nDemonstração interrompida pelo usuário")
        sys.exit(0)
    except Exception as erro:
        print(f"Erro fatal na demonstração: {erro}")
        traceback.print_exc()
        sys.exit(1)
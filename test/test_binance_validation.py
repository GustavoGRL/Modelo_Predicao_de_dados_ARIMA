#!/usr/bin/env python3
"""Teste de validação da configuração da Binance."""

import sys
sys.path.insert(0, '..')

import yaml
from pathlib import Path

def test_binance_config():
    """Testa a validação de uma configuração com fonte Binance."""
    print("Testando validação da configuração da Binance...")
    print("-" * 50)
    
    # Configuração de teste com fonte Binance
    config = {
        'projeto': {
            'nome': 'test_binance_validation',
            'descricao': 'Teste de validação da Binance',
            'versao': '2.0.0'
        },
        'execucao': {
            'modo': 'treino',
            'iniciar_dashboard_automaticamente': False
        },
        'dashboard': {
            'porta': 8004,
            'caminho_estado': 'output/test_estado.json',
            'caminho_historico': 'output/test_historico.csv'
        },
        'fonte_dados': {
            'tipo': 'binance'
        },
        'dados_binance': {
            'symbol': 'BTCUSDT',
            'interval': '1h',
            'limit': 100,
            'timeout': 10
        },
        'processamento': {
            'remover_duplicados': True,
            'estrategia_valores_faltantes': 'remove',
            'normalizar_nomes_colunas': True
        },
        'dados': {
            'tendencias': []
        },
        'divisao': {
            'porcentagem_avaliacao': 30
        },
        'treinamento': {
            'n_execucoes': 10,
            'execucoes_por_rodada': 2,
            'top_k': 5,
            'mostrar_graficos': False,
            'semente_aleatoria': 42
        },
        'modelo': {
            'tipo': 'arima',
            'intervalo_p': [0, 10],
            'intervalo_d': [0, 2],
            'intervalo_q': [0, 10],
            'max_tentativas': 20
        },
        'teste': {
            'ordem_fixa': [5, 1, 5]
        },
        'saida': {
            'pasta': 'output',
            'arquivo_resultados': 'output/test_resultados.txt',
            'salvar_relatorio': True
        }
    }
    
    # Salvar configuração de teste
    test_config_path = Path('config/test_binance_validation.yaml')
    with test_config_path.open('w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    
    print(f"✓ Configuração de teste criada: {test_config_path}")
    
    # Validar configuração
    from src.model.gerenciador_configuracao import GerenciadorConfiguracao
    
    try:
        gerenciador = GerenciadorConfiguracao(str(test_config_path))
        validated_config = gerenciador.carregar_configuracao()
        
        print("✓ Configuração validada com sucesso")
        print(f"  - Tipo de fonte: {validated_config['fonte_dados']['tipo']}")
        print(f"  - Symbol: {validated_config['dados_binance']['symbol']}")
        print(f"  - Interval: {validated_config['dados_binance']['interval']}")
        print(f"  - Limit: {validated_config['dados_binance']['limit']}")
        print(f"  - Porcentagem de avaliação: {validated_config['divisao']['porcentagem_avaliacao']}%")
        
        # Verificar se a porcentagem de treino não está mais presente
        if 'porcentagem_treino' in validated_config.get('divisao', {}):
            print("✗ 'porcentagem_treino' ainda presente na configuração validada")
            return False
        
        print("✓ 'porcentagem_treino' corretamente removido")
        
        # Limpar arquivo de teste
        test_config_path.unlink()
        print("✓ Arquivo de teste removido")
        
        print("\n" + "=" * 50)
        print("✅ VALIDAÇÃO DA CONFIGURAÇÃO DA BINANCE BEM-SUCEDIDA!")
        return True
        
    except Exception as e:
        print(f"✗ Erro na validação: {e}")
        import traceback
        traceback.print_exc()
        
        # Tentar remover o arquivo de teste mesmo em caso de erro
        try:
            test_config_path.unlink()
        except:
            pass
        
        return False

def main():
    """Executa o teste de validação."""
    print("=" * 60)
    print("Teste de Validação da Configuração da Binance")
    print("=" * 60)
    
    result = test_binance_config()
    
    if result:
        print("\n🎉 A configuração da Binance foi validada com sucesso!")
        print("O sistema está pronto para usar dados da API da Binance.")
        return 0
    else:
        print("\n✗ A validação da configuração da Binance falhou.")
        print("Verifique os erros acima.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
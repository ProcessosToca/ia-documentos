# tests/test_openai_connection.py
import os
import sys
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

# Adicionar o diretório raiz ao path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Carregar variáveis de ambiente
load_dotenv()

def test_openai_api_key():
    """Testa se a API Key da OpenAI está configurada e válida"""
    print("🔑 TESTE 1: Verificando API Key da OpenAI")
    print("-" * 50)
    
    api_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        print("❌ ERRO: OPENAI_API_KEY não encontrada no arquivo .env")
        return False
    
    print(f"✅ API Key encontrada: {api_key[:10]}...{api_key[-4:]}")
    
    # Testar se a API Key é válida
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(
            'https://api.openai.com/v1/models',
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            models = response.json()
            print(f"✅ API Key válida! Modelos disponíveis: {len(models.get('data', []))}")
            return True
        elif response.status_code == 401:
            print("❌ ERRO: API Key inválida ou expirada")
            return False
        else:
            print(f"❌ ERRO: Status {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ ERRO: Timeout na conexão com OpenAI")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ ERRO: Falha na conexão com OpenAI")
        return False
    except Exception as e:
        print(f"❌ ERRO: {e}")
        return False

def test_openai_client():
    """Testa o cliente OpenAI do projeto"""
    print("\n🤖 TESTE 2: Testando Cliente OpenAI do Projeto")
    print("-" * 50)
    
    try:
        from src.services.openai_service import OpenAIService
        
        # Criar instância do serviço
        openai_service = OpenAIService()
        print("✅ OpenAIService criado com sucesso")
        
        # Testar interpretação simples
        print("�� Testando interpretação de mensagem...")
        resultado = openai_service.interpretar_mensagem("Bom dia")
        
        if resultado:
            print(f"✅ Interpretação bem-sucedida: {resultado.get('mensagem_resposta', 'N/A')[:50]}...")
            return True
        else:
            print("❌ Falha na interpretação")
            return False
            
    except Exception as e:
        print(f"❌ ERRO no teste do cliente: {e}")
        return False

def test_network_connectivity():
    """Testa conectividade de rede"""
    print("\n🌐 TESTE 3: Verificando Conectividade de Rede")
    print("-" * 50)
    
    # Testar conectividade básica
    try:
        response = requests.get('https://api.openai.com', timeout=10)
        print(f"✅ Conectividade básica: Status {response.status_code}")
    except Exception as e:
        print(f"❌ Falha na conectividade básica: {e}")
        return False
    
    # Testar DNS
    try:
        import socket
        ip = socket.gethostbyname('api.openai.com')
        print(f"✅ DNS funcionando: api.openai.com -> {ip}")
    except Exception as e:
        print(f"❌ Falha no DNS: {e}")
        return False
    
    # Testar porta HTTPS
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex(('api.openai.com', 443))
        sock.close()
        
        if result == 0:
            print("✅ Porta 443 (HTTPS) acessível")
        else:
            print(f"❌ Porta 443 não acessível: {result}")
            return False
    except Exception as e:
        print(f"❌ Falha no teste de porta: {e}")
        return False
    
    return True

def test_environment_variables():
    """Testa variáveis de ambiente"""
    print("\n⚙️ TESTE 4: Verificando Variáveis de Ambiente")
    print("-" * 50)
    
    variaveis = [
        'OPENAI_API_KEY',
        'W_API_HOST',
        'W_API_INSTANCE_ID',
        'W_API_TOKEN',
        'SUPABASE_URL',
        'SUPABASE_KEY'
    ]
    
    todas_ok = True
    
    for var in variaveis:
        valor = os.getenv(var)
        if valor:
            print(f"✅ {var}: {valor[:10]}..." if len(valor) > 10 else f"✅ {var}: {valor}")
        else:
            print(f"❌ {var}: NÃO CONFIGURADA")
            todas_ok = False
    
    return todas_ok

def test_simple_openai_request():
    """Testa uma requisição simples para OpenAI"""
    print("\n📡 TESTE 5: Requisição Simples para OpenAI")
    print("-" * 50)
    
    api_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        print("❌ API Key não disponível")
        return False
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    data = {
        'model': 'gpt-4o-mini',
        'messages': [
            {'role': 'user', 'content': 'Diga apenas "Olá, teste funcionando!"'}
        ],
        'max_tokens': 50
    }
    
    try:
        print("📤 Enviando requisição de teste...")
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers=headers,
            json=data,
            timeout=30
        )
        
        print(f"📊 Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            print(f"✅ Resposta recebida: {content}")
            return True
        else:
            print(f"❌ Erro: {response.status_code}")
            print(f"📄 Resposta: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Timeout na requisição")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ Erro de conexão")
        return False
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def main():
    """Executa todos os testes"""
    print("🔍 DIAGNÓSTICO COMPLETO - CONEXÃO OPENAI")
    print("=" * 60)
    print(f"🕐 Início: {datetime.now().strftime('%H:%M:%S')}")
    print()
    
    resultados = {}
    
    # Executar testes
    resultados['api_key'] = test_openai_api_key()
    resultados['network'] = test_network_connectivity()
    resultados['env_vars'] = test_environment_variables()
    resultados['simple_request'] = test_simple_openai_request()
    resultados['client'] = test_openai_client()
    
    # Resumo final
    print("\n" + "=" * 60)
    print("📊 RESUMO DOS TESTES")
    print("=" * 60)
    
    for teste, resultado in resultados.items():
        status = "✅ PASSOU" if resultado else "❌ FALHOU"
        print(f"{teste.upper()}: {status}")
    
    sucessos = sum(resultados.values())
    total = len(resultados)
    
    print(f"\n�� RESULTADO: {sucessos}/{total} testes passaram")
    
    if sucessos == total:
        print("🎉 TODOS OS TESTES PASSARAM! O problema pode ser intermitente.")
    elif sucessos >= 3:
        print("⚠️ MAIORIA DOS TESTES PASSOU. Verificar configurações específicas.")
    else:
        print("❌ MUITOS TESTES FALHARAM. Problema de configuração ou conectividade.")
    
    print(f"\n�� Fim: {datetime.now().strftime('%H:%M:%S')}")

if __name__ == "__main__":
    main()
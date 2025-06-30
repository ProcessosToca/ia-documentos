import os
import requests
import json
from datetime import datetime

# Configurações do arquivo .env
W_API_HOST = "api.w-api.app"
W_API_INSTANCE_ID = "A2KKIF-WBQIPM-TCYIDI"
W_API_TOKEN = "m3mA0QbFwcT3InJckLPj9CBLSXaeNmtwG"
WEBHOOK_URL = "https://rqyyoofuwrwwfcuxfjwu.supabase.co/functions/v1/whatsapp-webhook"

def testar_envio_mensagem():
    """
    Testa o envio de mensagem para o número 14997751850
    """
    print("🚀 Iniciando teste de envio de mensagem")
    print(f"📱 Número de destino: 5514997751850")
    print(f"🕐 Horário: {datetime.now().strftime('%H:%M:%S')}")
    print("-" * 50)
    
    # Dados da mensagem simulando um webhook recebido
    webhook_data = {
        "instanceId": W_API_INSTANCE_ID,
        "messages": [{
            "key": {
                "remoteJid": "5514997751850@s.whatsapp.net",
                "fromMe": False,
                "id": f"MSG_TESTE_{int(datetime.now().timestamp())}"
            },
            "messageTimestamp": int(datetime.now().timestamp()),
            "pushName": "Teste Python",
            "message": {
                "conversation": "Olá! Este é um teste do sistema Python integrado ao webhook Supabase"
            }
        }]
    }
    
    try:
        print("📤 Enviando dados para o webhook...")
        print(f"🔗 URL: {WEBHOOK_URL}")
        print(f"📄 Payload: {json.dumps(webhook_data, indent=2)}")
        
        response = requests.post(
            WEBHOOK_URL,
            json=webhook_data,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {W_API_TOKEN}'
            },
            timeout=30
        )
        
        print(f"\n✅ Status Code: {response.status_code}")
        print(f"📋 Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"🎉 Sucesso! Resposta: {json.dumps(result, indent=2)}")
            
            if result.get('status') == 'success':
                print(f"✅ Mensagens processadas: {result.get('processed', 0)}")
                print("🤖 O sistema deve ter enviado uma mensagem de teste!")
            else:
                print(f"⚠️ Status: {result.get('status')}")
                
        else:
            print(f"❌ Erro HTTP: {response.status_code}")
            print(f"📄 Conteúdo: {response.text}")
            
    except requests.RequestException as e:
        print(f"❌ Erro na requisição: {e}")
    except json.JSONDecodeError as e:
        print(f"❌ Erro ao decodificar JSON: {e}")
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")

def verificar_webhook_status():
    """
    Verifica se o webhook está ativo
    """
    print("\n🔍 Verificando status do webhook...")
    
    try:
        response = requests.get(
            WEBHOOK_URL,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Webhook ativo: {result.get('message')}")
            return True
        else:
            print(f"❌ Webhook com problema: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao verificar webhook: {e}")
        return False

if __name__ == "__main__":
    print("🤖 SISTEMA DE TESTE WHATSAPP + SUPABASE")
    print("=" * 50)
    
    # Primeiro verificar se o webhook está funcionando
    if verificar_webhook_status():
        print("\n" + "=" * 50)
        # Fazer o teste de envio
        testar_envio_mensagem()
    else:
        print("❌ Webhook não está respondendo. Verifique a configuração.")
    
    print("\n" + "=" * 50)
    print("🏁 Teste concluído!")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 SISTEMA DE LOCAÇÃO - TOCA IMÓVEIS
Servidor FastAPI para integração com WhatsApp via W-API

Funcionalidades nesta versão:
- ✅ Receber mensagens via webhook
- ✅ Processar solicitações de locação
- ✅ Integração com W-API do WhatsApp
- ✅ Diferenciação entre colaboradores e clientes
- ✅ Menus interativos para colaboradores
- ✅ Processamento de respostas de menu (listResponseMessage)

NOVO v2.0: Sistema agora processa tanto mensagens de texto quanto respostas de menu
"""

import os
import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import logging

# Importar nossos serviços
from src.services.whatsapp_service import WhatsAppService

# Carregar variáveis de ambiente
load_dotenv()

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Inicializar FastAPI
app = FastAPI(
    title="🚀 Sistema de Locação",
    description="Sistema de atendimento para locação via WhatsApp",
    version="1.0.0"
)

# Inicializar serviços
whatsapp_service = WhatsAppService()

@app.get("/")
async def home():
    """Página inicial da API"""
    return {
        "projeto": "🏠 Sistema de Locação - Toca Imóveis",
        "status": "🚀 Sistema Online",
        "versao": "2.0.0",
        "recursos": [
            "✅ Atendimento via WhatsApp",
            "✅ Solicitação automática de CPF",
            "✅ Webhook W-API funcionando",
            "🔧 Processamento de documentos em desenvolvimento"
        ]
    }

@app.get("/health")
async def health_check():
    """Verificação de saúde do sistema"""
    return {
        "status": "healthy",
        "whatsapp_configured": bool(os.getenv('W_API_HOST')),
        "supabase_configured": bool(os.getenv('SUPABASE_URL')),
        "openai_configured": bool(os.getenv('OPENAI_API_KEY'))
    }

@app.post("/webhook")
async def webhook_whatsapp(request: Request):
    """
    Webhook para receber mensagens do WhatsApp via W-API
    """
    try:
        # Receber dados do webhook
        webhook_data = await request.json()
        
        # Só logar webhooks de mensagens recebidas
        if webhook_data.get('event') == 'webhookReceived':
            logger.info("📨 Nova mensagem recebida via webhook")
        
        # Processar mensagem através do serviço
        mensagem_processada = whatsapp_service.processar_webhook_mensagem(webhook_data)
        
        # Verificar se é uma mensagem válida
        if mensagem_processada.get("valido"):
            remetente = mensagem_processada.get("remetente")
            texto_mensagem = mensagem_processada.get("mensagem")
            message_id = mensagem_processada.get("message_id")
            nome_remetente = mensagem_processada.get("nome_remetente", "")
            
            # NOVA LÓGICA: VERIFICAR SE É RESPOSTA DE MENU
            # ==============================================
            
            # Extrair dados de resposta de menu se existir
            msg_content = webhook_data.get('msgContent', {})
            list_response = msg_content.get('listResponseMessage')
            
            if list_response:
                # É UMA RESPOSTA DE MENU INTERATIVO
                # --------------------------------
                single_select = list_response.get('singleSelectReply', {})
                row_id = single_select.get('selectedRowId')
                opcao_selecionada = list_response.get('title', 'Opção não identificada')
                
                logger.info(f"📋 RESPOSTA DE MENU de {nome_remetente}: {opcao_selecionada}")
                logger.info(f"🎯 Row ID capturado: {row_id}")
                
                # Processar resposta do menu usando a nova função
                logger.info(f"🔄 Processando resposta de menu: {row_id} do usuário {remetente}")
                resultado_menu = whatsapp_service.processar_resposta_menu_colaborador(
                    remetente=remetente,
                    row_id=row_id,
                    webhook_data=webhook_data
                )
                logger.info(f"✅ Resultado do processamento: {resultado_menu}")
                
                return JSONResponse(
                    status_code=200,
                    content={
                        "status": "menu_processado",
                        "remetente": remetente,
                        "nome_remetente": nome_remetente,
                        "opcao_selecionada": opcao_selecionada,
                        "row_id": row_id,
                        "acao_executada": resultado_menu.get("acao_executada"),
                        "sucesso": resultado_menu.get("sucesso")
                    }
                )
            
            else:
                # É UMA MENSAGEM DE TEXTO NORMAL
                # -----------------------------
                logger.info(f"💬 Mensagem de {nome_remetente}: {texto_mensagem}")
                
                # Interpretar mensagem do usuário com IA
                resultado = whatsapp_service.interpretar_mensagem_usuario(remetente, texto_mensagem, message_id)
                
                return JSONResponse(
                    status_code=200,
                    content={
                        "status": "interpretado",
                        "remetente": remetente,
                        "nome_remetente": nome_remetente,
                        "cpf_encontrado": resultado.get("cpf"),
                        "solicitar_cpf": resultado.get("solicitar_cpf"),
                        "mensagem_recebida": texto_mensagem[:50] + "..." if len(texto_mensagem) > 50 else texto_mensagem
                    }
                )
        else:
            # Mensagem não válida ou tipo não suportado
            return JSONResponse(status_code=200, content={"status": "ignorado"})
            
    except Exception as e:
        logger.error(f"❌ Erro no webhook: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "erro",
                "mensagem": str(e)
            }
        )

@app.post("/test/send-message")
async def test_send_message(telefone: str, mensagem: str = "Teste do Agente IA"):
    """
    Endpoint para testar envio de mensagem
    Usar apenas para desenvolvimento/teste
    """
    try:
        resultado = whatsapp_service.enviar_mensagem(telefone, mensagem)
        
        return JSONResponse(
            status_code=200 if resultado.get("sucesso") else 500,
            content=resultado
        )
        
    except Exception as e:
        logger.error(f"❌ Erro no teste de envio: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "sucesso": False,
                "erro": str(e)
            }
        )

if __name__ == "__main__":
    logger.info("🚀 Iniciando Sistema de Locação - Toca Imóveis...")
    
    # Verificar configurações essenciais
    required_env_vars = ['W_API_HOST', 'W_API_INSTANCE_ID', 'W_API_TOKEN']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"❌ Variáveis de ambiente faltando: {missing_vars}")
        exit(1)
    
    logger.info("✅ Configurações validadas")
    logger.info("📱 WhatsApp W-API configurado")
    logger.info("🌐 Servidor iniciando na porta 8000")
    logger.info(" Sistema pronto para atender!")
    
    # Iniciar servidor
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

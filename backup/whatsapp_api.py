import os
import requests
from typing import Dict, Any
import logging

# Configuração de logging
logger = logging.getLogger(__name__)

class WhatsAppAPI:
    """
    API dedicada para comunicação com W-API do WhatsApp
    
    RESPONSABILIDADES:
    =================
    - Envio de mensagens de texto
    - Verificação de números WhatsApp
    - Marcação de mensagens como lidas
    - Processamento de webhooks
    - Configuração e autenticação da API
    
    BENEFÍCIOS DA SEPARAÇÃO:
    =======================
    - Código de comunicação isolado
    - Fácil manutenção da integração
    - Testes unitários específicos
    - Reutilização em outros serviços
    - Menor risco de quebra em alterações
    
    VERSÃO: 1.0
    EXTRAÍDO DE: WhatsAppService DATA: JUlho/2025
    """
    
    def __init__(self):
        """Inicializar configurações da W-API"""
        # Carregar configurações do .env
        self.api_host = os.getenv('W_API_HOST', 'https://api.w-api.app')
        self.instance_id = os.getenv('W_API_INSTANCE_ID')
        self.token = os.getenv('W_API_TOKEN')
        
        # Headers padrão com Authorization Bearer
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.token}'
        }
        
        logger.info(f"WhatsApp API inicializada para instância: {self.instance_id}")

    def enviar_mensagem(self, numero_telefone: str, mensagem: str) -> Dict[str, Any]:
        """
        Envia uma mensagem via W-API
        
        Args:
            numero_telefone (str): Número do telefone no formato internacional
            mensagem (str): Texto da mensagem a ser enviada
            
        Returns:
            Dict: Resposta da API
        """
        try:
            # CORREÇÃO: Garantir que quebras de linha sejam interpretadas corretamente
            mensagem_formatada = mensagem.replace('\\n', '\n') if '\\n' in mensagem else mensagem
            
            # Nova URL da API W-API
            url = f"{self.api_host}/v1/message/send-text"
            
            # Parâmetros da nova API
            params = {
                "instanceId": self.instance_id
            }
            
            # Dados da mensagem conforme nova API
            payload = {
                "phone": numero_telefone,
                "message": mensagem_formatada,
                "delayMessage": 2
            }
            
            # Fazer requisição
            response = requests.post(url, json=payload, headers=self.headers, params=params)
            
            if response.status_code == 200:
                logger.info("✅ Mensagem enviada")
                return {
                    "sucesso": True,
                    "dados": response.json(),
                    "status_code": response.status_code
                }
            else:
                logger.error(f"❌ Erro ao enviar mensagem: {response.status_code}")
                return {
                    "sucesso": False,
                    "erro": response.text,
                    "status_code": response.status_code
                }
                
        except Exception as e:
            logger.error(f"❌ Erro ao enviar mensagem: {str(e)}")
            return {
                "sucesso": False,
                "erro": str(e),
                "status_code": 500
            }

    def marcar_como_lida(self, numero_telefone: str, message_id: str) -> Dict[str, Any]:
        """
        Marca uma mensagem como lida
        
        Args:
            numero_telefone (str): Número do telefone
            message_id (str): ID da mensagem
            
        Returns:
            Dict: Resposta da API
        """
        try:
            url = f"{self.api_host}/v1/message/read-message"
            
            params = {
                "instanceId": self.instance_id
            }
            
            payload = {
                "phone": numero_telefone,
                "messageId": message_id
            }
            
            response = requests.post(url, json=payload, headers=self.headers, params=params)
            
            return {
                "sucesso": response.status_code == 200,
                "dados": response.json() if response.status_code == 200 else None,
                "status_code": response.status_code
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao marcar mensagem como lida: {str(e)}")
            return {"sucesso": False, "erro": str(e)}

    def verificar_numero_tem_whatsapp(self, numero_telefone: str) -> Dict[str, Any]:
        """
        Verifica se um número de telefone possui WhatsApp ativo
        
        Args:
            numero_telefone (str): Número no formato brasileiro (ex: 5511999999999)
            
        Returns:
            Dict: {"existe": bool, "numero": str, "sucesso": bool}
        """
        try:
            # Limpar número (remover caracteres especiais)
            numero_limpo = ''.join(filter(str.isdigit, numero_telefone))
            
            # Se não começar com 55, adicionar
            if not numero_limpo.startswith('55'):
                numero_limpo = '55' + numero_limpo
            
            logger.info(f"📱 Verificando se número tem WhatsApp: {numero_limpo}")
            
            url = f"{self.api_host}/v1/contacts/phone-exists"
            params = {
                "instanceId": self.instance_id,
                "phoneNumber": numero_limpo
            }
            
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code == 200:
                resultado = response.json()
                existe = resultado.get("exists", False)
                
                logger.info(f"✅ Verificação WhatsApp: {numero_limpo} → {'EXISTE' if existe else 'NÃO EXISTE'}")
                
                return {
                    "sucesso": True,
                    "existe": existe,
                    "numero": numero_limpo,
                    "dados_api": resultado
                }
            else:
                logger.error(f"❌ Erro na verificação WhatsApp: {response.status_code}")
                return {
                    "sucesso": False,
                    "erro": f"API retornou status {response.status_code}",
                    "numero": numero_limpo
                }
                
        except Exception as e:
            logger.error(f"❌ Erro ao verificar WhatsApp: {str(e)}")
            return {
                "sucesso": False,
                "erro": str(e),
                "numero": numero_telefone
            }

    def processar_webhook_mensagem(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa dados do webhook de mensagem recebida (Formato W-API)
        
        Args:
            webhook_data (Dict): Dados do webhook da W-API
            
        Returns:
            Dict: Dados processados da mensagem
        """
        try:
            # Verificar se é o formato da W-API
            if webhook_data.get('event') == 'webhookReceived':
                # Verificar se não é mensagem nossa (fromMe)
                if webhook_data.get('fromMe', False):
                    return {
                        "valido": False,
                        "motivo": "Mensagem própria ignorada"
                    }
                
                # Extrair dados da mensagem
                msg_content = webhook_data.get('msgContent', {})
                sender = webhook_data.get('sender', {})
                chat = webhook_data.get('chat', {})
                
                # Extrair texto da mensagem
                texto_mensagem = msg_content.get('conversation', '')
                
                # Se não for conversation, tentar outros campos
                if not texto_mensagem:
                    texto_mensagem = msg_content.get('text', '') or msg_content.get('message', '')
                
                # NOVO: Verificar se é resposta de menu (listResponseMessage)
                # Para manter compatibilidade, vamos considerar válido mesmo sem texto
                list_response = msg_content.get('listResponseMessage')
                if list_response and not texto_mensagem:
                    # É uma resposta de menu, criar texto descritivo para processamento
                    opcao_selecionada = list_response.get('title', 'Opção selecionada')
                    texto_mensagem = f"[MENU] {opcao_selecionada}"
                
                # Extrair remetente
                remetente = sender.get('id', '')
                nome_remetente = sender.get('pushName', '')
                message_id = webhook_data.get('messageId', '')
                
                if remetente and texto_mensagem:
                    return {
                        "valido": True,
                        "remetente": remetente,
                        "mensagem": texto_mensagem,
                        "nome_remetente": nome_remetente,
                        "message_id": message_id,
                        "chat_id": chat.get('id'),
                        "timestamp": webhook_data.get('moment')
                    }
                else:
                    return {
                        "valido": False,
                        "motivo": "Dados de mensagem incompletos"
                    }
            else:
                return {
                    "valido": False,
                    "motivo": f"Evento não suportado: {webhook_data.get('event')}"
                }
                
        except Exception as e:
            logger.error(f"❌ Erro ao processar webhook: {str(e)}")
            return {
                "valido": False,
                "erro": str(e)
            } 
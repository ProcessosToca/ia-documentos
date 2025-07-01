import os
import requests
from typing import Dict, Any
import logging
from .openai_service import OpenAIService
from .buscar_usuarios_supabase import identificar_tipo_usuario

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WhatsAppService:
    """Serviço para integração com W-API do WhatsApp"""
    
    def __init__(self):
        # Carregar configurações do .env
        self.api_host = os.getenv('W_API_HOST', 'https://api.w-api.app')
        self.instance_id = os.getenv('W_API_INSTANCE_ID')
        self.token = os.getenv('W_API_TOKEN')
        
        # Headers padrão com Authorization Bearer
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.token}'
        }
        
        # Inicializar OpenAI Service
        self.openai_service = OpenAIService()
        
        # Dicionário para armazenar CPFs temporariamente
        self.cpfs_temp = {}
        
        logger.info(f"WhatsApp Service inicializado para instância: {self.instance_id}")
    
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
    
    def primeira_mensagem(self, remetente: str, message_id: str = None) -> Dict[str, Any]:
        """
        Envia primeira mensagem da Bia Corretora de Locação
        
        Args:
            remetente (str): Número do remetente
            message_id (str): ID da mensagem (opcional para marcar como lida)
            
        Returns:
            Dict: Resultado do processamento
        """
        try:
            # Marcar mensagem como lida
            if message_id:
                self.marcar_como_lida(remetente, message_id)
            
            # Mensagem de boas-vindas da Bia
            mensagem = (
                "Olá! 👋\n\n"
                "Aqui é a Bia, Corretora de Locação\n\n"
                "Para iniciarmos seu atendimento, por favor me envie seu CPF (apenas números).\n\n"
                "Exemplo: 12345678901"
            )
            
            # Enviar mensagem
            resultado = self.enviar_mensagem(remetente, mensagem)
            
            return {
                "novo_usuario": True,
                "cpf": None,
                "solicitar_cpf": True,
                "mensagem_resposta": mensagem
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar primeira mensagem: {str(e)}")
            return {
                "novo_usuario": True,
                "cpf": None,
                "solicitar_cpf": True,
                "mensagem_resposta": "Erro ao enviar mensagem inicial"
            }
    
    def interpretar_mensagem_usuario(self, remetente: str, mensagem: str, message_id: str = None) -> Dict[str, Any]:
        """
        Interpreta a mensagem do usuário usando OpenAI e gerencia o fluxo de CPF
        
        Args:
            remetente (str): Número do remetente
            mensagem (str): Mensagem do usuário
            message_id (str): ID da mensagem (opcional)
            
        Returns:
            Dict: Resultado do processamento
        """
        try:
            # Marcar mensagem como lida
            if message_id:
                self.marcar_como_lida(remetente, message_id)
            
            # Interpretar mensagem com OpenAI
            resultado = self.openai_service.interpretar_mensagem(mensagem)
            logger.info(f"🔍 Resultado da interpretação: {resultado}")
            
            # PRIORIDADE 1: Se encontrou CPF, processar imediatamente
            if resultado.get("cpf"):
                cpf = resultado["cpf"]
                self.cpfs_temp[remetente] = cpf
                logger.info(f"✅ CPF recebido: {cpf}")
                
                # Identificar se é corretor ou cliente
                identificacao = identificar_tipo_usuario(cpf)
                logger.info(f"👤 Tipo de usuário identificado: {identificacao}")
                
                # Usar apenas a mensagem da identificação
                mensagem_resposta = identificacao['mensagem']
                
                # Enviar resposta ao usuário
                self.enviar_mensagem(remetente, mensagem_resposta)
                
                # Adicionar tipo de usuário ao resultado
                resultado["tipo_usuario"] = identificacao["tipo"]
                resultado["mensagem_resposta"] = mensagem_resposta
                
                return resultado
            
            # PRIORIDADE 2: Se for novo usuário e NÃO tem CPF, enviar primeira mensagem
            if resultado.get("novo_usuario"):
                logger.info("👋 Novo usuário detectado")
                return self.primeira_mensagem(remetente, message_id)
            
            # PRIORIDADE 3: Outras mensagens
            # Enviar resposta ao usuário
            self.enviar_mensagem(remetente, resultado["mensagem_resposta"])
            
            return resultado
            
        except Exception as e:
            logger.error(f"❌ Erro ao interpretar mensagem do usuário: {str(e)}")
            return {
                "cpf": None,
                "novo_usuario": False,
                "solicitar_cpf": True,
                "mensagem_resposta": "Desculpe, tive um problema ao processar sua mensagem. Por favor, envie seu CPF novamente."
            } 
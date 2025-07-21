# Menu Service - WhatsApp
# Arquivo reservado para implementação futura dos menus interativos 

import os
import requests
import logging
from typing import Dict, Any

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MenuServiceWhatsApp:
    """
    Serviço para enviar menus interativos via W-API WhatsApp
    """
    
    def __init__(self):
        self.api_host = os.getenv('W_API_HOST', 'https://api.w-api.app')
        self.instance_id = os.getenv('W_API_INSTANCE_ID')
        self.token = os.getenv('W_API_TOKEN')
        
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.token}'
        }
        
        # Obter nome da empresa do .env com fallback
        self.company_name = os.getenv('COMPANY_NAME', 'Locação Online')
        
        logger.info("📋 MenuServiceWhatsApp inicializado")

    def processar_resposta_menu(self, row_id: str, usuario_id: str, webhook_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Função genérica para processar respostas de QUALQUER menu
        
        Args:
            row_id (str): ID da opção selecionada pelo usuário (ex: "concordo_dados")
            usuario_id (str): Telefone/ID do usuário que respondeu
            webhook_data (Dict, optional): Dados completos do webhook para contexto
            
        Returns:
            Dict: Resultado do processamento com próxima ação
        """
        try:
            logger.info(f"📋 Processando resposta de menu: {row_id} do usuário {usuario_id}")
            
            # Dicionário com todas as ações possíveis de todos os menus
            acoes_menu = {
                # MENU DE CONCORDÂNCIA LGPD
                "concordo_dados": {
                    "acao": "registrar_concordancia_dados",
                    "mensagem": "✅ Concordância registrada! Seus dados serão tratados conforme nossa política de privacidade.",
                    "proximo_passo": "aguardar_concordancia_documentos"
                },
                "politica_privacidade": {
                    "acao": "enviar_politica",
                    "mensagem": "📄 Aqui está nossa política de privacidade...",
                    "proximo_passo": "aguardar_concordancia"
                },
                "concordo_documentos": {
                    "acao": "registrar_concordancia_documentos", 
                    "mensagem": "✅ Autorização para documentos registrada!",
                    "proximo_passo": "aguardar_concordancia_total"
                },
                "lista_documentos": {
                    "acao": "mostrar_lista_documentos",
                    "mensagem": "📋 Documentos necessários:\n• RG ou CNH\n• Comprovante de renda\n• Comprovante de residência\n• Certidão de nascimento/casamento (opcional)",
                    "proximo_passo": "aguardar_decisao"
                },
                "concordo_tudo": {
                    "acao": "iniciar_processo_completo",
                    "mensagem": "🎉 Perfeito! Vamos iniciar seu processo de locação sem fiador. Me peça para enviar documentos que inicio a sequência de envios com você! 📄",
                    "proximo_passo": "aguardar_solicitacao_documentos"
                },
                "mais_informacoes": {
                    "acao": "transferir_atendente",
                    "mensagem": "👥 Vou conectar você com um de nossos atendentes para esclarecer suas dúvidas.",
                    "proximo_passo": "aguardar_atendente"
                },
                
                # MENU DE OPÇÕES DE ATENDIMENTO
                "usar_ia_duvidas": {
                    "acao": "ativar_ia_especializada",
                    "mensagem": "🤖 IA Especializada Ativada! Pode me perguntar",''
                    "proximo_passo": "aguardando_duvida_locacao"
                },
                "iniciar_fechamento": {
                    "acao": "coletar_nome_cliente",
                    "mensagem": "📝 Vamos coletar dados do cliente para iniciar o fechamento.\n\n*Por favor, informe o nome completo do cliente:*",
                    "proximo_passo": "aguardando_nome_cliente"
                },
                
                # MENU DE CONFIRMAÇÃO SIMPLES
                "confirmar_sim": {
                    "acao": "confirmar_acao",
                    "mensagem": "✅ Confirmado! Prosseguindo com a ação.",
                    "proximo_passo": "acao_confirmada"
                },
                "confirmar_nao": {
                    "acao": "cancelar_acao", 
                    "mensagem": "❌ Ação cancelada.",
                    "proximo_passo": "acao_cancelada"
                },
                
                # MENU DE CONFIRMAÇÃO - ATENDIMENTO CLIENTE
                "confirmar_atendimento_sim": {
                    "acao": "iniciar_atendimento_cliente",
                    "mensagem": "✅ Iniciando contato com o cliente...",
                    "proximo_passo": "contato_cliente_iniciado"
                },
                "confirmar_atendimento_nao": {
                    "acao": "encerrar_atendimento_corretor",
                    "mensagem": "Obrigado pelo retorno, estamos encerrando seu atendimento.",
                    "proximo_passo": "atendimento_encerrado"
                },
                
                # MENU DE CONFIRMAÇÃO DO CLIENTE
                "cliente_aceita_atendimento": {
                    "acao": "solicitar_cpf_cliente",
                    "mensagem": "✅ Perfeito! Para prosseguir, preciso do seu CPF.",
                    "proximo_passo": "aguardando_cpf_cliente"
                },
                "cliente_recusa_atendimento": {
                    "acao": "encerrar_atendimento_cliente",
                    "mensagem": "Entendido! Qualquer dúvida, estaremos à disposição.",
                    "proximo_passo": "atendimento_cliente_encerrado"
                },
                
                # MENU DE CONFIRMAÇÃO DE ENDEREÇO
                "confirmar_endereco_sim": {
                    "acao": "confirmar_endereco",
                    "mensagem": "✅ Endereço confirmado! Agora preciso do número da residência:",
                    "proximo_passo": "aguardando_numero"
                },
                "confirmar_endereco_nao": {
                    "acao": "corrigir_endereco",
                    "mensagem": "❌ Vamos corrigir o endereço. Por favor, digite o CEP novamente:",
                    "proximo_passo": "aguardando_cep"
                },
                
                # MENU DE CONFIRMAÇÃO DE DOCUMENTOS
                "confirmar_documentos_sim": {
                    "acao": "iniciar_coleta_documentos",
                    "mensagem": "✅ Perfeito! Vamos começar a coleta de documentos. Vou te encaminhar a lista de Documentos necessários .",
                    "proximo_passo": "aguardando_solicitacao_documentos"
                },
                "confirmar_documentos_nao": {
                    "acao": "encerrar_processo_documentos",
                    "mensagem": "Entendido! Qualquer dúvida sobre documentos, estaremos à disposição. Obrigado pelo contato! 👋",
                    "proximo_passo": "processo_encerrado"
                },
                
                # ESPAÇO PARA FUTUROS MENUS
                # "menu_documentos_xxx": {...},
                # "menu_status_xxx": {...},
                # "menu_contato_xxx": {...},
            }
            
            # Verificar se o row_id existe no mapeamento
            if row_id in acoes_menu:
                resposta = acoes_menu[row_id]
                
                logger.info(f"✅ Ação encontrada: {resposta['acao']}")
                
                return {
                    "sucesso": True,
                    "row_id": row_id,
                    "acao": resposta["acao"],
                    "mensagem_resposta": resposta["mensagem"],
                    "proximo_passo": resposta["proximo_passo"],
                    "usuario_id": usuario_id
                }
            else:
                logger.warning(f"⚠️ Row ID não reconhecido: {row_id}")
                return {
                    "sucesso": False,
                    "erro": f"Opção não reconhecida: {row_id}",
                    "mensagem_resposta": "Desculpe, não entendi sua escolha. Pode tentar novamente?",
                    "row_id": row_id,
                    "usuario_id": usuario_id
                }
                
        except Exception as e:
            logger.error(f"❌ Erro ao processar resposta do menu: {str(e)}")
            return {
                "sucesso": False,
                "erro": str(e),
                "mensagem_resposta": "Tive um problema ao processar sua escolha. Pode tentar novamente?",
                "row_id": row_id,
                "usuario_id": usuario_id
            }

    # Menu de LGPD
    def enviar_menu_concordancia_dados(self, numero_telefone: str) -> Dict[str, Any]:
        """
        Envia menu de concordância com divulgação de dados e documentos
        
        Args:
            numero_telefone (str): Número do telefone do destinatário
            
        Returns:
            Dict: Resposta da API
        """
        try:
            url = f"{self.api_host}/v1/message/send-list"
            
            params = {
                "instanceId": self.instance_id
            }
            
            payload = {
                "phone": numero_telefone,
                "title": "📋 Concordância - Dados e Documentos",
                "description": "Para prosseguir com sua locação, precisamos da sua concordância sobre o tratamento de dados pessoais e envio de documentos.",
                "buttonText": "Ver Opções",
                "footerText": f"{self.company_name} - Locação Sem Fiador",
                "sections": [
                    {
                        "title": "✅ Concordância Completa",
                        "rows": [
                            {
                                "title": "Concordo com tudo e prosseguir",
                                "description": "Aceito todos os termos e quero iniciar o processo",
                                "rowId": "concordo_tudo"
                            },
                            {
                                "title": "Preciso de mais informações",
                                "description": "Falar com atendente antes de concordar",
                                "rowId": "mais_informacoes"
                            }
                        ]
                    },
                    {
                        "title": "📄 Dados Pessoais",
                        "rows": [
                            {
                                "title": "Concordo com tratamento de dados",
                                "description": "Autorizo o uso dos meus dados para processo de locação",
                                "rowId": "concordo_dados"
                            },
                            {
                                "title": "Ler política de privacidade",
                                "description": "Visualizar termos de privacidade completos",
                                "rowId": "politica_privacidade"
                            }
                        ]
                    },
                    {
                        "title": "📂 Documentos",
                        "rows": [
                            {
                                "title": "Concordo em enviar documentos",
                                "description": "Autorizo envio de RG, CPF, comprovantes necessários",
                                "rowId": "concordo_documentos"
                            },
                            {
                                "title": "Ver lista de documentos",
                                "description": "Consultar quais documentos serão solicitados",
                                "rowId": "lista_documentos"
                            }
                        ]
                    }
                ],
                "delayMessage": 2
            }
            
            response = requests.post(url, json=payload, headers=self.headers, params=params)
            
            if response.status_code == 200:
                logger.info("✅ Menu de concordância enviado com sucesso")
                return {
                    "sucesso": True,
                    "dados": response.json(),
                    "status_code": response.status_code
                }
            else:
                logger.error(f"❌ Erro ao enviar menu: {response.status_code}")
                return {
                    "sucesso": False,
                    "erro": response.text,
                    "status_code": response.status_code
                }
                
        except Exception as e:
            logger.error(f"❌ Erro ao enviar menu de concordância: {str(e)}")
            return {
                "sucesso": False,
                "erro": str(e),
                "status_code": 500
            }

    # Menu de Opções de Atendimento
    def enviar_menu_opcoes_atendimento(self, numero_telefone: str) -> Dict[str, Any]:
        """
        Envia menu com opções de atendimento: IA para dúvidas ou iniciar fechamento
        
        Args:
            numero_telefone (str): Número do telefone do destinatário
            
        Returns:
            Dict: Resposta da API
        """
        try:
            url = f"{self.api_host}/v1/message/send-list"
            
            params = {
                "instanceId": self.instance_id
            }
            
            payload = {
                "phone": numero_telefone,
                "title": " Opções de Atendimento",
                "description": "Como posso ajudar você hoje? Escolha uma das opções abaixo:",
                "buttonText": "Ver Opções",
                "footerText": f"{self.company_name} - Locação Sem Fiador",
                "sections": [
                    {
                        "title": "🔧 Atendimento",
                        "rows": [
                            {
                                "title": "🤖 Usar IA para Dúvidas",
                                "description": "Converse comigo sobre locação, documentos e processos",
                                "rowId": "usar_ia_duvidas"
                            },
                            {
                                "title": "🏠 Iniciar Fechamento Locação",
                                "description": "Dar início ao processo de fechamento da locação",
                                "rowId": "iniciar_fechamento"
                            }
                        ]
                    }
                ],
                "delayMessage": 2
            }
            
            response = requests.post(url, json=payload, headers=self.headers, params=params)
            
            if response.status_code == 200:
                logger.info("✅ Menu de opções de atendimento enviado com sucesso")
                return {
                    "sucesso": True,
                    "dados": response.json(),
                    "status_code": response.status_code
                }
            else:
                logger.error(f"❌ Erro ao enviar menu: {response.status_code}")
                return {
                    "sucesso": False,
                    "erro": response.text,
                    "status_code": response.status_code
                }
                
        except Exception as e:
            logger.error(f"❌ Erro ao enviar menu de opções de atendimento: {str(e)}")
            return {
                "sucesso": False,
                "erro": str(e),
                "status_code": 500
            }

    # Menu de Confirmação Simples
    def enviar_menu_confirmacao(self, numero_telefone: str, titulo: str = "Confirmação", pergunta: str = "Deseja prosseguir?") -> Dict[str, Any]:
        """
        Envia menu de confirmação simples com apenas "Sim" e "Não"
        
        Args:
            numero_telefone (str): Número do telefone do destinatário
            titulo (str): Título do menu de confirmação
            pergunta (str): Pergunta a ser feita ao usuário
            
        Returns:
            Dict: Resposta da API
        """
        try:
            url = f"{self.api_host}/v1/message/send-list"
            
            params = {
                "instanceId": self.instance_id
            }
            
            payload = {
                "phone": numero_telefone,
                "title": f"❓ {titulo}",
                "description": pergunta,
                "buttonText": "Responder",
                "footerText": f"{self.company_name} - Confirmação",
                "sections": [
                    {
                        "title": "Sua resposta:",
                        "rows": [
                            {
                                "title": "✅ Sim",
                                "description": "Confirmar e prosseguir",
                                "rowId": "confirmar_sim"
                            },
                            {
                                "title": "❌ Não",
                                "description": "Cancelar ação",
                                "rowId": "confirmar_nao"
                            }
                        ]
                    }
                ],
                "delayMessage": 1
            }
            
            response = requests.post(url, json=payload, headers=self.headers, params=params)
            
            if response.status_code == 200:
                logger.info("✅ Menu de confirmação enviado com sucesso")
                return {
                    "sucesso": True,
                    "dados": response.json(),
                    "status_code": response.status_code
                }
            else:
                logger.error(f"❌ Erro ao enviar menu: {response.status_code}")
                return {
                    "sucesso": False,
                    "erro": response.text,
                    "status_code": response.status_code
                }
                
        except Exception as e:
            logger.error(f"❌ Erro ao enviar menu de confirmação: {str(e)}")
            return {
                "sucesso": False,
                "erro": str(e),
                "status_code": 500
            }

    # Menu de Confirmação de Atendimento
    def enviar_menu_confirmacao_atendimento(self, numero_telefone: str, cliente_nome: str) -> Dict[str, Any]:
        """
        Envia menu de confirmação específico para iniciar atendimento com cliente
        
        Args:
            numero_telefone (str): Número do telefone do corretor
            cliente_nome (str): Nome do cliente para personalizar a mensagem
            
        Returns:
            Dict: Resposta da API
        """
        try:
            url = f"{self.api_host}/v1/message/send-list"
            
            params = {
                "instanceId": self.instance_id
            }
            
            payload = {
                "phone": numero_telefone,
                "title": "🏠 Iniciar Atendimento",
                "description": f"Posso seguir com o Atendimento ao Cliente {cliente_nome}?",
                "buttonText": "Responder",
                "footerText": f"{self.company_name} - Fechamento",
                "sections": [
                    {
                        "title": "Sua decisão:",
                        "rows": [
                            {
                                "title": "✅ Sim",
                                "description": "Iniciar contato com o cliente",
                                "rowId": "confirmar_atendimento_sim"
                            },
                            {
                                "title": "❌ Não",
                                "description": "Encerrar processo",
                                "rowId": "confirmar_atendimento_nao"
                            }
                        ]
                    }
                ],
                "delayMessage": 1
            }
            
            response = requests.post(url, json=payload, headers=self.headers, params=params)
            
            if response.status_code == 200:
                logger.info("✅ Menu de confirmação de atendimento enviado com sucesso")
                return {
                    "sucesso": True,
                    "dados": response.json(),
                    "status_code": response.status_code
                }
            else:
                logger.error(f"❌ Erro ao enviar menu: {response.status_code}")
                return {
                    "sucesso": False,
                    "erro": response.text,
                    "status_code": response.status_code
                }
                
        except Exception as e:
            logger.error(f"❌ Erro ao enviar menu de confirmação de atendimento: {str(e)}")
            return {
                "sucesso": False,
                "erro": str(e),
                "status_code": 500
            }

    # Menu de Confirmação do Cliente
    def enviar_menu_confirmacao_cliente(self, numero_telefone: str, corretor_nome: str) -> Dict[str, Any]:
        """
        Envia menu de confirmação para o cliente sobre aceitar atendimento do corretor
        
        Args:
            numero_telefone (str): Número do telefone do cliente
            corretor_nome (str): Nome do corretor
            
        Returns:
            Dict: Resposta da API
        """
        try:
            url = f"{self.api_host}/v1/message/send-list"
            
            params = {
                "instanceId": self.instance_id
            }
            
            payload = {
                "phone": numero_telefone,
                "title": "🏢 Confirmação de Atendimento",
                "description": f"O corretor {corretor_nome} da {self.company_name} está pronto para atendê-lo. Deseja prosseguir?",
                "buttonText": "Selecione uma opção",
                "footerText": f"{self.company_name} - Locação Sem Fiador",
                "sections": [
                    {
                        "title": "Opções de Atendimento",
                        "rows": [
                            {
                                "title": "✅ Sim, aceito o atendimento",
                                "description": "Prosseguir com o corretor",
                                "rowId": "cliente_aceita_atendimento"
                            },
                            {
                                "title": "❌ Não, não aceito",
                                "description": "Encerrar atendimento",
                                "rowId": "cliente_recusa_atendimento"
                            }
                        ]
                    }
                ],
                "delayMessage": 2
            }
            
            response = requests.post(url, json=payload, headers=self.headers, params=params)
            
            if response.status_code == 200:
                logger.info("✅ Menu de confirmação do cliente enviado com sucesso")
                return {
                    "sucesso": True,
                    "dados": response.json(),
                    "status_code": response.status_code
                }
            else:
                logger.error(f"❌ Erro ao enviar menu do cliente: {response.status_code}")
                return {
                    "sucesso": False,
                    "erro": response.text,
                    "status_code": response.status_code
                }
                
        except Exception as e:
            logger.error(f"❌ Erro ao enviar menu de confirmação do cliente: {str(e)}")
            return {
                "sucesso": False,
                "erro": str(e),
                "status_code": 500
            }

    def enviar_menu_confirmacao_endereco(self, numero_telefone: str, endereco: str) -> Dict[str, Any]:
        """
        Envia menu de confirmação de endereço
        
        Args:
            numero_telefone (str): Número do telefone do destinatário
            endereco (str): Endereço encontrado para confirmar
            
        Returns:
            Dict: Resposta da API
        """
        try:
            url = f"{self.api_host}/v1/message/send-list"
            
            params = {
                "instanceId": self.instance_id
            }
            
            payload = {
                "phone": numero_telefone,
                "title": "📍 Confirmação de Endereço",
                "description": "O endereço encontrado está correto?",
                "buttonText": "Responder",
                "footerText": f"{self.company_name} - Locação Sem Fiador",
                "sections": [
                    {
                        "title": "Opções",
                        "rows": [
                            {
                                "title": "✅ Sim, endereço correto",
                                "description": "Confirmar e prosseguir para número",
                                "rowId": "confirmar_endereco_sim"
                            },
                            {
                                "title": "❌ Não, endereço incorreto",
                                "description": "Digitar CEP novamente",
                                "rowId": "confirmar_endereco_nao"
                            }
                        ]
                    }
                ],
                "delayMessage": 1
            }
            
            response = requests.post(url, json=payload, headers=self.headers, params=params)
            
            if response.status_code == 200:
                logger.info(f"✅ Menu de confirmação de endereço enviado para {numero_telefone}")
                return {
                    "sucesso": True,
                    "dados": response.json(),
                    "status_code": response.status_code
                }
            else:
                logger.error(f"❌ Erro ao enviar menu: {response.status_code}")
                return {
                    "sucesso": False,
                    "erro": response.text,
                    "status_code": response.status_code
                }
                
        except Exception as e:
            logger.error(f"❌ Erro ao enviar menu de confirmação de endereço: {str(e)}")
            return {
                "sucesso": False,
                "erro": str(e),
                "status_code": 500
            }

    def enviar_menu_confirmacao_documentos(self, numero_telefone: str) -> Dict[str, Any]:
        """
        Envia menu de confirmação para prosseguir com coleta de documentos para locação
        
        Args:
            numero_telefone (str): Número do telefone do destinatário
            
        Returns:
            Dict: Resposta da API
        """
        try:
            url = f"{self.api_host}/v1/message/send-list"
            
            params = {
                "instanceId": self.instance_id
            }
            
            payload = {
                "phone": numero_telefone,
                "title": "📄 Coleta de Documentos",
                "description": "Deseja prosseguir com a coleta de documentos para sua locação?",
                "buttonText": "Responder",
                "footerText": f"{self.company_name} - Locação Sem Fiador",
                "sections": [
                    {
                        "title": "Sua decisão:",
                        "rows": [
                            {
                                "title": "✅ Sim, quero enviar documentos",
                                "description": "Prosseguir com coleta de documentos",
                                "rowId": "confirmar_documentos_sim"
                            },
                            {
                                "title": "❌ Não, não quero agora",
                                "description": "Encerrar processo por enquanto",
                                "rowId": "confirmar_documentos_nao"
                            }
                        ]
                    }
                ],
                "delayMessage": 1
            }
            
            response = requests.post(url, json=payload, headers=self.headers, params=params)
            
            if response.status_code == 200:
                logger.info("✅ Menu de confirmação de documentos enviado com sucesso")
                return {
                    "sucesso": True,
                    "dados": response.json(),
                    "status_code": response.status_code
                }
            else:
                logger.error(f"❌ Erro ao enviar menu: {response.status_code}")
                return {
                    "sucesso": False,
                    "erro": response.text,
                    "status_code": response.status_code
                }
                
        except Exception as e:
            logger.error(f"❌ Erro ao enviar menu de confirmação de documentos: {str(e)}")
            return {
                "sucesso": False,
                "erro": str(e),
                "status_code": 500
            }
        
        
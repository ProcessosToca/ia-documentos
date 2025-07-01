import os
import requests
from typing import Dict, Any
import logging
from .openai_service import OpenAIService
from .buscar_usuarios_supabase import identificar_tipo_usuario
from .menu_service_whatsapp import MenuServiceWhatsApp
import time

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WhatsAppService:
    """
    Serviço para integração com W-API do WhatsApp
    
    FUNCIONALIDADES PRINCIPAIS:
    ==========================
    
    1. IDENTIFICAÇÃO DE USUÁRIOS:
       - Processa CPF via OpenAI
       - Identifica se é colaborador ou cliente
       - Direciona para fluxos específicos
    
    2. FLUXO DIFERENCIADO POR TIPO:
       - COLABORADORES: Recebem menu de opções (IA + Fechamento)
       - CLIENTES: Mantêm fluxo original (LGPD + Documentos)
    
    3. MENUS INTERATIVOS:
       - Integração com MenuServiceWhatsApp
       - Processamento de respostas de menu
       - Tratamento de erros robusto
    
    4. COMUNICAÇÃO:
       - Envio de mensagens
       - Marcação como lida
       - Processamento de webhooks
    
    MANUTENÇÃO:
    ===========
    - Logs detalhados em todas as operações
    - Tratamento de exceções em cada função
    - Comentários explicativos para futuras alterações
    - Fallbacks para quando menus falham
    
    VERSÃO: 2.0 (Adicionado suporte a menus para colaboradores)
    DATA: Março/2024
    """
    
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
        
        # Inicializar Menu Service para WhatsApp
        # Este serviço gerencia menus interativos enviados aos usuários
        self.menu_service = MenuServiceWhatsApp()
        
        # Dicionário para armazenar CPFs temporariamente
        self.cpfs_temp = {}
        
        # Sistema de sessões com timeout para IA especializada
        self.sessoes_ativas = {}
        self.TIMEOUT_SESSAO = 30 * 60  # 30 minutos em segundos
        
        # Sistema de coleta de dados do cliente para fechamento
        # Formato: {telefone_colaborador: {"nome": "", "telefone": "", "etapa": "aguardando_nome|aguardando_telefone|concluido"}}
        self.coleta_dados_cliente = {}
        
        # Sistema de atendimentos iniciados com clientes
        # Formato: {telefone_corretor: {"cliente_nome": "", "cliente_telefone": "", "corretor_nome": "", "status": "..."}}
        self.atendimentos_cliente = {}
        
        logger.info(f"WhatsApp Service inicializado para instância: {self.instance_id}")
        logger.info("🔧 Novo recurso ativo: Menu diferenciado para colaboradores")

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
        
        # IMPORTANTE PARA MANUTENÇÃO:
        # ===========================
        # 
        # FLUXO DE USO DA NOVA FUNCIONALIDADE:
        # 
        # 1. Usuário envia CPF
        # 2. Sistema identifica se é colaborador ou cliente
        # 3. Se COLABORADOR: 
        #    - Envia mensagem de boas-vindas
        #    - Aguarda 3 segundos
        #    - Envia menu com opções: "Usar IA" e "Iniciar Fechamento"
        # 4. Se CLIENTE:
        #    - Mantém fluxo original (sem alterações)
        # 
        # PARA PROCESSAR RESPOSTAS DE MENU:
        # - Use a função: processar_resposta_menu_colaborador()
        # - Passe o row_id recebido do webhook
        # 
                 # CÓDIGOS DE ROW_ID DISPONÍVEIS:
         # - "usar_ia_duvidas" → Ativa chat com IA
         # - "iniciar_fechamento" → Inicia processo de fechamento

    def identificar_tipo_usuario_rapido(self, remetente: str) -> str:
        """
        Identificação rápida do tipo de usuário para processamento de intenções
        
        Esta função faz uma verificação básica para determinar se o usuário
        é colaborador ou cliente, sem fazer consultas pesadas ao banco.
        
        Args:
            remetente (str): Número do telefone do usuário
            
        Returns:
            str: "colaborador" | "cliente" | "desconhecido"
            
        Nota:
            - Verifica primeiro se existe sessão ativa (colaborador)
            - Futuramente pode consultar cache de usuários identificados
            - Em caso de dúvida, retorna "desconhecido" para continuar fluxo normal
        """
        try:
            # VERIFICAÇÃO 1: Se tem sessão ativa, é colaborador
            if remetente in self.sessoes_ativas:
                return "colaborador"
            
            # VERIFICAÇÃO 2: Aqui poderíamos consultar cache de usuários identificados
            # Por enquanto, retorna desconhecido para não quebrar o fluxo
            # TODO: Implementar cache de identificação de usuários
            
            logger.info(f"🔍 Tipo de usuário não identificado rapidamente: {remetente}")
            return "desconhecido"
            
        except Exception as e:
            logger.warning(f"⚠️ Erro na identificação rápida de usuário: {e}")
            return "desconhecido"

    def processar_intencao_interpretada(self, remetente: str, interpretacao: Dict[str, Any], message_id: str = None) -> Dict[str, Any]:
        """
        Processa intenções detectadas pelo interpretador GPT
        
        Esta função é chamada quando o interpretador GPT detecta uma intenção
        específica (saudação ou menu) e executa a ação apropriada.
        
        Args:
            remetente (str): Número do telefone do usuário
            interpretacao (Dict): Resultado da análise do GPT com intenção detectada
            message_id (str, optional): ID da mensagem para marcar como lida
            
        Returns:
            Dict com resultado do processamento da intenção
            
        Fluxo de processamento:
            - SAUDAÇÃO → Primeira mensagem da Bia (solicita CPF)
            - MENU + Colaborador → Menu de opções de atendimento
            - MENU + Cliente → [FUTURO] Menu do cliente
            - Outros casos → Continua fluxo normal
        """
        try:
            intencao = interpretacao.get("intencao")
            confianca = interpretacao.get("confianca", 0.0)
            
            logger.info(f"🎯 Processando intenção '{intencao}' com confiança {confianca:.2f}")
            
            # Marcar mensagem como lida se fornecido
            if message_id:
                self.marcar_como_lida(remetente, message_id)
            
            # ====================================================================
            # PROCESSAMENTO DE SAUDAÇÕES - Primeira mensagem da Bia
            # ====================================================================
            if intencao == "saudacao":
                logger.info(f"👋 Saudação detectada de: {remetente}")
                
                # Enviar primeira mensagem padrão da Bia
                resultado = self.primeira_mensagem(remetente, message_id)
                
                # Adicionar informações da interpretação para logs
                resultado.update({
                    "interpretacao_gpt": True,
                    "intencao_detectada": "saudacao",
                    "confianca_gpt": confianca,
                    "acao_executada": "primeira_mensagem_bia"
                })
                
                return resultado
            
            # ====================================================================
            # PROCESSAMENTO DE SOLICITAÇÕES DE MENU
            # ====================================================================
            elif intencao == "menu":
                logger.info(f"📋 Solicitação de menu detectada de: {remetente}")
                
                # Identificar tipo de usuário para enviar menu apropriado
                tipo_usuario = self.identificar_tipo_usuario_rapido(remetente)
                
                # MENU PARA COLABORADORES - Implementado
                if tipo_usuario == "colaborador":
                    logger.info(f"👨‍💼 Enviando menu de colaborador para: {remetente}")
                    
                    # Enviar menu de opções de atendimento existente
                    resultado_menu = self.menu_service.enviar_menu_opcoes_atendimento(remetente)
                    
                    if resultado_menu.get("sucesso"):
                        return {
                            "sucesso": True,
                            "interpretacao_gpt": True,
                            "intencao_detectada": "menu",
                            "tipo_usuario": "colaborador",
                            "acao_executada": "menu_colaborador_enviado",
                            "confianca_gpt": confianca,
                            "mensagem_resposta": "Menu de colaborador enviado com sucesso"
                        }
                    else:
                        # Fallback se menu falhar
                        logger.warning(f"⚠️ Falha ao enviar menu de colaborador")
                        self.enviar_mensagem(remetente, "Menu temporariamente indisponível. Como posso ajudar?")
                        return {
                            "sucesso": False,
                            "erro": "falha_envio_menu_colaborador",
                            "fallback_executado": True
                        }
                
                # MENU PARA CLIENTES - Futuro
                elif tipo_usuario == "cliente":
                    logger.info(f"👥 Menu de cliente solicitado (implementação futura): {remetente}")
                    
                    # TODO: Implementar menu específico para clientes
                    # return self.menu_service.enviar_menu_cliente(remetente)
                    
                    # Por enquanto, apenas registra a solicitação
                    return {
                        "sucesso": True,
                        "interpretacao_gpt": True,
                        "intencao_detectada": "menu",
                        "tipo_usuario": "cliente", 
                        "acao_executada": "menu_cliente_pendente",
                        "confianca_gpt": confianca,
                        "implementacao": "futura",
                        "mensagem_resposta": "Menu de cliente será implementado em breve"
                    }
                
                # USUÁRIO DESCONHECIDO - Continuar fluxo normal
                else:
                    logger.info(f"❓ Menu solicitado por usuário não identificado: {remetente}")
                    return {
                        "bypass_fluxo": False,
                        "continuar_fluxo_normal": True,
                        "motivo": "usuario_nao_identificado"
                    }
            
            # ====================================================================
            # OUTRAS INTENÇÕES - Continuar fluxo normal
            # ====================================================================
            else:
                logger.info(f"🔄 Intenção '{intencao}' não requer bypass, continuando fluxo normal")
                return {
                    "bypass_fluxo": False,
                    "continuar_fluxo_normal": True,
                    "intencao_detectada": intencao
                }
                
        except Exception as e:
            logger.error(f"❌ Erro ao processar intenção interpretada: {str(e)}")
            # Em caso de erro, sempre continuar fluxo normal
            return {
                "bypass_fluxo": False,
                "continuar_fluxo_normal": True,
                "erro": str(e)
            }

    def sessao_ativa(self, telefone: str) -> bool:
        """
        Verifica se existe uma sessão ativa para o telefone e se não expirou
        
        Args:
            telefone (str): Número do telefone do colaborador
            
        Returns:
            bool: True se sessão ativa, False se não existe ou expirou
        """
        if telefone not in self.sessoes_ativas:
            return False
        
        sessao = self.sessoes_ativas[telefone]
        agora = time.time()
        
        if agora > sessao["expira_em"]:
            # Sessão expirada, remover
            logger.info(f"🕐 Sessão expirada para colaborador: {telefone}")
            del self.sessoes_ativas[telefone]
            return False
        
        # Atualizar última atividade
        sessao["ultima_atividade"] = agora
        logger.info(f"✅ Sessão ativa confirmada para colaborador: {telefone}")
        return True

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
        Interpreta mensagem do usuário e determina próxima ação
        
        Esta é a função CENTRAL de processamento de mensagens que:
        1. PRIMEIRO: Usa interpretador GPT para detectar intenções (saudações, menu)
        2. SEGUNDO: Se não for intenção especial, segue fluxo original
        
        Funcionalidades implementadas:
        - 🧠 Interpretador inteligente GPT detecta saudações e solicitações de menu
        - 👋 Saudações automáticas → Primeira mensagem da Bia
        - 📋 "Menu" de colaboradores → Menu de opções de atendimento
        - 📋 "Menu" de clientes → [FUTURO] Menu específico do cliente
        - 🔄 Fallback seguro → Se interpretador falhar, continua fluxo normal
        
        Args:
            remetente (str): Número do remetente
            mensagem (str): Mensagem do usuário  
            message_id (str): ID da mensagem (opcional)
            
        Returns:
            Dict: Resultado do processamento
            
        Fluxo de prioridades:
            0. Interpretador GPT (saudações, menu)
            1. Identificação de CPF
            2. Sessão IA ativa (colaboradores)
            3. Novo usuário
            4. Outras mensagens
        """
        try:
            # Marcar mensagem como lida
            if message_id:
                self.marcar_como_lida(remetente, message_id)
            
            # ====================================================================
            # PRIORIDADE 0: VERIFICAR SE É COLABORADOR EM PROCESSO DE COLETA DE DADOS
            # =========================================================================
            # IMPORTANTE: Esta verificação deve ser ANTES do interpretador GPT para evitar
            # que telefones sejam interpretados como CPF durante a coleta!
            if remetente in self.coleta_dados_cliente and self.coleta_dados_cliente[remetente]["etapa"] != "concluido":
                logger.info(f"📝 Colaborador em processo de coleta detectado: {remetente}")
                return self.processar_coleta_dados_cliente(remetente, mensagem, message_id)
            
            # ====================================================================
            # PRIORIDADE 1: INTERPRETADOR INTELIGENTE GPT
            # ====================================================================
            # Usar novo interpretador para detectar intenções antes de tudo
            try:
                logger.info("🧠 Iniciando interpretação inteligente com GPT...")
                interpretacao = self.openai_service.interpretar_intencao_mensagem(mensagem, remetente)
                
                # Se GPT detectou intenção específica com alta confiança
                if interpretacao.get("bypass_fluxo") and interpretacao.get("confianca", 0) >= 0.7:
                    logger.info(f"🎯 Intenção detectada com alta confiança: {interpretacao['intencao']}")
                    
                    # Processar a intenção detectada
                    resultado_intencao = self.processar_intencao_interpretada(remetente, interpretacao, message_id)
                    
                    # Se processamento foi bem-sucedido, retornar resultado
                    if not resultado_intencao.get("continuar_fluxo_normal"):
                        logger.info("✅ Intenção processada com sucesso, finalizando")
                        return resultado_intencao
                    
                # Se chegou aqui, continuar com fluxo original
                logger.info("🔄 Continuando com fluxo original após interpretação GPT")
                
            except Exception as e:
                logger.warning(f"⚠️ Erro no interpretador GPT, continuando fluxo normal: {e}")
                # Em caso de erro no interpretador, continuar normalmente
            
            # ====================================================================
            # FLUXO ORIGINAL PRESERVADO (SEM ALTERAÇÕES!)
            # ====================================================================
            
            # Interpretar mensagem com OpenAI (função original)
            resultado = self.openai_service.interpretar_mensagem(mensagem)
            logger.info(f"🔍 Resultado da interpretação: {resultado}")
            
            # PRIORIDADE 2: Se encontrou CPF, processar imediatamente
            if resultado.get("cpf"):
                cpf = resultado["cpf"]
                self.cpfs_temp[remetente] = cpf
                logger.info(f"✅ CPF recebido: {cpf}")
                
                # Identificar se é corretor ou cliente
                identificacao = identificar_tipo_usuario(cpf)
                logger.info(f"👤 Tipo de usuário identificado: {identificacao}")
                
                # Usar apenas a mensagem da identificação
                mensagem_resposta = identificacao['mensagem']
                
                # FLUXO DIFERENCIADO BASEADO NO TIPO DE USUÁRIO
                # =================================================
                
                if identificacao["tipo"] == "colaborador":
                    # FLUXO PARA COLABORADORES/CORRETORES
                    # -----------------------------------
                    logger.info("🏢 Usuário identificado como COLABORADOR - Enviando menu de opções")
                    
                    # 1. Enviar mensagem de boas-vindas personalizada
                    self.enviar_mensagem(remetente, mensagem_resposta)
                    
                    # 2. Aguardar 3 segundos para melhor experiência do usuário
                    import time
                    time.sleep(3)
                    
                    # 3. Enviar menu de opções de atendimento específico para corretores
                    # Este menu contém: "Usar IA para Dúvidas" e "Iniciar Fechamento Locação"
                    try:
                        resultado_menu = self.menu_service.enviar_menu_opcoes_atendimento(remetente)
                        if resultado_menu["sucesso"]:
                            logger.info("✅ Menu de opções enviado com sucesso para colaborador")
                        else:
                            logger.error(f"❌ Erro ao enviar menu: {resultado_menu.get('erro')}")
                    except Exception as e_menu:
                        logger.error(f"❌ Erro ao enviar menu de opções: {str(e_menu)}")
                        # Fallback: enviar mensagem simples se menu falhar
                        self.enviar_mensagem(remetente, "Menu de opções temporariamente indisponível. Digite sua dúvida que irei ajudar!")
                
                else:
                    # FLUXO PARA CLIENTES (MANTIDO ORIGINAL)
                    # -------------------------------------
                    logger.info("👥 Usuário identificado como CLIENTE - Mantendo fluxo original")
                    
                    # Para clientes, mantemos o comportamento original:
                    # - Enviar apenas mensagem de resposta da identificação
                    # - Fluxo normal de LGPD será tratado em outro momento/lugar
                    self.enviar_mensagem(remetente, mensagem_resposta)
                
                # FINALIZAÇÃO COMUM PARA AMBOS OS FLUXOS
                # ======================================
                
                # Adicionar tipo de usuário ao resultado para logs/debug
                resultado["tipo_usuario"] = identificacao["tipo"]
                resultado["mensagem_resposta"] = mensagem_resposta
                
                # Log final da operação
                logger.info(f"✅ Processamento completo para {identificacao['tipo']}: {remetente}")
                
                return resultado
            
            # PRIORIDADE 3: VERIFICAR SE É COLABORADOR COM SESSÃO IA ATIVA 
            # =============================================================
            if self.sessao_ativa(remetente):
                logger.info(f"🤖 Colaborador com IA Especializada ativa detectado: {remetente}")
                return self.processar_duvida_colaborador(remetente, mensagem, message_id)
            
            # PRIORIDADE 4: Se for novo usuário e NÃO tem CPF, enviar primeira mensagem
            if resultado.get("novo_usuario"):
                logger.info("👋 Novo usuário detectado")
                return self.primeira_mensagem(remetente, message_id)
            
            # PRIORIDADE 5: Outras mensagens
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

    def processar_resposta_menu_colaborador(self, remetente: str, row_id: str, webhook_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Processa respostas de menus interativos especificamente para colaboradores
        
        Esta função é chamada quando um colaborador clica em uma opção do menu
        enviado pelo sistema (ex: "Usar IA para Dúvidas", "Iniciar Fechamento Locação")
        
        Args:
            remetente (str): Número do telefone do colaborador que respondeu
            row_id (str): ID da opção selecionada no menu (ex: "usar_ia_duvidas")
            webhook_data (Dict, optional): Dados completos do webhook para contexto adicional
            
        Returns:
            Dict: Resultado do processamento com próxima ação
            
        Exemplo de uso:
            resultado = service.processar_resposta_menu_colaborador(
                "5511999999999", 
                "usar_ia_duvidas"
            )
        """
        try:
            logger.info(f"📋 Processando resposta de menu do COLABORADOR: {remetente} → {row_id}")
            
            # Usar o menu service para processar a resposta
            # O menu service contém toda a lógica de mapeamento de ações
            resultado_processamento = self.menu_service.processar_resposta_menu(
                row_id=row_id,
                usuario_id=remetente,
                webhook_data=webhook_data
            )
            
            if resultado_processamento["sucesso"]:
                # RESPOSTA PROCESSADA COM SUCESSO
                logger.info(f"✅ Ação identificada: {resultado_processamento['acao']}")
                
                # Enviar mensagem de resposta ao colaborador
                mensagem_resposta = resultado_processamento["mensagem_resposta"]
                self.enviar_mensagem(remetente, mensagem_resposta)
                
                # VERIFICAR AÇÕES ESPECIAIS DOS COLABORADORES
                # ==========================================
                
                # Ativação da IA Especializada
                if resultado_processamento["acao"] == "ativar_ia_especializada":
                    # Criar sessão ativa com timeout para este colaborador
                    agora = time.time()
                    self.sessoes_ativas[remetente] = {
                        "tipo": "ia_especializada",
                        "dados_colaborador": None,  # Será preenchido quando necessário
                        "ativado_em": agora,
                        "expira_em": agora + self.TIMEOUT_SESSAO,
                        "ultima_atividade": agora
                    }
                    logger.info(f"🤖 IA Especializada ATIVADA para colaborador: {remetente} (expira em 30min)")
                
                # Início da coleta de dados do cliente
                elif resultado_processamento["acao"] == "coletar_nome_cliente":
                    # Iniciar processo de coleta de dados do cliente
                    self.coleta_dados_cliente[remetente] = {
                        "nome": "",
                        "telefone": "",
                        "etapa": "aguardando_nome",
                        "iniciado_em": time.time()
                    }
                    logger.info(f"📝 Iniciando coleta de dados do cliente para colaborador: {remetente}")
                
                # Confirmação de atendimento do corretor (SIM)
                elif resultado_processamento["acao"] == "iniciar_atendimento_cliente":
                    logger.info(f"🚀 Iniciando atendimento com cliente para corretor: {remetente}")
                    # Verificar se temos dados da coleta para este corretor
                    if remetente in self.coleta_dados_cliente:
                        dados_cliente = self.coleta_dados_cliente[remetente]
                        logger.info(f"📋 Dados do cliente encontrados: {dados_cliente}")
                        resultado_confirmacao = self.processar_confirmacao_atendimento_sim(remetente, dados_cliente)
                        logger.info(f"✅ Resultado da confirmação: {resultado_confirmacao}")
                        # Não retornar aqui, deixar continuar o fluxo normal
                    else:
                        logger.error(f"❌ Dados de coleta não encontrados para corretor: {remetente}")
                        self.enviar_mensagem(remetente, "❌ Erro: Dados do cliente não encontrados. Inicie uma nova coleta.")
                
                # Cancelamento de atendimento do corretor (NÃO)  
                elif resultado_processamento["acao"] == "encerrar_atendimento_corretor":
                    logger.info(f"❌ Encerrando atendimento para corretor: {remetente}")
                    resultado_cancelamento = self.processar_confirmacao_atendimento_nao(remetente)
                    logger.info(f"✅ Resultado do cancelamento: {resultado_cancelamento}")
                    # Não retornar aqui, deixar continuar o fluxo normal
                
                # Cliente aceita atendimento (SIM)
                elif resultado_processamento["acao"] == "solicitar_cpf_cliente":
                    self.enviar_mensagem(remetente, "📄 *Para prosseguir, preciso do seu CPF:*\n\n(Somente números, exemplo: 12345678901)")
                    logger.info(f"📋 Solicitando CPF para cliente: {remetente}")
                
                # Cliente recusa atendimento (NÃO)
                elif resultado_processamento["acao"] == "encerrar_atendimento_cliente":
                    # Limpar dados do atendimento
                    if remetente in self.atendimentos_cliente:
                        del self.atendimentos_cliente[remetente]
                    logger.info(f"❌ Cliente recusou atendimento: {remetente}")
                
                # LOG DETALHADO PARA MANUTENÇÃO
                logger.info(f"📤 Mensagem enviada para colaborador {remetente}: {mensagem_resposta[:50]}...")
                logger.info(f"🔄 Próximo passo definido: {resultado_processamento['proximo_passo']}")
                
                return {
                    "sucesso": True,
                    "tipo_usuario": "colaborador",
                    "acao_executada": resultado_processamento["acao"],
                    "proximo_passo": resultado_processamento["proximo_passo"],
                    "mensagem_enviada": mensagem_resposta,
                    "row_id_processado": row_id,
                    "ia_especializada_ativa": resultado_processamento["acao"] == "ativar_ia_especializada"
                }
                
            else:
                # ERRO NO PROCESSAMENTO DA RESPOSTA
                logger.warning(f"⚠️ Opção não reconhecida pelo colaborador: {row_id}")
                
                # Enviar mensagem de erro amigável
                mensagem_erro = resultado_processamento.get("mensagem_resposta", 
                    "Não consegui processar sua escolha. Pode tentar novamente?")
                self.enviar_mensagem(remetente, mensagem_erro)
                
                return {
                    "sucesso": False,
                    "tipo_usuario": "colaborador", 
                    "erro": resultado_processamento.get("erro"),
                    "row_id_nao_reconhecido": row_id,
                    "mensagem_erro_enviada": mensagem_erro
                }
                
        except Exception as e:
            # TRATAMENTO DE ERRO CRÍTICO
            logger.error(f"❌ Erro crítico ao processar resposta de menu do colaborador: {str(e)}")
            logger.error(f"❌ Dados: remetente={remetente}, row_id={row_id}")
            
            # Enviar mensagem de erro técnico
            mensagem_erro_tecnico = "Tive um problema técnico ao processar sua escolha. Nossa equipe foi notificada."
            self.enviar_mensagem(remetente, mensagem_erro_tecnico)
            
            return {
                "sucesso": False,
                "tipo_usuario": "colaborador",
                "erro_critico": str(e),
                "row_id": row_id,
                "remetente": remetente,
                "mensagem_erro_enviada": mensagem_erro_tecnico
            }

    def processar_coleta_dados_cliente(self, remetente: str, mensagem: str, message_id: str = None) -> Dict[str, Any]:
        """
        Processa coleta de dados do cliente durante processo de fechamento
        
        Esta função é chamada quando um colaborador está em processo de coleta
        de dados (nome e telefone) de um cliente para fechamento de locação.
        
        Funcionalidades:
        - Valida dados usando GPT
        - Permite interrupções limitadas (menu explícito, dúvidas com palavras interrogativas)
        - Controla etapas da coleta (nome → telefone → concluído)
        - Finaliza quando todos os dados são coletados
        - Evita falsos positivos (nomes não são tratados como dúvidas)
        
        Args:
            remetente (str): Número do telefone do colaborador
            mensagem (str): Resposta do colaborador
            message_id (str): ID da mensagem (opcional)
            
        Returns:
            Dict: Resultado do processamento da coleta
        """
        try:
            # Marcar mensagem como lida
            if message_id:
                self.marcar_como_lida(remetente, message_id)
            
            # Obter dados da coleta em andamento
            dados_coleta = self.coleta_dados_cliente[remetente]
            etapa_atual = dados_coleta["etapa"]
            
            logger.info(f"📝 Processando coleta - Etapa: {etapa_atual}, Mensagem: {mensagem[:50]}...")
            
            # ====================================================================
            # VERIFICAR INTERRUPÇÕES (MENU OU DÚVIDAS EXPLÍCITAS)
            # ====================================================================
            # 
            # Durante a coleta, permitimos apenas interrupções CLARAS:
            # - Menu: palavras como "menu", "opções" com alta confiança
            # - Dúvidas: apenas perguntas EXPLÍCITAS com "?", "como", "o que", etc.
            # 
            # IMPORTANTE: "conversa_normal" NÃO é mais tratada como dúvida!
            # Isso evita que nomes como "Andreia Robe" sejam interpretados como dúvidas.
            
            # Usar interpretador GPT para verificar se é menu ou dúvida
            try:
                interpretacao = self.openai_service.interpretar_intencao_mensagem(mensagem, remetente)
                
                # Se solicitou menu
                if interpretacao.get("intencao") == "menu" and interpretacao.get("confianca", 0) >= 0.7:
                    logger.info(f"📋 Menu solicitado durante coleta por colaborador: {remetente}")
                    resultado_menu = self.menu_service.enviar_menu_opcoes_atendimento(remetente)
                    return {
                        "sucesso": True,
                        "interrupcao": "menu_enviado",
                        "coleta_pausada": True,
                        "etapa_atual": etapa_atual,
                        "mensagem_resposta": "Menu enviado. Digite novamente o dado solicitado para continuar a coleta."
                    }
                
                # Se fez pergunta/dúvida EXPLÍCITA (apenas dúvidas técnicas claras)
                elif interpretacao.get("intencao") == "duvida_tecnica" and interpretacao.get("confianca", 0) >= 0.7:
                    # Verificar se realmente parece uma pergunta (contém palavras interrogativas)
                    palavras_pergunta = ["como", "o que", "qual", "quando", "onde", "por que", "porque", "?", "ajuda", "dúvida", "duvida"]
                    mensagem_lower = mensagem.lower()
                    
                    # Só tratar como dúvida se contiver palavras interrogativas claras
                    if any(palavra in mensagem_lower for palavra in palavras_pergunta):
                        logger.info(f"❓ Dúvida técnica explícita detectada durante coleta: {remetente}")
                        # Ativar IA especializada temporariamente
                        agora = time.time()
                        self.sessoes_ativas[remetente] = {
                            "tipo": "ia_especializada",
                            "dados_colaborador": None,
                            "ativado_em": agora,
                            "expira_em": agora + self.TIMEOUT_SESSAO,
                            "ultima_atividade": agora
                        }
                        self.enviar_mensagem(remetente, "🤖 IA Especializada Ativada!")
                        return self.processar_duvida_colaborador(remetente, mensagem, message_id)
                    else:
                        logger.info(f"📝 Dúvida técnica detectada, mas sem palavras interrogativas - continuando coleta")
                        # Continuar com validação normal se não for pergunta clara
                    
            except Exception as e:
                logger.warning(f"⚠️ Erro na interpretação durante coleta: {e}")
                # Continuar com validação normal se interpretador falhar
            
            # ====================================================================
            # PROCESSAR DADOS BASEADO NA ETAPA ATUAL
            # ====================================================================
            
            if etapa_atual == "aguardando_nome":
                # Validar nome do cliente
                logger.info(f"👤 Validando nome do cliente: {mensagem}")
                validacao = self.openai_service.validar_dado_cliente("nome", mensagem)
                
                if validacao["valido"]:
                    # Nome válido - salvar e solicitar telefone
                    dados_coleta["nome"] = validacao.get("valor_corrigido", mensagem)
                    dados_coleta["etapa"] = "aguardando_telefone"
                    
                    mensagem_resposta = f"""✅ Nome registrado: *{dados_coleta['nome']}*

📞 Agora informe o telefone do cliente:
(Exemplo: 11999999999 ou (11) 99999-9999)"""
                    
                    self.enviar_mensagem(remetente, mensagem_resposta)
                    
                    logger.info(f"✅ Nome válido coletado: {dados_coleta['nome']}")
                    return {
                        "sucesso": True,
                        "etapa_concluida": "nome",
                        "proxima_etapa": "telefone",
                        "nome_coletado": dados_coleta['nome']
                    }
                
                else:
                    # Nome inválido - solicitar novamente
                    motivo = validacao.get("motivo_erro", "Nome não parece válido")
                    sugestao = validacao.get("sugestao", "Tente novamente")
                    
                    mensagem_erro = f"""❌ {motivo}

💡 {sugestao}

*Por favor, informe o nome completo do cliente:*"""
                    
                    self.enviar_mensagem(remetente, mensagem_erro)
                    
                    logger.warning(f"❌ Nome inválido rejeitado: {mensagem}")
                    return {
                        "sucesso": False,
                        "erro": "nome_invalido",
                        "motivo": motivo,
                        "etapa_atual": "aguardando_nome"
                    }
            
            elif etapa_atual == "aguardando_telefone":
                # Validar telefone do cliente
                logger.info(f"📞 Validando telefone do cliente: {mensagem}")
                validacao = self.openai_service.validar_dado_cliente("telefone", mensagem)
                
                if validacao["valido"]:
                    # Telefone válido - finalizar coleta
                    dados_coleta["telefone"] = validacao.get("valor_corrigido", mensagem)
                    dados_coleta["etapa"] = "concluido"
                    dados_coleta["concluido_em"] = time.time()
                    
                    mensagem_final = f"""✅ *Dados do cliente coletados com sucesso!*

👤 *Nome:* {dados_coleta['nome']}
📞 *Telefone:* {dados_coleta['telefone']}"""
                    
                    self.enviar_mensagem(remetente, mensagem_final)
                    
                    # Aguardar um momento e enviar menu de confirmação
                    time.sleep(2)
                    
                    # Enviar menu de confirmação personalizado
                    resultado_menu = self.menu_service.enviar_menu_confirmacao_atendimento(
                        remetente, 
                        dados_coleta['nome']
                    )
                    
                    if resultado_menu.get("sucesso"):
                        logger.info(f"✅ Menu de confirmação enviado para corretor {remetente}")
                    else:
                        logger.warning(f"⚠️ Falha ao enviar menu, enviando pergunta simples")
                        self.enviar_mensagem(remetente, "🚀 Posso seguir com o Atendimento ao Cliente? (Responda Sim ou Não)")
                    
                    logger.info(f"🎉 Coleta concluída para colaborador {remetente}")
                    logger.info(f"📋 Dados coletados: Nome={dados_coleta['nome']}, Tel={dados_coleta['telefone']}")
                    
                    return {
                        "sucesso": True,
                        "coleta_concluida": True,
                        "dados_cliente": {
                            "nome": dados_coleta['nome'],
                            "telefone": dados_coleta['telefone']
                        },
                        "colaborador": remetente,
                        "tempo_coleta": dados_coleta['concluido_em'] - dados_coleta['iniciado_em'],
                        "menu_confirmacao_enviado": resultado_menu.get("sucesso", False)
                    }
                
                else:
                    # Telefone inválido - solicitar novamente
                    motivo = validacao.get("motivo_erro", "Telefone não parece válido")
                    sugestao = validacao.get("sugestao", "Tente novamente")
                    
                    mensagem_erro = f"""❌ {motivo}

💡 {sugestao}

*Por favor, informe o telefone do cliente:*
(Exemplo: 11999999999 ou (11) 99999-9999)"""
                    
                    self.enviar_mensagem(remetente, mensagem_erro)
                    
                    logger.warning(f"❌ Telefone inválido rejeitado: {mensagem}")
                    return {
                        "sucesso": False,
                        "erro": "telefone_invalido",
                        "motivo": motivo,
                        "etapa_atual": "aguardando_telefone"
                    }
            
            else:
                # Etapa não reconhecida
                logger.error(f"❌ Etapa de coleta não reconhecida: {etapa_atual}")
                return {
                    "sucesso": False,
                    "erro": "etapa_invalida",
                    "etapa_atual": etapa_atual
                }
                
        except Exception as e:
            logger.error(f"❌ Erro ao processar coleta de dados: {str(e)}")
            # Enviar mensagem de erro
            self.enviar_mensagem(remetente, "❌ Erro técnico na coleta. Tente novamente.")
            return {
                "sucesso": False,
                "erro_critico": str(e),
                "etapa_atual": dados_coleta.get("etapa", "desconhecida")
            }

    def processar_duvida_colaborador(self, remetente: str, duvida: str, message_id: str = None) -> Dict[str, Any]:
        """
        Processa dúvidas de colaboradores quando a IA especializada está ativa
        
        Esta função é chamada quando um colaborador tem a IA especializada ativada
        e envia uma pergunta relacionada a processos de locação.
        
        Args:
            remetente (str): Número do telefone do colaborador
            duvida (str): Pergunta/dúvida do colaborador
            message_id (str): ID da mensagem (opcional)
            
        Returns:
            Dict: Resultado do processamento da dúvida
        """
        try:
            # Marcar mensagem como lida
            if message_id:
                self.marcar_como_lida(remetente, message_id)
            
            logger.info(f"🤖 Processando dúvida de colaborador: {remetente}")
            logger.info(f"💭 Dúvida: {duvida[:100]}...")
            
            # Obter dados do colaborador se disponível
            contexto_colaborador = self.sessoes_ativas[remetente].get("dados_colaborador")
            
            # Usar o OpenAI Service para processar a dúvida
            resultado_ia = self.openai_service.responder_duvida_locacao(
                duvida=duvida,
                contexto_colaborador=contexto_colaborador
            )
            
            if resultado_ia["sucesso"]:
                # RESPOSTA DA IA GERADA COM SUCESSO
                resposta_formatada = f"""🤖 *IA Especializada Responde:*

{resultado_ia['resposta']}

📊 *Categoria:* {resultado_ia['categoria'].title()}
🎯 *Confiança:* {resultado_ia['confianca'].title()}"""
                
                # Adicionar sugestões extras se existirem
                if resultado_ia.get('sugestoes_extras') and len(resultado_ia['sugestoes_extras']) > 0:
                    resposta_formatada += "\n\n💡 *Sugestões adicionais:*"
                    for i, sugestao in enumerate(resultado_ia['sugestoes_extras'], 1):
                        resposta_formatada += f"\n{i}. {sugestao}"
                
                # Adicionar instrução para continuar
                resposta_formatada += "\n\n❓ *Posso esclarecer mais alguma dúvida sobre locação?*"
                
                # Enviar resposta ao colaborador
                self.enviar_mensagem(remetente, resposta_formatada)
                
                # Atualizar última interação na sessão
                if remetente in self.sessoes_ativas:
                    self.sessoes_ativas[remetente]["ultima_interacao"] = duvida
                
                # LOGS DETALHADOS
                logger.info(f"✅ Dúvida processada com sucesso - Categoria: {resultado_ia['categoria']}")
                logger.info(f"📤 Resposta enviada para colaborador: {remetente}")
                
                return {
                    "sucesso": True,
                    "tipo_resposta": "ia_especializada",
                    "categoria_duvida": resultado_ia['categoria'],
                    "confianca": resultado_ia['confianca'],
                    "resposta_enviada": resposta_formatada,
                    "sugestoes_enviadas": len(resultado_ia.get('sugestoes_extras', [])),
                    "colaborador": resultado_ia.get('colaborador'),
                    "setor": resultado_ia.get('setor')
                }
                
            else:
                # ERRO NO PROCESSAMENTO DA IA
                logger.error(f"❌ Erro na IA especializada: {resultado_ia.get('erro')}")
                
                # Enviar mensagem de erro amigável
                mensagem_erro = f"""🤖 Desculpe, tive dificuldade para processar sua dúvida.

{resultado_ia['resposta']}

💡 Você pode:
• Reformular a pergunta de forma mais específica
• Perguntar sobre temas como: documentos, contratos, processos
• Tentar novamente em alguns instantes

❓ Como posso ajudar você?"""
                
                self.enviar_mensagem(remetente, mensagem_erro)
                
                return {
                    "sucesso": False,
                    "tipo_resposta": "ia_especializada_erro",
                    "erro": resultado_ia.get('erro'),
                    "mensagem_erro_enviada": mensagem_erro,
                    "duvida_original": duvida[:100]
                }
                
        except Exception as e:
            # ERRO CRÍTICO NO PROCESSAMENTO
            logger.error(f"❌ Erro crítico ao processar dúvida do colaborador: {str(e)}")
            
            # Enviar mensagem de erro técnico
            mensagem_erro_critico = """🤖 Tive um problema técnico ao processar sua dúvida.

Nossa equipe foi notificada e está resolvendo.

💡 Enquanto isso, você pode:
• Tentar reformular a pergunta
• Aguardar alguns minutos e tentar novamente
• Entrar em contato com suporte técnico

Peço desculpas pelo inconveniente! 🙏"""
            
            self.enviar_mensagem(remetente, mensagem_erro_critico)
            
            return {
                "sucesso": False,
                "tipo_resposta": "erro_critico",
                "erro_critico": str(e),
                "mensagem_erro_enviada": mensagem_erro_critico,
                "duvida_original": duvida,
                "remetente": remetente
            }

    def processar_confirmacao_atendimento_sim(self, corretor: str, dados_cliente: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa confirmação SIM do corretor para iniciar atendimento com cliente
        
        Args:
            corretor (str): Telefone do corretor
            dados_cliente (Dict): Dados coletados do cliente (nome, telefone)
            
        Returns:
            Dict: Resultado do processamento
        """
        try:
            # Obter dados do corretor se disponível
            corretor_nome = "Corretor da Toca Imóveis"  # Padrão se não encontrar
            
            # Tentar obter nome do corretor do banco de dados
            try:
                from .buscar_usuarios_supabase import identificar_tipo_usuario
                # TODO: Implementar busca específica do nome do corretor
                # Por enquanto, usar nome padrão mais profissional
                logger.info(f"📋 Usando nome padrão para corretor: {corretor_nome}")
            except Exception as e:
                logger.warning(f"⚠️ Não foi possível obter nome do corretor: {e}")
            
            # Converter telefone do cliente para formato para verificação
            telefone_cliente = dados_cliente.get('telefone', '')
            
            # Limpar telefone (remover parênteses, hífens, espaços)
            telefone_limpo = ''.join(filter(str.isdigit, telefone_cliente))
            
            logger.info(f"🔍 Verificando se cliente {dados_cliente['nome']} tem WhatsApp: {telefone_limpo}")
            
            # Verificar se o cliente tem WhatsApp
            verificacao = self.verificar_numero_tem_whatsapp(telefone_limpo)
            
            if not verificacao.get("sucesso"):
                # Erro na verificação
                self.enviar_mensagem(corretor, f"❌ Erro ao verificar WhatsApp do cliente. Tente novamente.")
                return {"sucesso": False, "erro": "erro_verificacao_whatsapp"}
            
            if not verificacao.get("existe"):
                # Cliente não tem WhatsApp
                mensagem_erro = f"""❌ *Cliente não possui WhatsApp ativo*

👤 *Nome:* {dados_cliente['nome']}
📞 *Telefone:* {telefone_cliente}

💡 *Sugestões:*
• Confirme se o número está correto
• Entre em contato por outro meio
• Solicite o WhatsApp atualizado do cliente"""
                
                self.enviar_mensagem(corretor, mensagem_erro)
                logger.warning(f"❌ Cliente sem WhatsApp: {telefone_limpo}")
                return {"sucesso": False, "erro": "cliente_sem_whatsapp"}
            
            # Cliente TEM WhatsApp - prosseguir
            logger.info(f"✅ Cliente tem WhatsApp, iniciando contato: {telefone_limpo}")
            
            # Salvar dados do atendimento
            self.atendimentos_cliente[corretor] = {
                "cliente_nome": dados_cliente['nome'],
                "cliente_telefone": verificacao["numero"],  # Número formatado da API
                "corretor_nome": corretor_nome,
                "status": "aguardando_confirmacao_cliente",
                "iniciado_em": time.time()
            }
            
            # Enviar mensagem inicial para o cliente
            mensagem_cliente = f"""🏠 *Olá {dados_cliente['nome']}!*

Sou a Bia, assistente virtual da *Toca Imóveis*.

O corretor *{corretor_nome}* solicitou iniciar o processo de *fechamento de locação* com você.

Deseja prosseguir com o atendimento?"""
            
            # Enviar mensagem ao cliente
            resultado_msg = self.enviar_mensagem(verificacao["numero"], mensagem_cliente)
            
            if resultado_msg.get("sucesso"):
                # Aguardar um momento e enviar menu de confirmação
                time.sleep(3)
                
                # Enviar menu de confirmação ao cliente
                resultado_menu = self.menu_service.enviar_menu_confirmacao_cliente(
                    verificacao["numero"], 
                    corretor_nome
                )
                
                if resultado_menu.get("sucesso"):
                    # Confirmar ao corretor
                    confirmacao_corretor = f"""✅ *Contato iniciado com sucesso!*

👤 *Cliente:* {dados_cliente['nome']}
📞 *WhatsApp:* {telefone_cliente}

🚀 *Mensagem enviada ao cliente aguardando resposta...*

📋 *Status:* Aguardando confirmação do cliente"""
                    
                    self.enviar_mensagem(corretor, confirmacao_corretor)
                    
                    # Limpar dados da coleta (já processados)
                    if corretor in self.coleta_dados_cliente:
                        del self.coleta_dados_cliente[corretor]
                    
                    logger.info(f"✅ Atendimento iniciado: {corretor} → {dados_cliente['nome']}")
                    
                    return {
                        "sucesso": True,
                        "acao": "atendimento_iniciado",
                        "cliente_contatado": True,
                        "menu_enviado": True,
                        "dados_atendimento": self.atendimentos_cliente[corretor]
                    }
                
                else:
                    # Falha no menu - usar mensagem simples
                    logger.warning(f"⚠️ Falha no menu do cliente, enviando pergunta simples")
                    self.enviar_mensagem(verificacao["numero"], 
                        "Por favor, responda: Deseja prosseguir com o atendimento?\n\n✅ Digite *Sim* para continuar\n❌ Digite *Não* para cancelar")
                    
                    # Confirmar ao corretor mesmo assim
                    self.enviar_mensagem(corretor, "✅ Cliente contatado! Aguardando resposta...")
                    return {"sucesso": True, "acao": "atendimento_iniciado", "menu_enviado": False}
            
            else:
                # Falha ao enviar mensagem
                self.enviar_mensagem(corretor, f"❌ Erro ao enviar mensagem para o cliente. Verifique o número.")
                return {"sucesso": False, "erro": "falha_envio_mensagem"}
                
        except Exception as e:
            logger.error(f"❌ Erro ao processar confirmação SIM: {str(e)}")
            self.enviar_mensagem(corretor, "❌ Erro técnico. Nossa equipe foi notificada.")
            return {"sucesso": False, "erro_critico": str(e)}

    def processar_confirmacao_atendimento_nao(self, corretor: str) -> Dict[str, Any]:
        """
        Processa confirmação NÃO do corretor (cancelar atendimento)
        
        Args:
            corretor (str): Telefone do corretor
            
        Returns:
            Dict: Resultado do processamento
        """
        try:
            logger.info(f"❌ Corretor cancelou atendimento: {corretor}")
            
            # Limpar dados da coleta se existir
            if corretor in self.coleta_dados_cliente:
                dados_cliente = self.coleta_dados_cliente[corretor]
                logger.info(f"🗑️ Limpando dados da coleta: {dados_cliente['nome']}")
                del self.coleta_dados_cliente[corretor]
            
            # Limpar sessão IA se ativa
            if corretor in self.sessoes_ativas:
                logger.info(f"🗑️ Encerrando sessão IA do corretor: {corretor}")
                del self.sessoes_ativas[corretor]
            
            # Log da operação
            logger.info(f"✅ Atendimento encerrado e dados limpos para: {corretor}")
            
            return {
                "sucesso": True,
                "acao": "atendimento_cancelado",
                "dados_limpos": True,
                "sessao_encerrada": True
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar cancelamento: {str(e)}")
            return {"sucesso": False, "erro_critico": str(e)} 
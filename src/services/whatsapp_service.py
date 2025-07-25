import os
import re
from typing import Dict, Any, Optional
import logging
from .openai_service import OpenAIService
from .buscar_usuarios_supabase import identificar_tipo_usuario
from .menu_service_whatsapp import MenuServiceWhatsApp
from .whatsapp_api import WhatsAppAPI
from .session_manager import SessionManager
import time
import requests
from datetime import datetime

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
    DATA: JUlho/2025
    """
    
    def __init__(self):
        # MODULARIZAÇÃO: Inicializar módulos especializados
        # =================================================
        
        # Módulo de comunicação com WhatsApp API
        self.whatsapp_api = WhatsAppAPI()
        
        # Módulo de gestão de sessões ativas
        self.session_manager = SessionManager(timeout_sessao=30 * 60)  # 30 minutos
        
        # Inicializar OpenAI Service
        self.openai_service = OpenAIService()
        
        # Inicializar Menu Service para WhatsApp
        # Este serviço gerencia menus interativos enviados aos usuários
        self.menu_service = MenuServiceWhatsApp()
        
        # NOVO: Serviço de deduplicação de mensagens
        from .message_deduplication_service import MessageDeduplicationService
        self.dedup_service = MessageDeduplicationService()
        
        # NOVO: ConversationLogger para captura de conversas (OPCIONAL)
        # =============================================================
        try:
            from .conversation_logger import ConversationLogger
            self.conversation_logger = ConversationLogger()
            self.logging_enabled = True
            logger.info("🗂️ ConversationLogger ativado")
        except Exception as e:
            self.conversation_logger = None
            self.logging_enabled = False
            logger.warning(f"⚠️ ConversationLogger não disponível: {e}")
        
        # NOVO: Serviços de Consentimento e Coleta Expandida (OPCIONAL)
        # =============================================================
        try:
            from .consentimento_service import ConsentimentoService
            self.consentimento_service = ConsentimentoService()
            logger.info("✅ ConsentimentoService inicializado")
        except Exception as e:
            self.consentimento_service = None
            logger.warning(f"⚠️ ConsentimentoService não disponível: {e}")
        
        try:
            from .coleta_dados_service import ColetaDadosService
            self.coleta_dados_service = ColetaDadosService()
            logger.info("✅ ColetaDadosService inicializado")
        except Exception as e:
            self.coleta_dados_service = None
            logger.warning(f"⚠️ ColetaDadosService não disponível: {e}")
        
        # FLAG de controle para ativar/desativar novo fluxo (SEM QUEBRAR NADA)
        self.fluxo_expandido_ativo = True
        
        # COMPATIBILIDADE: Manter referências diretas para não quebrar código existente
        # ============================================================================
        # Note: As propriedades @property são definidas na classe, não no __init__
        
        # Sistema de coleta de dados do cliente para fechamento
        # Formato: {telefone_colaborador: {"nome": "", "telefone": "", "etapa": "aguardando_nome|aguardando_telefone|concluido"}}
        self.coleta_dados_cliente = {}
        
        # Sistema de atendimentos iniciados com clientes
        # Formato: {telefone_corretor: {"cliente_nome": "", "cliente_telefone": "", "corretor_nome": "", "status": "..."}}
        self.atendimentos_cliente = {}
        
        logger.info(f"WhatsApp Service inicializado com arquitetura modular")
        logger.info("🔧 Módulos ativos: WhatsAppAPI + SessionManager + MenuService")
        logger.info("✅ Compatibilidade mantida - todas as funcionalidades preservadas")
        
        self.company_name = os.getenv('COMPANY_NAME', 'Locação Online')

    # PROPRIEDADES DE COMPATIBILIDADE
    # ================================
    # Estas propriedades redirecionam para os módulos apropriados
    # mantendo a compatibilidade com código existente
    
    @property
    def sessoes_ativas(self):
        """Redireciona para SessionManager.sessoes_ativas (compatibilidade)"""
        return self.session_manager.sessoes_ativas
    
    @property  
    def TIMEOUT_SESSAO(self):
        """Redireciona para SessionManager.TIMEOUT_SESSAO (compatibilidade)"""
        return self.session_manager.TIMEOUT_SESSAO

    def verificar_numero_tem_whatsapp(self, numero_telefone: str) -> Dict[str, Any]:
        """
        Verifica se um número de telefone possui WhatsApp ativo
        
        MODULARIZADO: Esta função agora usa WhatsAppAPI
        
        Args:
            numero_telefone (str): Número no formato brasileiro (ex: 5511999999999)
            
        Returns:
            Dict: {"existe": bool, "numero": str, "sucesso": bool}
        """
        # Redirecionar para o módulo WhatsAppAPI
        return self.whatsapp_api.verificar_numero_tem_whatsapp(numero_telefone)
        
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
        Identificação rápida do tipo de usuário baseada em cache
        """
        try:
            # Cache simples para evitar consultas repetidas
            if not hasattr(self, '_cache_tipos_usuario'):
                self._cache_tipos_usuario = {}
            
            if remetente in self._cache_tipos_usuario:
                return self._cache_tipos_usuario[remetente]
            
            # Verificar se é colaborador (busca por CPF conhecido)
            # Esta é uma verificação simplificada - pode ser expandida
            resultado = "cliente"  # Default
            
            # Cache do resultado
            self._cache_tipos_usuario[remetente] = resultado
            return resultado
            
        except Exception as e:
            logger.error(f"❌ Erro na identificação rápida: {e}")
            return "cliente"  # Default seguro

    def _identificar_tipo_remetente(self, remetente: str, conversation_id: str) -> tuple:
        """
        ✅ VERSÃO MELHORADA: Identifica corretor/cliente por telefone principal e relacionados
        
        Args:
            remetente (str): Número do telefone do remetente
            conversation_id (str): ID da conversa ativa
            
        Returns:
            tuple: (sender_type, receiver_type, phase)
        """
        try:
            # 🎯 CONTEXTO ESPECÍFICO: Se está em coleta expandida, sempre é cliente
            if (self.fluxo_expandido_ativo and self.coleta_dados_service and 
                self.coleta_dados_service.obter_dados_sessao(remetente)):
                return ("cliente", "ia", "ia_cliente")
            
            # 1. Buscar dados da conversa ativa
            if hasattr(self.conversation_logger, 'active_conversations') and conversation_id:
                conversation = self.conversation_logger.active_conversations.get(conversation_id)
                
                # ✅ VALIDAÇÃO ROBUSTA para evitar erro NoneType
                if (conversation and isinstance(conversation, dict) and 
                    "conversation_info" in conversation):
                    
                    conv_info = conversation.get("conversation_info", {})
                    participants = conversation.get("participants", {})
                    
                    # ✅ NOVO: Verificar telefone principal (corretor)
                    phone_principal = conv_info.get("phone_number")
                    if phone_principal and remetente == phone_principal:
                        return ("corretor", "ia", "ia_corretor")
                    
                    # ✅ NOVO: Verificar telefones relacionados (cliente)
                    related_phones = conv_info.get("related_phones", [])
                    if remetente in related_phones:
                        return ("cliente", "ia", "ia_cliente")
                    
                    # 2. Fallback: Verificar dados dos participantes
                    broker_data = participants.get("broker")
                    if broker_data and isinstance(broker_data, dict):
                        broker_phone = broker_data.get("phone")
                        if broker_phone and remetente == broker_phone:
                            return ("corretor", "ia", "ia_corretor")
                    
                    client_data = participants.get("client")
                    if client_data and isinstance(client_data, dict):
                        client_phone = client_data.get("phone")
                        if client_phone and remetente == client_phone:
                            return ("cliente", "ia", "ia_cliente")
            
            # 3. Fallback: verificar atendimentos ativos
            if hasattr(self, 'atendimentos_cliente'):
                for corretor_tel, dados in self.atendimentos_cliente.items():
                    if remetente == corretor_tel:
                        return ("corretor", "ia", "ia_corretor")
                    elif remetente == dados.get("cliente_telefone"):
                        return ("cliente", "ia", "ia_cliente")
            
            # 4. Default inteligente - para coleta expandida, prefere cliente
            if (self.fluxo_expandido_ativo and self.coleta_dados_service):
                return ("cliente", "ia", "ia_cliente")
            
            # 5. Default original para manter compatibilidade
            return ("corretor", "ia", "ia_corretor")
            
        except Exception as e:
            logger.warning(f"⚠️ Erro na identificação de remetente: {e}")
            # Fallback ultra-seguro - prefere cliente para coleta expandida
            if (self.fluxo_expandido_ativo and self.coleta_dados_service):
                return ("cliente", "ia", "ia_cliente")
            return ("corretor", "ia", "ia_corretor")

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
        
        MODULARIZADO: Esta função agora usa SessionManager
        
        Args:
            telefone (str): Número do telefone do colaborador
            
        Returns:
            bool: True se sessão ativa, False se não existe ou expirou
        """
        # Redirecionar para o módulo SessionManager
        return self.session_manager.sessao_ativa(telefone)

    def enviar_mensagem(self, numero_telefone: str, mensagem: str) -> Dict[str, Any]:
        """
        Envia mensagem via WhatsApp API e captura para logging
        
        Se a mensagem for duplicada, apenas retorna sucesso sem enviar,
        permitindo que o fluxo continue para a próxima mensagem.
        """
        try:
            # Verificar duplicação com contexto da conversa
            context = None
            if self.logging_enabled and self.conversation_logger:
                conv_id = self.conversation_logger.get_active_conversation_id(numero_telefone)
                if conv_id and conv_id in self.conversation_logger.active_conversations:
                    conv_data = self.conversation_logger.active_conversations[conv_id]
                    context = {
                        "phase": conv_data.get("conversation_info", {}).get("current_phase", "unknown"),
                        "conversation_id": conv_id
                    }
            
            # Verificar duplicação
            is_duplicate = hasattr(self, 'dedup_service') and self.dedup_service.is_duplicate(mensagem, numero_telefone, context)
            
            if is_duplicate:
                # Se for duplicada, apenas loga e retorna sucesso para continuar o fluxo
                logger.info(f"🔄 Mensagem duplicada ignorada para: {numero_telefone} - Continuando fluxo")
                return {
                    "sucesso": True,
                    "duplicada": True,
                    "mensagem": mensagem,
                    "continuar_fluxo": True
                }
            
            # Se não for duplicada, envia normalmente
            resultado = self.whatsapp_api.enviar_mensagem(numero_telefone, mensagem)
            
            # NOVO: Capturar mensagem se for resposta para cliente
            if self.logging_enabled and self.conversation_logger:
                # Verificar se é mensagem para cliente em atendimento
                corretor = self._obter_corretor_da_sessao(numero_telefone)
                if corretor:
                    # É uma mensagem para cliente
                    conv_id = self.conversation_logger.get_active_conversation_id(corretor)
                    if conv_id:
                        self.conversation_logger.add_message_enhanced(
                            conv_id,
                            "ia",
                            "cliente",
                            mensagem,
                            "ia_cliente"
                        )
            
            return resultado
                
        except Exception as e:
            logger.error(f"❌ Erro ao enviar mensagem: {str(e)}")
            return {"sucesso": False, "erro": str(e)}
    
    def marcar_como_lida(self, numero_telefone: str, message_id: str) -> Dict[str, Any]:
        """
        Marca uma mensagem como lida
        
        MODULARIZADO: Esta função agora usa WhatsAppAPI
        
        Args:
            numero_telefone (str): Número do telefone
            message_id (str): ID da mensagem
            
        Returns:
            Dict: Resposta da API
        """
        # Redirecionar para o módulo WhatsAppAPI
        return self.whatsapp_api.marcar_como_lida(numero_telefone, message_id)
    
    def processar_webhook_mensagem(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa dados do webhook de mensagem recebida (Formato W-API)
        MODULARIZADO: Esta função agora usa WhatsAppAPI
        """
        # NOVO: Interceptar recebimento de PDF ou imagem para baixar e avançar sequência de coleta
        try:
            msgContent = webhook_data.get("msgContent", {})
            remetente = webhook_data.get("sender", {}).get("id") or webhook_data.get("chat", {}).get("id")
            doc = msgContent.get("documentMessage")
            img = msgContent.get("imageMessage") if "imageMessage" in msgContent else None
            if doc and doc.get("mimetype") == "application/pdf":
                logger.info(f"📥 Documento PDF recebido de {remetente}")
                # Baixar e salvar documento antes de avançar
                try:
                    indice = None
                    if hasattr(self, '_controle_coleta_documentos') and remetente in self._controle_coleta_documentos:
                        indice = self._controle_coleta_documentos[remetente]['indice_atual'] + 1
                    self.baixar_e_salvar_documento(
                        media_key=doc["mediaKey"],
                        direct_path=doc["directPath"],
                        tipo="document",
                        mimetype=doc["mimetype"],
                        file_name=doc.get("fileName", "documento.pdf"),
                        remetente=remetente,
                        indice=indice
                    )
                    
                    # ✅ NOVO: Registrar mensagem de documento no ConversationLogger
                    if self.logging_enabled and self.conversation_logger:
                        try:
                            conv_id = self.conversation_logger.obter_conversa_ativa_por_telefone(remetente)
                            if conv_id:
                                self.conversation_logger.log_message(
                                    conversation_id=conv_id,
                                    sender=remetente,
                                    receiver=self.numero_whatsapp,
                                    content=f"📄 Documento enviado: {doc.get('fileName', 'documento.pdf')}",
                                    message_type="document",
                                    timestamp=datetime.now().isoformat(),
                                    metadata={
                                        "file_name": doc.get("fileName", "documento.pdf"),
                                        "mimetype": doc["mimetype"],
                                        "media_key": doc["mediaKey"],
                                        "document_type": "pdf"
                                    }
                                )
                                logger.info(f"✅ Mensagem de documento registrada no ConversationLogger: {doc.get('fileName', 'documento.pdf')}")
                        except Exception as e:
                            logger.error(f"❌ Erro ao registrar mensagem de documento no ConversationLogger: {e}")
                    
                except Exception as e:
                    logger.error(f"❌ Erro ao baixar/salvar documento: {e}")
                self._avancar_coleta_documentos(remetente)
            elif img:
                logger.info(f"📥 Imagem recebida de {remetente}")
                try:
                    indice = None
                    if hasattr(self, '_controle_coleta_documentos') and remetente in self._controle_coleta_documentos:
                        indice = self._controle_coleta_documentos[remetente]['indice_atual'] + 1
                    self.baixar_e_salvar_documento(
                        media_key=img["mediaKey"],
                        direct_path=img["directPath"],
                        tipo="image",
                        mimetype=img.get("mimetype", "image/jpeg"),
                        file_name=img.get("fileName", "imagem.jpg"),
                        remetente=remetente,
                        indice=indice
                    )
                    
                    # ✅ NOVO: Registrar mensagem de imagem no ConversationLogger
                    if self.logging_enabled and self.conversation_logger:
                        try:
                            conv_id = self.conversation_logger.obter_conversa_ativa_por_telefone(remetente)
                            if conv_id:
                                self.conversation_logger.log_message(
                                    conversation_id=conv_id,
                                    sender=remetente,
                                    receiver=self.numero_whatsapp,
                                    content=f"📷 Imagem enviada: {img.get('fileName', 'imagem.jpg')}",
                                    message_type="image",
                                    timestamp=datetime.now().isoformat(),
                                    metadata={
                                        "file_name": img.get("fileName", "imagem.jpg"),
                                        "mimetype": img.get("mimetype", "image/jpeg"),
                                        "media_key": img["mediaKey"],
                                        "document_type": "image"
                                    }
                                )
                                logger.info(f"✅ Mensagem de imagem registrada no ConversationLogger: {img.get('fileName', 'imagem.jpg')}")
                        except Exception as e:
                            logger.error(f"❌ Erro ao registrar mensagem de imagem no ConversationLogger: {e}")
                    
                except Exception as e:
                    logger.error(f"❌ Erro ao baixar/salvar imagem: {e}")
                self._avancar_coleta_documentos(remetente)
        except Exception as e:
            logger.error(f"❌ Erro ao processar recebimento de documento/imagem para coleta: {e}")
        # Redirecionar para o módulo WhatsAppAPI
        return self.whatsapp_api.processar_webhook_mensagem(webhook_data)

    def _avancar_coleta_documentos(self, remetente: str):
        """
        Avança para o próximo documento da sequência com tempo de espera para múltiplos arquivos.
        """
        try:
            # Aguardar 1 minutos para múltiplos arquivos
            tempo_espera = 40 # 1minutos
            logger.info(f"⏰ Aguardando {tempo_espera}s para múltiplos arquivos de {remetente}...")
            time.sleep(tempo_espera)
            
            # Avançar normalmente
            if hasattr(self, '_controle_coleta_documentos') and remetente in self._controle_coleta_documentos:
                self._controle_coleta_documentos[remetente]['indice_atual'] += 1
                self.solicitar_proximo_documento(remetente)
            else:
                logger.info(f"Usuário {remetente} não está em sequência de coleta ativa.")
                
        except Exception as e:
            logger.error(f"❌ Erro ao avançar coleta para {remetente}: {e}")
    
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
            
            # CAPTURA: Mensagem inicial do usuário (se for colaborador)
            if self.logging_enabled and self.conversation_logger:
                try:
                    conversation_id = self.conversation_logger.get_active_conversation_id(remetente)
                    if conversation_id:
                        # ✅ CORREÇÃO: Usar identificação dinâmica pelo telefone
                        sender_type, receiver_type, phase = self._identificar_tipo_remetente(remetente, conversation_id)
                        
                        # Usar add_message_enhanced para evitar duplicação
                        self.conversation_logger.add_message_enhanced(
                            conversation_id,
                            sender_type,    # ✅ Dinâmico: "corretor" ou "cliente"
                            receiver_type,  # ✅ "ia" 
                            mensagem,
                            phase          # ✅ Dinâmico: "ia_corretor" ou "ia_cliente"
                        )
                except Exception as e:
                    logger.warning(f"⚠️ Erro na captura de mensagem inicial: {e}")
            
            # ====================================================================
            # PRIORIDADE 0: VERIFICAR SE É COLABORADOR EM PROCESSO DE COLETA DE DADOS
            # =========================================================================
            # IMPORTANTE: Esta verificação deve ser ANTES do interpretador GPT para evitar
            # que telefones sejam interpretados como CPF durante a coleta!
            if remetente in self.coleta_dados_cliente and self.coleta_dados_cliente[remetente]["etapa"] != "concluido":
                logger.info(f"📝 Colaborador em processo de coleta detectado: {remetente}")
                return self.processar_coleta_dados_cliente(remetente, mensagem, message_id)
            
            # ====================================================================
            # PRIORIDADE 0.5: VERIFICAR SE É CLIENTE EM PROCESSO DE COLETA EXPANDIDA
            # ======================================================================
            # NOVO: Verificar se cliente está em sessão de coleta de dados expandida
            if (self.fluxo_expandido_ativo and self.coleta_dados_service and 
                self.coleta_dados_service.obter_dados_sessao(remetente)):
                logger.info(f"📋 Cliente em processo de coleta expandida detectado: {remetente}")
                return self.processar_coleta_expandida_cliente(remetente, mensagem, message_id)
            
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
                logger.info(f"✅ CPF recebido: {cpf}")
                
                # 🔥 NOVO: REGISTRAR MENSAGEM DO CPF ANTES DO PROCESSAMENTO
                if self.logging_enabled and self.conversation_logger:
                    try:
                        # Buscar conversa existente (incluindo telefones relacionados)
                        conv_id = self.conversation_logger.obter_conversa_ativa_por_telefone(remetente)
                        
                        if conv_id:
                            # Registrar mensagem do cliente com CPF
                            self.conversation_logger.add_message_enhanced(
                                conversation_id=conv_id,
                                sender="cliente",
                                receiver="ia",
                                content=mensagem,  # A mensagem original contendo o CPF
                                phase="ia_cliente"
                            )
                            logger.info(f"📄 Mensagem do CPF registrada: {mensagem}")
                        else:
                            logger.info(f"⚠️ Nenhuma conversa ativa encontrada para registrar CPF: {remetente}")
                    except Exception as e:
                        logger.warning(f"⚠️ Erro ao registrar mensagem do CPF: {e}")
                
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
                    
                    # NOVO: Iniciar captura de conversa (se habilitado)
                    conversation_id = None
                    if self.logging_enabled:
                        try:
                            conversation_id = self.conversation_logger.start_conversation(
                                remetente,
                                "em_andamento",  # Inicia em andamento, move depois
                                {
                                    "type": "broker",
                                    "name": identificacao.get("dados_usuario", {}).get("nome", "Corretor"),
                                    "phone": remetente,
                                    "cpf": cpf,
                                    "sector": identificacao.get("dados_usuario", {}).get("setor", "N/A")
                                }
                            )
                            logger.info(f"🗂️ Conversa iniciada: {conversation_id}")
                        except Exception as e:
                            logger.warning(f"⚠️ Erro ao iniciar captura: {e}")
                    
                    # 1. Enviar mensagem de boas-vindas personalizada
                    self.enviar_mensagem(remetente, mensagem_resposta)
                    
                    # CAPTURA: Mensagem de boas-vindas da IA (usando add_message_enhanced para evitar duplicação)
                    if self.logging_enabled and self.conversation_logger and conversation_id:
                        try:
                            # Usar add_message_enhanced em vez de add_message para evitar duplicação
                            self.conversation_logger.add_message_enhanced(
                                conversation_id,
                                "ia",
                                "corretor",
                                mensagem_resposta,
                                "ia_corretor"
                            )
                        except Exception as e:
                            logger.warning(f"⚠️ Erro na captura de boas-vindas: {e}")
                    
                    # 2. Aguardar 3 segundos para melhor experiência do usuário
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
                    # FLUXO PARA CLIENTES - MELHORADO COM VERIFICAÇÃO DE CONSENTIMENTO
                    # ----------------------------------------------------------------
                    logger.info("👥 Usuário identificado como CLIENTE - Verificando consentimento LGPD")
                    
                    # NOVO FLUXO: Verificar consentimento LGPD e enviar menu de concordância
                    if self.fluxo_expandido_ativo and self.consentimento_service and self.consentimento_service.is_enabled():
                        try:
                            # Verificar consentimento do cliente
                            resultado_consentimento = self.consentimento_service.verificar_status_consentimento(cpf)
                            logger.info(f"🔒 Consentimento: {resultado_consentimento['mensagem']}")
                            
                            # Buscar dados do corretor que iniciou o atendimento
                            corretor_telefone = self._obter_corretor_da_sessao(remetente)
                            nome_cliente = self._obter_nome_cliente_da_sessao(corretor_telefone)
                            
                            if resultado_consentimento['pode_coletar_dados']:
                                # CLIENTE PODE FORNECER DADOS - Verificar se já tem consentimento completo
                                
                                # Verificar se cliente já tem consentimento completo
                                tem_consentimento_completo = (
                                    resultado_consentimento.get('tem_consentimento', False) and
                                    resultado_consentimento.get('status') == 'complete'
                                )
                                
                                if tem_consentimento_completo:
                                    # Cliente já tem consentimento completo - pular menu e ir direto para coleta
                                    logger.info(f"✅ Cliente já tem consentimento completo - iniciando coleta direta: {remetente}")
                                    
                                    # Iniciar sessão de coleta diretamente
                                    if self.coleta_dados_service:
                                        try:
                                            # Inicializar sessão de coleta
                                            dados_coleta = self.coleta_dados_service.iniciar_coleta(remetente, nome_cliente, cpf)
                                            
                                            # Solicitar primeiro dado: E-mail
                                            mensagem_email = """📧 *Digite seu e-mail:*

Exemplo: seuemail@gmail.com"""
                                            self.enviar_mensagem(remetente, mensagem_email)
                                            
                                            logger.info(f"📋 Coleta iniciada diretamente para cliente com consentimento: {remetente}")
                                            
                                        except Exception as e:
                                            logger.error(f"❌ Erro ao iniciar coleta direta: {e}")
                                            # Fallback: transferir para corretor
                                            self._transferir_para_corretor(remetente, corretor_telefone, nome_cliente, "erro_coleta")
                                    else:
                                        # Serviço não disponível - transferir para corretor
                                        self._transferir_para_corretor(remetente, corretor_telefone, nome_cliente, "servico_indisponivel")
                                
                            else:
                                # NÃO PODE COLETAR - Cliente já revogou consentimento
                                mensagem_bloqueio = self.consentimento_service.gerar_mensagem_para_cliente(resultado_consentimento)
                                self.enviar_mensagem(remetente, mensagem_bloqueio)
                                
                                # Notificar corretor sobre a situação
                                if corretor_telefone:
                                    mensagem_corretor = f"""⚠️ *Cliente com restrição LGPD*

O cliente informou o CPF {cpf[:3]}***{cpf[-2:]} mas *revogou* seu consentimento para uso de dados pessoais.

Não foi possível prosseguir com a coleta automática. Entre em contato diretamente para esclarecer a situação."""
                                    
                                    self.enviar_mensagem(corretor_telefone, mensagem_corretor)
                                    logger.info(f"📞 Corretor {corretor_telefone} notificado sobre restrição LGPD")
                                
                                logger.warning(f"⛔ Coleta bloqueada por revogação de consentimento: {remetente}")
                                
                        except Exception as e:
                            logger.warning(f"⚠️ Erro na verificação de consentimento: {e}")
                            # Fallback seguro: manter fluxo original
                            self.enviar_mensagem(remetente, mensagem_resposta)
                    
                    else:
                        # FLUXO ORIGINAL PRESERVADO (quando serviços não disponíveis)
                        logger.info("📄 Fluxo original mantido - serviços expandidos não disponíveis")
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

    def _obter_corretor_da_sessao(self, cliente_telefone: str) -> Optional[str]:
        """
        Obtém o telefone do corretor que iniciou atendimento com este cliente
        
        Args:
            cliente_telefone (str): Telefone do cliente
            
        Returns:
            str ou None: Telefone do corretor se encontrado
        """
        try:
            # Buscar nos atendimentos ativos
            for corretor_telefone, dados in self.atendimentos_cliente.items():
                if dados.get("cliente_telefone") == cliente_telefone:
                    logger.info(f"🔍 Corretor encontrado: {corretor_telefone} para cliente {cliente_telefone}")
                    return corretor_telefone
            
            # Buscar nas coletas de dados (corretor que coletou dados)
            for corretor_telefone, dados_coleta in self.coleta_dados_cliente.items():
                # Verificar se o telefone normalizado bate
                telefone_coleta = dados_coleta.get("telefone", "")
                # Extrair números do telefone
                numeros_coleta = re.sub(r'\D', '', telefone_coleta)
                numeros_cliente = re.sub(r'\D', '', cliente_telefone)
                
                if numeros_coleta and numeros_cliente and numeros_coleta in numeros_cliente:
                    logger.info(f"🔍 Corretor encontrado via coleta: {corretor_telefone} para cliente {cliente_telefone}")
                    return corretor_telefone
            
            logger.warning(f"⚠️ Corretor não encontrado para cliente: {cliente_telefone}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar corretor: {e}")
            return None
    
    def _obter_nome_cliente_da_sessao(self, corretor_telefone: str) -> Optional[str]:
        """
        Obtém o nome do cliente da sessão do corretor
        
        Args:
            corretor_telefone (str): Telefone do corretor
            
        Returns:
            str ou None: Nome do cliente se encontrado
        """
        try:
            if not corretor_telefone:
                return None
            
            # Buscar nos dados de coleta do corretor
            if corretor_telefone in self.coleta_dados_cliente:
                nome = self.coleta_dados_cliente[corretor_telefone].get("nome", "")
                if nome:
                    logger.info(f"👤 Nome do cliente encontrado: {nome[:10]}... para corretor {corretor_telefone}")
                    return nome
            
            # Buscar nos atendimentos
            if corretor_telefone in self.atendimentos_cliente:
                nome = self.atendimentos_cliente[corretor_telefone].get("cliente_nome", "")
                if nome:
                    logger.info(f"👤 Nome do cliente encontrado via atendimento: {nome[:10]}...")
                    return nome
            
            logger.info(f"⚠️ Nome do cliente não encontrado para corretor: {corretor_telefone}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar nome do cliente: {e}")
            return None

    def processar_coleta_expandida_cliente(self, remetente: str, mensagem: str, message_id: str = None) -> Dict[str, Any]:
        """
        Processa coleta expandida de dados do cliente
        """
        try:
            logger.info(f"📋 Processando coleta expandida - Cliente: {remetente}")
            
            # 🔥 DEBUG: Verificar se existe sessão de coleta
            dados_sessao_atual = self.coleta_dados_service.obter_dados_sessao(remetente)
            if dados_sessao_atual:
                logger.info(f"🔍 SESSÃO ENCONTRADA - Etapa atual: {dados_sessao_atual.etapa_atual}")
                logger.info(f"📊 Dados da sessão: Nome={dados_sessao_atual.nome}, CPF={dados_sessao_atual.cpf}")
            else:
                logger.warning(f"⚠️ NENHUMA SESSÃO DE COLETA ENCONTRADA para {remetente}")
                return {
                    "sucesso": False,
                    "erro": "Sessão de coleta não encontrada",
                    "mensagem_resposta": "Sessão expirada. Por favor, informe seu CPF novamente."
                }
            
            # NOVO: Capturar mensagem do cliente
            if self.logging_enabled and self.conversation_logger:
                # ✅ MELHORADO: Buscar conversa existente (incluindo telefones relacionados)
                conv_id = self.conversation_logger.obter_conversa_ativa_por_telefone(remetente)
                
                if not conv_id:
                    # ✅ CORREÇÃO: Só criar se realmente não existir
                    conv_id = self.conversation_logger.start_conversation(
                        phone_number=remetente,
                        conversation_type="em_andamento",
                        participant_data={
                            "telefone": remetente,
                            "tipo": "cliente",
                            "processo": "coleta_expandida"
                        }
                    )
                    logger.info(f"🆕 Nova conversa criada para cliente: {conv_id}")
                else:
                    # ✅ NOVO: Conversa encontrada - transicionar para fase cliente
                    self.conversation_logger.transition_phase(conv_id, "ia_cliente", "client_started_data_collection")
                    logger.info(f"🔄 Conversa existente encontrada, transitando para fase cliente: {conv_id}")
                
                if conv_id:
                    # Registrar mensagem do cliente - CORRIGIDO: usar add_message_enhanced
                    self.conversation_logger.add_message_enhanced(
                        conversation_id=conv_id,
                        sender="cliente",
                        receiver="ia",
                        content=mensagem,
                        phase="ia_cliente"
                    )
            
            # Marcar mensagem como lida
            if message_id:
                self.marcar_como_lida(remetente, message_id)
            
            # 🔥 DEBUG: Log antes do processamento
            logger.info(f"🔄 Processando mensagem '{mensagem}' para etapa '{dados_sessao_atual.etapa_atual}'")
            
            # Processar resposta usando o serviço de coleta
            resultado = self.coleta_dados_service.processar_resposta(remetente, mensagem)
            
            # 🔥 DEBUG: Log do resultado
            logger.info(f"📊 Resultado do processamento: sucesso={resultado['sucesso']}, proxima_etapa={resultado.get('proxima_etapa', 'N/A')}")
            if not resultado['sucesso']:
                logger.warning(f"⚠️ Erro no processamento: {resultado.get('erro', 'N/A')}")
            
            if resultado['sucesso']:
                logger.info(f"✅ Etapa processada: {resultado.get('proxima_etapa', 'N/A')}")
                
                # 🔥 NOVO: Atualizar dados do cliente na conversa PROGRESSIVAMENTE (igual ao corretor)
                if self.logging_enabled and self.conversation_logger:
                    conv_id = self.conversation_logger.obter_conversa_ativa_por_telefone(remetente)
                    if conv_id:
                        # Obter dados atuais da sessão de coleta (sempre tentar atualizar quando há sucesso)
                        dados_sessao = self.coleta_dados_service.obter_dados_sessao(remetente)
                        if dados_sessao:
                            # Preparar dados do cliente com todos os campos disponíveis
                            dados_cliente_atualizados = {
                                "name": dados_sessao.nome,
                                "phone": remetente,
                                "whatsapp_verified": True
                            }
                            
                            # Incluir CPF se disponível
                            if dados_sessao.cpf:
                                dados_cliente_atualizados["cpf"] = dados_sessao.cpf
                                logger.info(f"📄 CPF incluído na atualização: {dados_sessao.cpf}")
                            
                            # Incluir email se disponível
                            if dados_sessao.email:
                                dados_cliente_atualizados["email"] = dados_sessao.email
                                logger.info(f"📧 Email incluído na atualização: {dados_sessao.email}")
                            
                            # Incluir data de nascimento e idade se disponível
                            if dados_sessao.data_nascimento:
                                dados_cliente_atualizados["data_nascimento"] = dados_sessao.data_nascimento
                                if dados_sessao.idade:
                                    dados_cliente_atualizados["idade"] = dados_sessao.idade
                                logger.info(f"📅 Data nascimento incluída: {dados_sessao.data_nascimento}")
                            
                            # Incluir endereço se disponível
                            if dados_sessao.endereco_completo:
                                dados_cliente_atualizados["endereco_completo"] = dados_sessao.endereco_completo
                                dados_cliente_atualizados["cep"] = dados_sessao.cep
                                dados_cliente_atualizados["cidade"] = dados_sessao.cidade
                                dados_cliente_atualizados["uf"] = dados_sessao.uf
                                logger.info(f"🏠 Endereço incluído: {dados_sessao.cidade}/{dados_sessao.uf}")
                            
                            # Incluir número da residência se disponível
                            if dados_sessao.numero:
                                dados_cliente_atualizados["numero_residencia"] = dados_sessao.numero
                                logger.info(f"🏠 Número incluído: {dados_sessao.numero}")
                            
                            # ✅ ATUALIZAÇÃO PROGRESSIVA: Usar mesmo padrão do corretor
                            logger.info(f"🔄 INICIANDO ATUALIZAÇÃO PROGRESSIVA: {conv_id}")
                            logger.info(f"📊 Dados a serem atualizados: {dados_cliente_atualizados}")
                            
                            sucesso_atualizacao = self.conversation_logger.update_participant_data(
                                conv_id,
                                "client",
                                dados_cliente_atualizados
                            )
                            
                            if sucesso_atualizacao:
                                logger.info(f"✅ ATUALIZAÇÃO PROGRESSIVA CONCLUÍDA COM SUCESSO: {conv_id}")
                            else:
                                logger.warning(f"⚠️ FALHA NA ATUALIZAÇÃO PROGRESSIVA: {conv_id}")
                
                # Enviar mensagem de resposta
                if 'mensagem' in resultado:
                    self.enviar_mensagem(remetente, resultado['mensagem'])
                    
                    # ✅ NOVO: Enviar também para o corretor se for mensagem final de coleta
                    if resultado.get('coleta_finalizada'):
                        try:
                            corretor_telefone = self._obter_corretor_da_sessao(remetente)
                            if corretor_telefone:
                                self.enviar_mensagem(corretor_telefone, resultado['mensagem'])
                                logger.info(f"✅ Mensagem final enviada também para corretor: {corretor_telefone}")
                                
                                # ✅ NOVA FUNCIONALIDADE: Capturar mensagem para corretor com classificação automática
                                if self.logging_enabled and self.conversation_logger:
                                    conv_id = self.conversation_logger.obter_conversa_ativa_por_telefone(remetente)
                                    if conv_id:
                                        self.conversation_logger.add_message_enhanced(
                                            conversation_id=conv_id,
                                            sender="ia",
                                            receiver="cliente",  # Será corrigido automaticamente para "corretor"
                                            content=resultado['mensagem'],
                                            phase="ia_cliente",
                                            telefone_destinatario=corretor_telefone  # ✅ CLASSIFICAÇÃO AUTOMÁTICA!
                                        )
                        except Exception as e:
                            logger.warning(f"⚠️ Erro ao enviar mensagem para corretor: {e}")
                    
                    # NOVO: Capturar mensagem de resposta da IA - CORRIGIDO: usar add_message_enhanced
                    if self.logging_enabled and self.conversation_logger:
                        conv_id = self.conversation_logger.obter_conversa_ativa_por_telefone(remetente)
                        if conv_id:
                            self.conversation_logger.add_message_enhanced(
                                conversation_id=conv_id,
                                sender="ia",
                                receiver="cliente",
                                content=resultado['mensagem'],
                                phase="ia_cliente"
                            )
                
                # ✅ NOVO: Verificar se precisa enviar menu de confirmação de endereço
                if resultado.get('proxima_etapa') == 'endereco_confirmacao' and resultado.get('acao') == 'enviar_menu_confirmacao_endereco':
                    # Enviar mensagem primeiro
                    if 'mensagem' in resultado:
                        self.enviar_mensagem(remetente, resultado['mensagem'])
                        
                        # NOVO: Capturar mensagem de resposta da IA
                        if self.logging_enabled and self.conversation_logger:
                            conv_id = self.conversation_logger.obter_conversa_ativa_por_telefone(remetente)
                            if conv_id:
                                self.conversation_logger.add_message_enhanced(
                                    conversation_id=conv_id,
                                    sender="ia",
                                    receiver="cliente",
                                    content=resultado['mensagem'],
                                    phase="ia_cliente"
                                )
                    
                    # Aguardar 1 segundo
                    time.sleep(1)
                    
                    # Enviar menu de confirmação
                    self.menu_service.enviar_menu_confirmacao_endereco(
                        remetente,
                        resultado.get('endereco', '')
                    )
                    return {
                        "sucesso": True,
                        "etapa": resultado.get('proxima_etapa', 'processando'),
                        "mensagem_resposta": resultado.get('mensagem', 'Processado com sucesso'),
                        "dados_completos": resultado.get('coleta_finalizada', False)
                    }
                
                # Enviar mensagem de resposta (para outros casos)
                if 'mensagem' in resultado:
                    self.enviar_mensagem(remetente, resultado['mensagem'])
                
                # Verificar se coleta foi finalizada
                if resultado.get('coleta_finalizada'):
                    logger.info(f"🎉 Coleta de dados finalizada para cliente: {remetente}")
                    
                    # Obter dados completos
                    dados_completos = resultado.get('dados_completos', {})
                    
                    # Verificar resultados do salvamento
                    cliente_salvo = resultado.get('cliente_salvo', False)
                    negociacao_criada = resultado.get('negociacao_criada', False)
                    
                    if cliente_salvo:
                        cliente_id = resultado.get('cliente_id')
                        logger.info(f"✅ Cliente salvo no Supabase: {cliente_id}")
                        
                        if negociacao_criada:
                            negociacao_id = resultado.get('negociacao_id')
                            logger.info(f"✅ Negociação criada no Supabase: {negociacao_id}")
                        else:
                            logger.warning("⚠️ Cliente salvo mas negociação não foi criada")
                    else:
                        logger.error("❌ Falha ao salvar cliente no Supabase")
                        erros = resultado.get('erros', [])
                        for erro in erros:
                            logger.error(f"❌ Erro {erro['tipo']}: {erro['erro']}")
                    
                    # Enviar menu de confirmação de documentos (se salvamento foi bem-sucedido)
                    if cliente_salvo and negociacao_criada:
                        try:
                            logger.info(f"📄 Enviando menu de confirmação de documentos para: {remetente}")
                            self.menu_service.enviar_menu_confirmacao_documentos(remetente)
                            logger.info(f"✅ Menu de documentos enviado com sucesso para: {remetente}")
                        except Exception as e:
                            logger.warning(f"⚠️ Erro ao enviar menu de documentos: {e}")
                            # Não falhar o processo se menu falhar
                    
                    # Limpar sessão de coleta
                    self.coleta_dados_service.limpar_sessao(remetente)
                    
                    logger.info("🎯 Processamento de coleta finalizado")
                
                return {
                    "sucesso": True,
                    "etapa": resultado.get('proxima_etapa', 'processando'),
                    "mensagem_resposta": resultado.get('mensagem', 'Processado com sucesso'),
                    "dados_completos": resultado.get('coleta_finalizada', False)
                }
            
            else:
                # Erro no processamento
                logger.warning(f"⚠️ Erro na coleta: {resultado.get('erro', 'Erro desconhecido')}")
                
                # Verificar ações especiais
                if resultado.get('acao') == 'transferir_atendente':
                    # Cliente rejeitou endereço - transferir para atendente humano
                    logger.info(f"👤 Transferindo cliente para atendente humano: {remetente}")
                    self.coleta_dados_service.limpar_sessao(remetente)
                    # Aqui você poderia implementar transferência real
                
                elif resultado.get('acao') == 'idade_insuficiente':
                    # Cliente menor de 18 anos
                    logger.info(f"🔞 Cliente menor de idade: {remetente}")
                    self.coleta_dados_service.limpar_sessao(remetente)
                
                elif resultado.get('acao') == 'reiniciar_coleta':
                    # Sessão perdida - limpar e reiniciar
                    logger.info(f"🔄 Reiniciando coleta para: {remetente}")
                    self.coleta_dados_service.limpar_sessao(remetente)
                
                # 🔥 NOVO: Verificar se precisa reenviar menu de confirmação de endereço
                elif resultado.get('acao') == 'enviar_menu_confirmacao_endereco':
                    logger.info(f"🔄 Reenviando menu de confirmação de endereço para: {remetente}")
                    # Aguardar 1 segundo
                    time.sleep(1)
                    # Enviar menu de confirmação
                    self.menu_service.enviar_menu_confirmacao_endereco(
                        remetente,
                        resultado.get('endereco', '')
                    )
                    return {
                        "sucesso": False,
                        "erro": resultado.get('erro', 'Erro no processamento'),
                        "acao": "menu_reenviado",
                        "mensagem_resposta": "Menu de confirmação reenviado"
                    }
                
                # Enviar mensagem de erro se disponível
                if 'mensagem' in resultado:
                    self.enviar_mensagem(remetente, resultado['mensagem'])
                    
                    # NOVO: Capturar mensagem de erro da IA - CORRIGIDO: usar add_message_enhanced
                    if self.logging_enabled and self.conversation_logger:
                        conv_id = self.conversation_logger.obter_conversa_ativa_por_telefone(remetente)
                        if conv_id:
                            self.conversation_logger.add_message_enhanced(
                                conversation_id=conv_id,
                                sender="ia",
                                receiver="cliente",
                                content=resultado['mensagem'],
                                phase="ia_cliente"
                            )
                
                return {
                    "sucesso": False,
                    "erro": resultado.get('erro', 'Erro no processamento'),
                    "acao": resultado.get('acao', 'continuar'),
                    "mensagem_resposta": resultado.get('mensagem', 'Erro processado')
                }
            
        except Exception as e:
            logger.error(f"❌ Erro na coleta expandida: {e}")
            
            # Cleanup em caso de erro
            if self.coleta_dados_service:
                self.coleta_dados_service.limpar_sessao(remetente)
            
            # Mensagem de erro para o cliente
            mensagem_erro = """❌ *Erro interno*

Ocorreu um problema técnico. Vou te transferir para um atendente.

📞 Ou entre em contato: *(14) 99999-9999*"""
            
            self.enviar_mensagem(remetente, mensagem_erro)
            
            # NOVO: Capturar mensagem de erro interno - CORRIGIDO: usar add_message_enhanced
            if self.logging_enabled and self.conversation_logger:
                conv_id = self.conversation_logger.obter_conversa_ativa_por_telefone(remetente)
                if conv_id:
                    self.conversation_logger.add_message_enhanced(
                        conversation_id=conv_id,
                        sender="ia",
                        receiver="cliente",
                        content=mensagem_erro,
                        phase="ia_cliente"
                    )
            
            return {
                "sucesso": False,
                "erro": f"Erro interno: {str(e)}",
                "mensagem_resposta": "Erro interno - cliente transferido"
            }

    def _processar_concordancia_lgpd_sim(self, remetente: str, row_id: str) -> Dict[str, Any]:
        """
        Processa quando cliente concorda com LGPD e inicia coleta expandida
        
        Args:
            remetente (str): Telefone do cliente
            row_id (str): ID da opção selecionada
            
        Returns:
            Dict: Resultado do processamento
        """
        try:
            logger.info(f"✅ Cliente concordou com LGPD: {remetente}")
            
            # Obter dados da sessão de espera
            dados_lgpd = None
            if hasattr(self, 'aguardando_lgpd') and remetente in self.aguardando_lgpd:
                dados_lgpd = self.aguardando_lgpd[remetente]
                del self.aguardando_lgpd[remetente]  # Limpar estado de espera
            
            if not dados_lgpd:
                logger.error(f"❌ Dados LGPD não encontrados para {remetente}")
                return {
                    "sucesso": False,
                    "erro": "Sessão LGPD expirada",
                    "mensagem_resposta": "Sessão expirada. Por favor, informe seu CPF novamente."
                }
            
            cpf = dados_lgpd['cpf']
            corretor_telefone = dados_lgpd['corretor']
            nome_cliente = dados_lgpd['nome_cliente'] or "Cliente"
            
            # Mensagem de confirmação personalizada
            mensagem_confirmacao = f"""✅ *Concordância Registrada*

Obrigado {nome_cliente}! Seus dados serão tratados com total segurança.

📋 *Dados Adicionais Necessários*

Para prosseguir com seu atendimento, preciso coletar algumas informações básicas.

Vamos começar:"""
            
            # Enviar mensagem de confirmação
            self.enviar_mensagem(remetente, mensagem_confirmacao)
            time.sleep(2)
            
            # SALVAR CONSENTIMENTO NO SUPABASE
            if self.consentimento_service:
                try:
                    resultado_salvamento = self.consentimento_service.salvar_consentimento_lgpd(
                        client_cpf=cpf,
                        client_name=nome_cliente,
                        client_phone=remetente,
                        tipo_consentimento="complete",
                        consent_origin="whatsapp",
                        whatsapp_message_id=f"menu_lgpd_{int(time.time())}",
                        notes=f"Cliente concordou via menu LGPD - Row ID: {row_id}"
                    )
                    
                    if resultado_salvamento["success"]:
                        logger.info(f"💾 Consentimento salvo no Supabase: {resultado_salvamento['action']} - Status: {resultado_salvamento['status']}")
                    else:
                        logger.warning(f"⚠️ Falha ao salvar consentimento: {resultado_salvamento['message']}")
                        
                except Exception as e_save:
                    logger.error(f"❌ Erro ao salvar consentimento: {e_save}")
            
            # INICIAR COLETA EXPANDIDA
            if self.coleta_dados_service:
                try:
                    # Inicializar sessão de coleta
                    dados_coleta = self.coleta_dados_service.iniciar_coleta(remetente, nome_cliente, cpf)
                    
                    # Solicitar primeiro dado: E-mail
                    mensagem_email = """📧 *Digite seu e-mail:*

Exemplo: seuemail@gmail.com"""
                    self.enviar_mensagem(remetente, mensagem_email)
                    
                    logger.info(f"📋 Coleta expandida iniciada após concordância LGPD: {remetente}")
                    
                    # Notificar corretor sobre o sucesso
                    if corretor_telefone:
                        mensagem_corretor = f"""✅ *Cliente concordou com LGPD*

O cliente {nome_cliente} concordou com o tratamento de dados e a coleta automática foi iniciada.

📋 *Status*: Coletando dados adicionais automaticamente
💾 *Consentimento*: Salvo no sistema automaticamente  
⏰ *Próximo passo*: Aguardar finalização da coleta"""
                        
                        self.enviar_mensagem(corretor_telefone, mensagem_corretor)
                        logger.info(f"📞 Corretor {corretor_telefone} notificado sobre concordância")
                    
                    return {
                        "sucesso": True,
                        "acao": "coleta_iniciada",
                        "tipo_usuario": "cliente",
                        "mensagem_resposta": "Coleta expandida iniciada",
                        "dados_lgpd": dados_lgpd,
                        "row_id_processado": row_id,
                        "consentimento_salvo": True
                    }
                    
                except Exception as e:
                    logger.error(f"❌ Erro ao iniciar coleta expandida: {e}")
                    # Fallback: transferir para corretor
                    return self._transferir_para_corretor(remetente, corretor_telefone, nome_cliente, "erro_coleta")
            
            else:
                # Serviço de coleta não disponível - transferir para corretor
                return self._transferir_para_corretor(remetente, corretor_telefone, nome_cliente, "servico_indisponivel")
            
        except Exception as e:
            logger.error(f"❌ Erro no processamento de concordância LGPD: {e}")
            return {
                "sucesso": False,
                "erro": f"Erro interno: {str(e)}",
                "mensagem_resposta": "Erro interno - tente novamente"
            }

    def _processar_concordancia_lgpd_nao(self, remetente: str, row_id: str) -> Dict[str, Any]:
        """
        Processa quando cliente NÃO concorda com LGPD ou quer mais informações
        
        Args:
            remetente (str): Telefone do cliente
            row_id (str): ID da opção selecionada
            
        Returns:
            Dict: Resultado do processamento
        """
        try:
            logger.info(f"❌ Cliente não concordou com LGPD: {remetente} ({row_id})")
            
            # Obter dados da sessão de espera
            dados_lgpd = None
            if hasattr(self, 'aguardando_lgpd') and remetente in self.aguardando_lgpd:
                dados_lgpd = self.aguardando_lgpd[remetente]
                del self.aguardando_lgpd[remetente]  # Limpar estado de espera
            
            corretor_telefone = dados_lgpd.get('corretor') if dados_lgpd else None
            nome_cliente = dados_lgpd.get('nome_cliente', 'Cliente') if dados_lgpd else 'Cliente'
            
            # Mensagem para o cliente
            mensagem_cliente = """📞 *Atendimento Personalizado*

Entendo sua preocupação com a proteção de dados.

Vou conectar você com um de nossos atendentes especializados que poderá esclarecer todas suas dúvidas e prosseguir com seu atendimento de forma personalizada.

⏰ *Aguarde um momento...*"""
            
            self.enviar_mensagem(remetente, mensagem_cliente)
            
            # Notificar corretor sobre a recusa
            if corretor_telefone:
                if row_id == "mais_informacoes":
                    motivo = "solicitou mais informações sobre proteção de dados"
                else:
                    motivo = "não concordou com o tratamento de dados pessoais"
                
                mensagem_corretor = f"""⚠️ *Cliente necessita atendimento personalizado*

*Cliente*: {nome_cliente}
*Telefone*: {remetente}
*Situação*: O cliente {motivo}

🔒 *LGPD*: Não foi possível prosseguir com coleta automática

📞 *Ação necessária*: Entre em contato direto para:
• Esclarecer dúvidas sobre proteção de dados
• Explicar o processo de forma personalizada  
• Coletar dados manualmente se cliente concordar

⏰ Cliente foi informado que receberá atendimento personalizado."""
                
                self.enviar_mensagem(corretor_telefone, mensagem_corretor)
                logger.info(f"📞 Corretor {corretor_telefone} notificado sobre necessidade de atendimento personalizado")
            
            return {
                "sucesso": True,
                "acao": "atendimento_personalizado",
                "tipo_usuario": "cliente", 
                "mensagem_resposta": "Cliente direcionado para atendimento personalizado",
                "motivo": row_id,
                "corretor_notificado": corretor_telefone is not None,
                "row_id_processado": row_id
            }
            
        except Exception as e:
            logger.error(f"❌ Erro no processamento de recusa LGPD: {e}")
            return {
                "sucesso": False,
                "erro": f"Erro interno: {str(e)}",
                "mensagem_resposta": "Erro interno - tente novamente"
            }

    def _transferir_para_corretor(self, cliente_telefone: str, corretor_telefone: str, nome_cliente: str, motivo: str) -> Dict[str, Any]:
        """
        Transfere o atendimento para um corretor específico
        """
        try:
            # Mensagem para o cliente
            mensagem_cliente = """📞 *Transferindo para Atendente*

Vou conectar você com um de nossos atendentes para prosseguir com seu atendimento de forma personalizada.

⏰ *Aguarde o contato...*"""
            
            self.enviar_mensagem(cliente_telefone, mensagem_cliente)
            
            # Mensagem para o corretor
            if corretor_telefone:
                motivos_amigaveis = {
                    "erro_coleta": "erro técnico na coleta automática",
                    "servico_indisponivel": "serviço de coleta temporariamente indisponível",
                    "sessao_expirada": "sessão de atendimento expirada"
                }
                
                motivo_amigavel = motivos_amigaveis.get(motivo, motivo)
                
                mensagem_corretor = f"""🔄 *Transferência de Cliente*

*Cliente*: {nome_cliente}
*Telefone*: {cliente_telefone}  
*Motivo*: {motivo_amigavel}

📞 *Ação necessária*: Entre em contato direto para prosseguir com o atendimento manualmente.

⏰ Cliente foi informado sobre a transferência."""
                
                self.enviar_mensagem(corretor_telefone, mensagem_corretor)
                logger.info(f"📞 Cliente transferido para corretor {corretor_telefone}")
            
            # NOVO: Transicionar fase para cliente e atualizar dados
            if self.logging_enabled and self.conversation_logger:
                # Obter ID da conversa ativa do corretor
                conv_id = self.conversation_logger.get_active_conversation_id(corretor_telefone)
                if conv_id:
                    # Atualizar dados do cliente
                    self.conversation_logger.update_participant_data(
                        conv_id,
                        "client",
                        {
                            "name": nome_cliente,
                            "phone": cliente_telefone,
                            "whatsapp_verified": True
                        }
                    )
                    # Transicionar para fase de cliente
                    self.conversation_logger.transition_phase(
                        conv_id,
                        "ia_cliente",
                        "client_contact_initiated"
                    )
            
            return {
                "sucesso": True,
                "acao": "transferencia_realizada",
                "motivo": motivo,
                "corretor_notificado": corretor_telefone is not None
            }
            
        except Exception as e:
            logger.error(f"❌ Erro na transferência: {e}")
            return {
                "sucesso": False,
                "erro": f"Erro na transferência: {str(e)}"
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
                
                # ✅ NOVO: Registrar mensagem da IA no JSON
                if self.logging_enabled and self.conversation_logger:
                    try:
                        conversation_id = self.conversation_logger.get_active_conversation_id(remetente)
                        if conversation_id:
                            self.conversation_logger.add_message_enhanced(
                                conversation_id,
                                "ia",
                                "corretor",
                                mensagem_resposta,
                                "ia_corretor",
                                telefone_destinatario=remetente
                            )
                    except Exception as e:
                        logger.warning(f"⚠️ Erro ao registrar mensagem da IA no JSON: {e}")
                
                # VERIFICAR AÇÕES ESPECIAIS DOS COLABORADORES
                # ==========================================
                
                # Ativação da IA Especializada
                if resultado_processamento["acao"] == "ativar_ia_especializada":
                    # CAPTURA: Colaborador escolheu "Usar IA para Dúvidas"
                    if self.logging_enabled and self.conversation_logger:
                        try:
                            conversation_id = self.conversation_logger.get_active_conversation_id(remetente)
                            if conversation_id:
                                self.conversation_logger.update_conversation_type(conversation_id, "duvidas")
                                # Usar add_message_enhanced para evitar duplicação
                                self.conversation_logger.add_message_enhanced(
                                    conversation_id,
                                    "corretor",
                                    "ia",
                                    f"Menu selecionado: Usar IA para Dúvidas (row_id: {row_id})",
                                    "ia_corretor"
                                )
                        except Exception as e:
                            logger.warning(f"⚠️ Erro na captura de menu dúvidas: {e}")
                    
                    # MODULARIZADO: Usar SessionManager para criar sessão
                    resultado_sessao = self.session_manager.criar_sessao_ia_especializada(
                        telefone=remetente,
                        dados_colaborador=None  # Será preenchido quando necessário
                    )
                    if resultado_sessao["sucesso"]:
                        logger.info(f"🤖 IA Especializada ATIVADA para colaborador: {remetente} (expira em {resultado_sessao['timeout_minutos']:.1f}min)")
                    else:
                        logger.error(f"❌ Erro ao criar sessão IA: {resultado_sessao.get('erro')}")
                
                # Início da coleta de dados do cliente
                elif resultado_processamento["acao"] == "coletar_nome_cliente":
                    # CAPTURA: Colaborador escolheu "Iniciar Fechamento Locação"
                    if self.logging_enabled and self.conversation_logger:
                        try:
                            conversation_id = self.conversation_logger.get_active_conversation_id(remetente)
                            if conversation_id:
                                self.conversation_logger.update_conversation_type(conversation_id, "em_andamento")
                                # Usar add_message_enhanced para evitar duplicação
                                self.conversation_logger.add_message_enhanced(
                                    conversation_id,
                                    "corretor",
                                    "ia",
                                    f"Menu selecionado: Iniciar Fechamento Locação (row_id: {row_id})",
                                    "ia_corretor"
                                )
                        except Exception as e:
                            logger.warning(f"⚠️ Erro na captura de menu fechamento: {e}")
                    
                    # Iniciar processo de coleta de dados do cliente
                    self.coleta_dados_cliente[remetente] = {
                        "nome": "",
                        "telefone": "",
                        "etapa": "aguardando_nome",
                        "iniciado_em": time.time()
                    }
                    logger.info(f"📝 Iniciando coleta de dados do cliente para colaborador: {remetente}")
                
                # NOVO: Processamento de respostas do menu LGPD
                elif resultado_processamento["acao"] == "iniciar_processo_completo":
                    # Cliente concordou com tudo - iniciar coleta expandida
                    return self._processar_concordancia_lgpd_sim(remetente, "concordo_tudo")
                
                elif resultado_processamento["acao"] == "transferir_atendente":
                    # Cliente quer mais informações - notificar corretor
                    return self._processar_concordancia_lgpd_nao(remetente, "mais_informacoes")
                
                elif resultado_processamento["acao"] == "enviar_politica":
                    # Cliente quer ler política de privacidade - buscar link dinâmico
                    self._enviar_politica_privacidade(remetente)
                    logger.info(f"📄 Política de privacidade enviada para: {remetente}")
                
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
                    time.sleep(1.5)  # ✅ Pausa para estabilização
                    logger.info(f"📋 Solicitando CPF para cliente: {remetente}")
                
                # Cliente recusa atendimento (NÃO)
                elif resultado_processamento["acao"] == "encerrar_atendimento_cliente":
                    # Limpar dados do atendimento
                    if remetente in self.atendimentos_cliente:
                        del self.atendimentos_cliente[remetente]
                    logger.info(f"❌ Cliente recusou atendimento: {remetente}")
                
                # NOVO: Iniciar coleta de documentos
                elif resultado_processamento["acao"] == "iniciar_coleta_documentos":
                    logger.info(f"📄 Iniciando coleta de documentos para cliente: {remetente}")
                    
                    try:
                        # Aguardar 1,5 segundos para estabilização
                        time.sleep(1.5)
                        
                        # Importar função para criar mensagem de documentos
                        from .buscar_usuarios_supabase import criar_mensagem_documentos_obrigatorios
                        
                        # Criar mensagem com documentos obrigatórios
                        mensagem_documentos = criar_mensagem_documentos_obrigatorios()
                        
                        # Enviar mensagem para o cliente
                        self.enviar_mensagem(remetente, mensagem_documentos)
                        
                        logger.info(f"✅ Mensagem de documentos enviada para: {remetente}")
                        
                        # NOVO: Enviar mensagem para o corretor
                        try:
                            # Aguardar 1 segundo antes de enviar para corretor
                            time.sleep(1)
                            
                            # Obter dados do corretor e cliente da sessão
                            corretor_telefone = self._obter_corretor_da_sessao(remetente)
                            nome_cliente = self._obter_nome_cliente_da_sessao(remetente)
                            
                            if corretor_telefone:
                                mensagem_corretor = f"✅ Cliente concordou com coleta de documentos. Fluxo iniciado."
                                self.enviar_mensagem(corretor_telefone, mensagem_corretor)
                                logger.info(f"✅ Mensagem enviada para corretor: {corretor_telefone}")
                            else:
                                logger.warning(f"⚠️ Não foi possível obter telefone do corretor para: {remetente}")
                                
                        except Exception as e:
                            logger.error(f"❌ Erro ao enviar mensagem para corretor: {e}")
                        
                        # NOVO: Enviar menu de início de coleta de documentos para o cliente
                        try:
                            self.menu_service.enviar_menu_inicio_coleta_documentos(remetente)
                            logger.info(f"✅ Menu de início de coleta de documentos enviado para: {remetente}")
                        except Exception as e:
                            logger.error(f"❌ Erro ao enviar menu de início de coleta de documentos: {e}")
                
                    except Exception as e:
                        logger.error(f"❌ Erro ao enviar mensagem de documentos: {e}")
                        
                        # FALLBACK: Usar documentos da imagem se função falhar
                        mensagem_fallback = """📄 *DOCUMENTOS OBRIGATÓRIOS*

Ótimo! Vamos iniciar o Fluxo de Coleta de Documentos.

Os documentos obrigatórios são:

1. *Comprovante de Residência*
   Conta de luz, água ou telefone

2. *Comprovante de Renda*
   Últimos 3 holerites ou declaração de renda

3. *Certidão de Nascimento/Casamento*
   Estado civil

4. *RG / CNH*
   Documento de identidade

⚠️ *IMPORTANTE:* Todos os documentos devem estar em formato PDF.

Envie um documento por vez. Vou te guiar durante todo o processo! 📋"""
                        
                        self.enviar_mensagem(remetente, mensagem_fallback)
                        logger.info(f"✅ Mensagem de fallback enviada para: {remetente}")
                
                # NOVO: Encerrar processo de documentos (cliente não concordou)
                elif resultado_processamento["acao"] == "encerrar_processo_documentos":
                    logger.info(f"❌ Cliente não concordou com coleta de documentos: {remetente}")
                    
                    try:
                        # Aguardar 1 segundo antes de enviar para corretor
                        time.sleep(1)
                        
                        # Obter dados do corretor e cliente da sessão
                        corretor_telefone = self._obter_corretor_da_sessao(remetente)
                        nome_cliente = self._obter_nome_cliente_da_sessao(remetente)
                        
                        if corretor_telefone:
                            mensagem_corretor = f"❌ Cliente não concordou com coleta de documentos. Entre em contato."
                            self.enviar_mensagem(corretor_telefone, mensagem_corretor)
                            logger.info(f"✅ Mensagem enviada para corretor: {corretor_telefone}")
                        else:
                            logger.warning(f"⚠️ Não foi possível obter telefone do corretor para: {remetente}")
                            
                    except Exception as e:
                        logger.error(f"❌ Erro ao enviar mensagem para corretor: {e}")
                
                # LOG DETALHADO PARA MANUTENÇÃO
                logger.info(f"📤 Mensagem enviada para colaborador {remetente}: {mensagem_resposta[:50]}...")
                logger.info(f"🔄 Próximo passo definido: {resultado_processamento['proximo_passo']}")
                
                # Após enviar a mensagem de resposta ao colaborador, obter sequência se for início de upload de documento
                if resultado_processamento["acao"] == "iniciar_upload_documento":
                    try:
                        from .buscar_usuarios_supabase import obter_sequencia_coleta_documentos
                        sequencia = obter_sequencia_coleta_documentos()
                        logger.info(f"[DEBUG] Sequência de coleta de documentos obtida para {remetente}: {sequencia}")
                        # Solicitar o primeiro documento da sequência
                        self.solicitar_proximo_documento(remetente)
                    except Exception as e:
                        logger.error(f"❌ Erro ao obter sequência de coleta de documentos: {e}")
                
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
            
            # ✅ REMOVIDO: Captura duplicada - já feita em interpretar_mensagem_usuario
            # A mensagem já foi registrada na linha 533, não precisa duplicar aqui
            
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
                        # MODULARIZADO: Ativar IA especializada temporariamente usando SessionManager
                        resultado_sessao = self.session_manager.criar_sessao_ia_especializada(
                            telefone=remetente,
                            dados_colaborador=None
                        )
                        if resultado_sessao["sucesso"]:
                            self.enviar_mensagem(remetente, "🤖 IA Especializada Ativada!")
                            return self.processar_duvida_colaborador(remetente, mensagem, message_id)
                        else:
                            logger.error(f"❌ Erro ao criar sessão IA durante coleta: {resultado_sessao.get('erro')}")
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
                    
                    # CAPTURA: Resposta da IA para nome válido
                    if self.logging_enabled and self.conversation_logger:
                        try:
                            conversation_id = self.conversation_logger.get_active_conversation_id(remetente)
                            if conversation_id:
                                # Usar add_message_enhanced para evitar duplicação
                                self.conversation_logger.add_message_enhanced(
                                    conversation_id,
                                    "ia",
                                    "corretor", 
                                    mensagem_resposta,
                                    "ia_corretor"
                                )
                        except Exception as e:
                            logger.warning(f"⚠️ Erro na captura de resposta nome: {e}")
                    
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
                    
                    # CAPTURA: Mensagem de erro de nome
                    if self.logging_enabled and self.conversation_logger:
                        try:
                            conversation_id = self.conversation_logger.get_active_conversation_id(remetente)
                            if conversation_id:
                                # Usar add_message_enhanced para evitar duplicação
                                self.conversation_logger.add_message_enhanced(
                                    conversation_id,
                                    "ia",
                                    "corretor",
                                    mensagem_erro,
                                    "ia_corretor"
                                )
                        except Exception as e:
                            logger.warning(f"⚠️ Erro na captura de erro nome: {e}")
                    
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
                    
                    # CAPTURA: Resposta da IA para telefone válido
                    if self.logging_enabled and self.conversation_logger:
                        try:
                            conversation_id = self.conversation_logger.get_active_conversation_id(remetente)
                            if conversation_id:
                                # Usar add_message_enhanced para evitar duplicação
                                self.conversation_logger.add_message_enhanced(
                                    conversation_id,
                                    "ia",
                                    "corretor",
                                    mensagem_final,
                                    "ia_corretor"
                                )
                        except Exception as e:
                            logger.warning(f"⚠️ Erro na captura de resposta telefone: {e}")
                    
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
            
            # CAPTURA: Mensagem de dúvida do colaborador
            if self.logging_enabled and self.conversation_logger:
                try:
                    conversation_id = self.conversation_logger.get_active_conversation_id(remetente)
                    if conversation_id:
                        # Usar add_message_enhanced para evitar duplicação
                        self.conversation_logger.add_message_enhanced(
                            conversation_id,
                            "corretor",
                            "ia",
                            duvida,
                            "ia_corretor"
                        )
                except Exception as e:
                    logger.warning(f"⚠️ Erro na captura de dúvida: {e}")
            
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
                
                # CAPTURA: Resposta da IA para dúvida
                if self.logging_enabled and self.conversation_logger:
                    try:
                        conversation_id = self.conversation_logger.get_active_conversation_id(remetente)
                        if conversation_id:
                            # Usar add_message_enhanced para evitar duplicação
                            self.conversation_logger.add_message_enhanced(
                                conversation_id,
                                "ia",
                                "corretor",
                                resposta_formatada,
                                "ia_corretor"
                            )
                    except Exception as e:
                        logger.warning(f"⚠️ Erro na captura de resposta IA: {e}")
                
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
            corretor_nome = "Corretor"  # Padrão se não encontrar
            
            # Tentar obter nome do corretor do conversation_logger
            try:
                if self.logging_enabled and self.conversation_logger:
                    conv_id = self.conversation_logger.get_active_conversation_id(corretor)
                    if conv_id:
                        # Tentar obter dados do broker da conversa atual
                        participants = self.conversation_logger.get_participants(conv_id)
                        if participants and 'broker' in participants:
                            broker_name = participants['broker'].get('name')
                            if broker_name and isinstance(broker_name, str) and len(broker_name.strip()) > 0:
                                corretor_nome = broker_name.strip()
                                logger.info(f"✅ Nome do corretor obtido do logger: {corretor_nome}")
                
                logger.info(f"📋 Usando nome para corretor: {corretor_nome}")
            except Exception as e:
                logger.warning(f"⚠️ Não foi possível obter nome do corretor: {e}")
                # Mantém o nome padrão em caso de erro
            
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
            
            # ✅ CORREÇÃO: Relacionar telefone do cliente à conversa existente
            if self.logging_enabled and self.conversation_logger:
                try:
                    conv_id = self.conversation_logger.get_active_conversation_id(corretor)
                    if conv_id:
                        # Adicionar telefone do cliente como relacionado
                        self.conversation_logger.add_related_phone(conv_id, verificacao["numero"])
                        logger.info(f"🔗 Telefone do cliente relacionado à conversa: {verificacao['numero']}")
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao relacionar telefone: {e}")
            
            # Enviar mensagem inicial para o cliente
            mensagem_cliente = f"""🏠 *Olá {dados_cliente['nome']}!*

Sou a Bia, assistente virtual da *{self.company_name}*.

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
                    
                    # CAPTURA: Atendimento iniciado com cliente
                    if self.logging_enabled and self.conversation_logger:
                        try:
                            conversation_id = self.conversation_logger.get_active_conversation_id(corretor)
                            if conversation_id:
                                # Atualizar dados do cliente na conversa
                                self.conversation_logger.update_participant_data(
                                    conversation_id,
                                    "client",
                                    {
                                        "name": dados_cliente['nome'],
                                        "phone": verificacao["numero"],
                                        "whatsapp_verified": True
                                    }
                                )
                                
                                # ❌ REMOVIDO: Mensagem do sistema não deve ser salva no JSON
                                # self.conversation_logger.add_message_enhanced(
                                #     conversation_id,
                                #     "system",
                                #     "all",
                                #     f"Atendimento iniciado com cliente {dados_cliente['nome']} - {verificacao['numero']}",
                                #     "ia_cliente"
                                # )
                                
                                # Finalizar conversa de fechamento
                                self.conversation_logger.finalize_conversation(
                                    conversation_id,
                                    "client_contact_initiated"
                                )
                        except Exception as e:
                            logger.warning(f"⚠️ Erro na captura de finalização: {e}")
                    
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
            
            # CAPTURA: Finalizar conversa cancelada
            if self.logging_enabled and self.conversation_logger:
                try:
                    conversation_id = self.conversation_logger.get_active_conversation_id(corretor)
                    if conversation_id:
                        # Usar add_message_enhanced para evitar duplicação
                        self.conversation_logger.add_message_enhanced(
                            conversation_id,
                            "system",
                            "all",
                            "Atendimento cancelado pelo corretor",
                            "ia_corretor"
                        )
                        self.conversation_logger.finalize_conversation(
                            conversation_id, 
                            "cancelled_by_broker"
                        )
                except Exception as e:
                    logger.warning(f"⚠️ Erro na captura de cancelamento: {e}")
            
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

    def _processar_menu_lgpd(self, from_user: str, message_text: str) -> bool:
        """
        Processa as opções do menu LGPD
        
        Args:
            from_user (str): Número do usuário
            message_text (str): Texto da mensagem
            
        Returns:
            bool: True se processou uma opção válida
        """
        
        opcoes_lgpd = {
            "1": "concordo_completo",
            "2": "mais_informacoes", 
            "3": "dados_pessoais",
            "4": "documentos",
            "5": "politica_privacidade"  # Nova opção adicionada
        }
        
        opcao_selecionada = opcoes_lgpd.get(message_text.strip())
        
        if opcao_selecionada == "concordo_completo":
            return self._processar_concordancia_lgpd_sim(from_user)
            
        elif opcao_selecionada == "mais_informacoes":
            return self._processar_concordancia_lgpd_nao(from_user)
            
        elif opcao_selecionada == "dados_pessoais":
            self._enviar_consentimento_dados_pessoais(from_user)
            return True
            
        elif opcao_selecionada == "documentos":
            self._enviar_consentimento_documentos(from_user)
            return True
            
        elif opcao_selecionada == "politica_privacidade":
            self._enviar_politica_privacidade(from_user)
            return True
            
        return False

    def _enviar_politica_privacidade(self, from_user: str):
        """
        Envia a política de privacidade com link dinâmico do Supabase
        
        Args:
            from_user (str): Número do usuário
        """
        try:
            # Buscar política no Supabase usando a instância já criada
            if self.consentimento_service:
                mensagem_politica = self.consentimento_service.gerar_mensagem_politica_privacidade()
            else:
                # Fallback caso o serviço não esteja disponível
                mensagem_politica = self._gerar_politica_fallback()
            
            # Enviar mensagem com política
            self.whatsapp_api.enviar_mensagem(from_user, mensagem_politica)
            
            # Log para acompanhamento
            logger.info(f"📄 Política de privacidade enviada para: {from_user}")
            
            # Aguardar 2 segundos e reenviar menu LGPD diretamente
            import time
            time.sleep(1)
            
            # Chamar diretamente o método enviar_menu_concordancia_dados
            self.menu_service.enviar_menu_concordancia_dados(from_user)
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar política de privacidade: {e}")
            
            # Fallback: enviar link padrão
            mensagem_fallback = f"""📄 **Política de Privacidade - {self.company_name}**

🔗 **Link para acesso**: https://tocaimoveis.com.br/politica-privacidade

Nossa política detalha como tratamos seus dados pessoais conforme a LGPD.

⬅️ *Volte para continuar seu atendimento após a leitura.*"""
            
            self.whatsapp_api.enviar_mensagem(from_user, mensagem_fallback)


    def _gerar_politica_fallback(self) -> str:
        """
        Gera política de privacidade completa como fallback quando ConsentimentoService não está disponível
        
        Returns:
            str: Política de privacidade completa formatada
        """
        return """📄 **Política de Privacidade para Coleta de Dados e Documentos via WhatsApp**

**1. Introdução**
Esta Política de Privacidade tem como objetivo informar como coletamos, utilizamos, armazenamos e protegemos os dados pessoais e documentos enviados por nossos clientes através do WhatsApp, em conformidade com a Lei nº 13.709/2018 (LGPD).

**2. Dados Coletados**
Coletamos informações pessoais e documentos que podem incluir:
• Nome completo
• CPF/RG ou outros documentos de identificação
• Endereço
• Dados de contato (telefone, e-mail, etc.)
• RG ou CNH, comprovantes e outros dados necessários para a prestação dos nossos serviços

**3. Finalidade da Coleta**
Os dados e documentos coletados via WhatsApp serão utilizados exclusivamente para:
• Identificação do cliente
• Análise de informações para prestação de serviços contratados
• Cumprimento de obrigações legais e regulatórias
• Comunicação relacionada aos serviços prestados

**4. Compartilhamento de Dados**
Seus dados poderão ser compartilhados apenas com terceiros necessários para a execução do serviço, sempre observando a confidencialidade e segurança das informações.

**5. Armazenamento e Segurança**
Seus dados e documentos serão armazenados em ambiente seguro e controlado, sendo adotadas medidas técnicas e administrativas para proteger suas informações contra acessos não autorizados, situações acidentais ou ilícitas de destruição, perda, alteração, comunicação ou difusão.

**6. Direitos dos Titulares**
Você pode, a qualquer momento, solicitar:
• Confirmação da existência de tratamento
• Acesso aos seus dados
• Correção de dados incompletos, inexatos ou desatualizados
• Anonimização, bloqueio ou eliminação de dados desnecessários ou excessivos
• Portabilidade dos dados a outro fornecedor de serviço, mediante requisição expressa
• Eliminação dos dados tratados com seu consentimento, exceto nas hipóteses previstas em lei

**7. Contato**
Para exercer seus direitos ou em caso de dúvidas sobre esta Política, entre em contato conosco através do WhatsApp.

**8. Atualizações**
Esta Política pode ser atualizada a qualquer momento para garantir nossa conformidade com a LGPD.

⬅️ *Volte para continuar seu atendimento após a leitura.*"""

    def _processar_coleta_dados(self, mensagem: str, numero_telefone: str, dados_sessao: Dict) -> Dict:
        """
        Processa mensagens durante a coleta de dados
        """
        try:
            # Processar resposta atual
            resultado = self.coleta_dados_service.processar_resposta(
                numero_telefone,
                mensagem
            )
            
            if not resultado['sucesso']:
                return {
                    'sucesso': False,
                    'mensagem': resultado.get('mensagem', 'Erro ao processar dados'),
                    'erro': resultado.get('erro', 'Erro desconhecido')
                }
            
            # Verificar ação necessária
            acao = resultado.get('acao')
            
            # Enviar mensagem de resposta primeiro
            if resultado.get('mensagem'):
                self.whatsapp_api.enviar_mensagem(
                    numero_telefone,
                    resultado['mensagem']
                )
            
            # Se for ação de menu de confirmação de endereço
            if acao == 'enviar_menu_confirmacao_endereco':
                # Aguardar 1 segundo para garantir que a mensagem anterior foi entregue
                time.sleep(2)
                
                # Enviar menu de confirmação
                menu_result = self.menu_service.enviar_menu_confirmacao_endereco(
                    numero_telefone,
                    resultado.get('endereco', '')
                )
                
                if not menu_result['sucesso']:
                    logger.warning(f"⚠️ Erro ao enviar menu de confirmação: {menu_result.get('erro')}")
                    # Fallback: continuar com mensagem de texto
                    self.whatsapp_api.enviar_mensagem(
                        numero_telefone,
                        "Por favor, responda *SIM* se o endereço está correto ou *NÃO* para corrigir."
                    )
            
            return {
                'sucesso': True,
                'mensagem': resultado.get('mensagem', ''),
                'acao': acao
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar coleta de dados: {str(e)}")
            return {
                'sucesso': False,
                'mensagem': 'Erro ao processar sua resposta. Por favor, tente novamente.',
                'erro': str(e)
            }

    def solicitar_proximo_documento(self, remetente: str):
        """
        Solicita o próximo documento da sequência de coleta de documentos
        """
        try:
            from .buscar_usuarios_supabase import obter_sequencia_coleta_documentos
            # Exemplo de controle simples em memória (pode evoluir para banco/sessão)
            if not hasattr(self, '_controle_coleta_documentos'):
                self._controle_coleta_documentos = {}
            # Obter sequência para o usuário (ou inicializar)
            if remetente not in self._controle_coleta_documentos:
                sequencia = obter_sequencia_coleta_documentos()
                self._controle_coleta_documentos[remetente] = {
                    'sequencia': sequencia,
                    'indice_atual': 0,
                    'documentos_recebidos': []
                }
            controle = self._controle_coleta_documentos[remetente]
            sequencia = controle['sequencia']
            indice = controle['indice_atual']
            # Verificar se ainda há documentos a solicitar
            if indice < len(sequencia):
                doc = sequencia[indice]
                nome = doc.get('name', 'Documento')
                descricao = doc.get('description', '')
                
                # NOVO: Mensagem com informação sobre tempo de espera
                mensagem = f"📄 *{nome}*\n"
                if descricao:
                    mensagem += f"📝 {descricao}\n\n"
                
                mensagem += "📤 Envie os arquivos deste documento.\n"
                mensagem += "⏰ Aguardarei 1 minuto antes de continuar."
                
                self.enviar_mensagem(remetente, mensagem)
                logger.info(f"Solicitado documento '{nome}' para {remetente} (etapa {indice+1}/{len(sequencia)})")
            else:
                # ✅ NOVO: FINALIZAÇÃO COMPLETA - TODOS OS DOCUMENTOS ENVIADOS
                self.enviar_mensagem(remetente, "✅ Todos os documentos foram enviados!")
                logger.info(f"Sequência de coleta finalizada para {remetente}")
                
                # ✅ NOVO: FINALIZAR PROCESSO COMPLETO
                try:
                    from .coleta_dados_service import ColetaDadosService
                    coleta_service = ColetaDadosService()
                    
                    # Buscar negotiation_id (pode ser armazenado na sessão)
                    negotiation_id = self._obter_negotiation_id_do_cliente(remetente)
                    
                    if negotiation_id:
                        logger.info(f"🔍 Negotiation ID encontrado para finalização: {negotiation_id}")
                        resultado_finalizacao = coleta_service.finalizar_processo_completo(remetente, negotiation_id)
                        
                        if resultado_finalizacao['sucesso']:
                            logger.info(f"🎉 Processo completo finalizado com sucesso: {remetente}")
                            logger.info(f" {resultado_finalizacao['mensagens_sincronizadas']} mensagens sincronizadas")
                        else:
                            logger.error(f"❌ Erro na finalização completa: {resultado_finalizacao['erro']}")
                    else:
                        logger.warning(f"⚠️ Negotiation ID não encontrado para finalização: {remetente}")
                        logger.warning(f"⚠️ Tentando buscar dados da sessão de coleta...")
                        
                        # Tentar obter da sessão de coleta diretamente
                        dados_sessao = coleta_service.obter_dados_sessao(remetente)
                        if dados_sessao and hasattr(dados_sessao, 'negotiation_id') and dados_sessao.negotiation_id:
                            logger.info(f"✅ Negotiation ID encontrado na sessão: {dados_sessao.negotiation_id}")
                            resultado_finalizacao = coleta_service.finalizar_processo_completo(remetente, dados_sessao.negotiation_id)
                            
                            if resultado_finalizacao['sucesso']:
                                logger.info(f"🎉 Processo completo finalizado com sucesso: {remetente}")
                                logger.info(f" {resultado_finalizacao['mensagens_sincronizadas']} mensagens sincronizadas")
                            else:
                                logger.error(f"❌ Erro na finalização completa: {resultado_finalizacao['erro']}")
                        else:
                            logger.error(f"❌ Negotiation ID não encontrado em nenhum local para {remetente}")
                        
                except Exception as e:
                    logger.error(f"❌ Erro ao finalizar processo completo: {e}")
                
                # Limpar controle de coleta
                if remetente in self._controle_coleta_documentos:
                    del self._controle_coleta_documentos[remetente]
                    
        except Exception as e:
            logger.error(f"❌ Erro ao solicitar próximo documento para {remetente}: {e}")
    
    def _obter_negotiation_id_do_cliente(self, telefone_cliente: str) -> Optional[str]:
        """
        ✅ MELHORADO: Obtém o negotiation_id do cliente com múltiplos fallbacks
        """
        try:
            # 1. Buscar na sessão de coleta
            from .coleta_dados_service import ColetaDadosService
            coleta_service = ColetaDadosService()
            dados_sessao = coleta_service.obter_dados_sessao(telefone_cliente)
            
            if dados_sessao and hasattr(dados_sessao, 'negotiation_id') and dados_sessao.negotiation_id:
                logger.info(f"✅ Negotiation ID encontrado na sessão: {dados_sessao.negotiation_id}")
                return dados_sessao.negotiation_id
            
            # 2. Fallback: buscar pelo telefone no banco
            from .document_uploader import get_negotiation_id_by_phone
            negotiation_id = get_negotiation_id_by_phone(telefone_cliente)
            
            if negotiation_id:
                logger.info(f"✅ Negotiation ID encontrado via fallback: {negotiation_id}")
                return negotiation_id
            
            # 3. Fallback: buscar na sessão ativa do WhatsApp
            sessao_ativa = self.sessoes_ativas.get(telefone_cliente, {})
            if sessao_ativa.get('negotiation_id'):
                logger.info(f"✅ Negotiation ID encontrado na sessão WhatsApp: {sessao_ativa['negotiation_id']}")
                return sessao_ativa['negotiation_id']
            
            # 4. Fallback: buscar diretamente no banco por telefone mais recente
            try:
                from src.services.buscar_usuarios_supabase import obter_cliente_supabase
                supabase = obter_cliente_supabase()
                
                # Buscar negociação mais recente pelo telefone do cliente
                # Tentar diferentes campos possíveis
                result = supabase.table('ai_negotiations').select('id, client_phone, client_id').order('created_at', desc=True).limit(10).execute()
                
                # Filtrar pelo telefone
                for neg in result.data:
                    if neg.get('client_phone') == telefone_cliente:
                        negotiation_id = neg['id']
                        logger.info(f"✅ Negotiation ID encontrado no banco: {negotiation_id}")
                        return negotiation_id
            except Exception as e:
                logger.warning(f"⚠️ Erro ao buscar negotiation_id no banco: {e}")
            
            logger.warning(f"⚠️ Negotiation ID não encontrado para {telefone_cliente}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter negotiation ID: {e}")
            return None

    def baixar_e_salvar_documento(
        self,
        media_key: str,
        direct_path: str,
        tipo: str,
        mimetype: str,
        file_name: str,
        remetente: str,
        indice: int = None,
        pasta_destino: str = "Clientes/Documentos"
    ) -> str:
        """
        Baixa o arquivo da W-API e salva na pasta destino.
        Retorna o caminho do arquivo salvo ou None em caso de erro.
        """
        try:
            # 1. Montar o payload e headers
            instance_id = os.getenv('W_API_INSTANCE_ID')
            w_api_token = os.getenv('W_API_TOKEN')
            if not instance_id or not w_api_token:
                logger.error("❌ Variáveis de ambiente W_API_INSTANCE_ID ou W_API_TOKEN não configuradas.")
                return None
            url = f"https://api.w-api.app/v1/message/download-media?instanceId={instance_id}"
            headers = {
                "Authorization": f"Bearer {w_api_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "mediaKey": media_key,
                "directPath": direct_path,
                "type": tipo,
                "mimetype": mimetype
            }
            # 2. Fazer POST para a API de download
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                logger.error(f"❌ Erro ao requisitar download-media: {response.status_code} - {response.text}")
                return None
            data = response.json()
            if data.get("error") or not data.get("fileLink"):
                logger.error(f"❌ Erro na resposta da API de download-media: {data}")
                return None
            file_link = data["fileLink"]
            # 3. Baixar o arquivo do fileLink
            file_response = requests.get(file_link)
            if file_response.status_code != 200:
                logger.error(f"❌ Erro ao baixar arquivo: {file_response.status_code}")
                return None
            # 4. Garantir que a pasta existe
            os.makedirs(pasta_destino, exist_ok=True)
            # 5. Montar nome do arquivo
            timestamp = int(time.time())
            ext = os.path.splitext(file_name)[1] or ".bin"
            nome_base = os.path.splitext(file_name)[0][:30].replace(" ", "_")
            nome_arquivo = f"{remetente}_{indice or ''}_{nome_base}_{timestamp}{ext}"
            caminho_arquivo = os.path.join(pasta_destino, nome_arquivo)
            # 6. Salvar o arquivo
            with open(caminho_arquivo, "wb") as f:
                f.write(file_response.content)
            logger.info(f"✅ Arquivo salvo em: {caminho_arquivo}")
            # NOVO: Upload automático para Supabase
            try:
                negotiation_id = self.sessoes_ativas.get(remetente, {}).get('negotiation_id')
                
                # FALLBACK: Se não encontrar na sessão, busca pelo telefone
                if not negotiation_id:
                    logger.info(f"[UPLOAD SUPABASE] negotiation_id não encontrado na sessão para {remetente}, buscando pelo telefone...")
                    from src.services.document_uploader import get_negotiation_id_by_phone
                    negotiation_id = get_negotiation_id_by_phone(remetente)
                    if negotiation_id:
                        logger.info(f"[UPLOAD SUPABASE] ✅ negotiation_id encontrado via fallback: {negotiation_id}")
                    else:
                        logger.warning(f"[UPLOAD SUPABASE] ❌ negotiation_id não encontrado nem na sessão nem pelo telefone para {remetente}")
                
                if hasattr(self, '_controle_coleta_documentos') and remetente in self._controle_coleta_documentos:
                    indice = self._controle_coleta_documentos[remetente]['indice_atual']
                    sequencia = self._controle_coleta_documentos[remetente]['sequencia']
                    if indice < len(sequencia):
                        document_type_id = sequencia[indice]['id']
                    else:
                        document_type_id = None
                else:
                    document_type_id = None
                if negotiation_id and document_type_id:
                    from src.services.coleta_dados_service import upload_documento_supabase
                    resultado_upload = upload_documento_supabase(
                        file_path=caminho_arquivo,
                        negotiation_id=negotiation_id,
                        document_type_id=document_type_id
                    )
                    logger.info(f"[UPLOAD SUPABASE] Resultado: {resultado_upload}")
                else:
                    logger.warning(f"[UPLOAD SUPABASE] negotiation_id ou document_type_id não encontrado para {remetente}")
            except Exception as e:
                logger.error(f"[UPLOAD SUPABASE] Erro ao tentar upload automático: {e}")
            return caminho_arquivo
        except Exception as e:
            logger.error(f"❌ Erro ao baixar/salvar documento: {e}")
            return None
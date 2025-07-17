"""
Módulo ConversationLogger - Sistema de Captura de Conversas (V2)
================================================================

VERSÃO 2.0 - MELHORIAS INCREMENTAIS:
- ✅ Classificação específica de sender/receiver
- ✅ Fases de conversa separadas  
- ✅ Contexto melhorado
- ✅ 100% compatível com código existente
- ✅ NOVO: Sincronização com Supabase

Responsável por capturar, estruturar e salvar todas as conversas entre:
- IA ↔ Cliente  
- IA ↔ Corretor

Funcionalidades:
- Captura em tempo real
- Classificação automática ESPECÍFICA
- Salvamento em JSON estruturado com FASES
- Sincronização com Supabase (ai_conversations)
- Gestão de arquivos por tipo
- Integração não-invasiva
- RETROCOMPATIBILIDADE total

Autor: Sistema IA Toca Imóveis
Data:  Julho/2025 - V2.0
"""

import os
import json
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

# Configuração de logging
logger = logging.getLogger(__name__)

class ConversationLogger:
    """
    Sistema profissional de captura de conversas V2.0
    
    MELHORIAS V2:
    - Classificação específica (ia_corretor, ia_cliente, corretor, cliente)
    - Fases de conversa separadas
    - Contexto melhorado
    - Detecção automática de tipo de interação
    - Estrutura preparada para Supabase
    - NOVO: Sincronização automática com Supabase
    
    Gerencia todo o ciclo de vida das conversas:
    1. Criação de nova conversa
    2. Captura de mensagens em tempo real
    3. Classificação automática (dúvidas/fechamento)
    4. Salvamento estruturado em JSON
    5. Sincronização com Supabase
    6. Movimentação entre pastas conforme status
    """
    
    def __init__(self, base_path: str = "conversations_logs"):
        """
        Inicializa o ConversationLogger V2
        
        Args:
            base_path (str): Caminho base para salvamento dos JSONs
        """
        self.base_path = Path(base_path)
        self.enabled = True
        self.active_conversations = {}  # Cache de conversas ativas
        
        # Garantir que as pastas existem
        self._ensure_directories()
        
        logger.info("🗂️ ConversationLogger V2.0 inicializado com melhorias + Supabase")
    
    def _ensure_directories(self):
        """Garante que todas as pastas necessárias existem"""
        directories = [
            self.base_path / "em_andamento",
            self.base_path / "finalizadas", 
            self.base_path / "duvidas"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            
        logger.info("📁 Estrutura de pastas verificada")
    
    def start_conversation(self, 
                          phone_number: str,
                          conversation_type: str,
                          participant_data: Dict[str, Any]) -> str:
        """
        Inicia uma nova conversa e retorna o ID único
        
        Args:
            phone_number (str): Número do telefone do participante
            conversation_type (str): "duvidas" ou "em_andamento"
            participant_data (dict): Dados de quem iniciou (corretor/cliente)
            
        Returns:
            str: ID único da conversa
        """
        try:
            # Gerar ID único
            conversation_id = f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
            
            # ✅ ESTRUTURA MELHORADA V2 - Mantendo compatibilidade
            conversation_data = {
                "conversation_info": {
                    "id": conversation_id,
                    "type": conversation_type,
                    "status": "active",
                    "start_time": datetime.now().isoformat(),
                    "last_updated": datetime.now().isoformat(),
                    "phone_number": phone_number,
                    # ✅ NOVOS CAMPOS V2
                    "version": "2.0",
                    "current_phase": "ia_corretor",  # Fase atual da conversa
                    "business_context": "rental_process"
                },
                "participants": {
                    "broker": participant_data,
                    "client": None,
                    "ai": {
                        "name": "IA Toca Imóveis",
                        "version": "1.0",
                        "model": "gpt-4o-mini"
                    }
                },
                "conversation_summary": {
                    "total_messages": 0,
                    "ai_messages": 0,
                    "user_messages": 0,
                    "duration_seconds": 0,
                    "classification_changes": [],
                    # ✅ NOVOS CAMPOS V2
                    "phases_count": 1,
                    "specific_interactions": {
                        "ia_corretor": 0,
                        "ia_cliente": 0,
                        "corretor_ia": 0,
                        "cliente_ia": 0
                    }
                },
                "messages": [],  # ✅ MANTIDO para compatibilidade
                # ✅ NOVA ESTRUTURA V2 - Fases separadas
                "conversation_phases": {
                    "current": "ia_corretor",
                    "phases": {
                        "ia_corretor": {
                            "started_at": datetime.now().isoformat(),
                            "ended_at": None,
                            "message_count": 0,
                            "classification": conversation_type,
                            "messages": []  # Mensagens específicas desta fase
                        }
                    }
                },
                "metadata": {
                    "platform": "whatsapp",
                    "system_version": "2.0",
                    "created_by": "conversation_logger_v2",
                    # ✅ NOVOS METADADOS V2
                    "improvements": ["specific_classification", "phase_separation", "context_awareness"],
                    "supabase_ready": True
                }
            }
            
            # Armazenar no cache
            self.active_conversations[conversation_id] = conversation_data
            
            # Salvar arquivo inicial
            self._save_conversation(conversation_id, conversation_type)
            
            logger.info(f"🆕 Nova conversa V2 iniciada: {conversation_id} (tipo: {conversation_type}, fase: ia_corretor)")
            return conversation_id
            
        except Exception as e:
            logger.error(f"❌ Erro ao iniciar conversa: {str(e)}")
            return None
    
    def log_message(self, 
                   conversation_id: str,
                   sender: str,
                   content: str,
                   message_type: str = "text",
                   metadata: Dict[str, Any] = None) -> bool:
        """
        Registra uma nova mensagem na conversa com classificação melhorada
        
        Args:
            conversation_id (str): ID da conversa
            sender (str): Quem enviou ("cliente", "corretor", "ia", "user", "assistant")
            content (str): Conteúdo da mensagem
            message_type (str): Tipo da mensagem
            metadata (dict): Metadados adicionais
            
        Returns:
            bool: True se registrou com sucesso
        """
        try:
            if not self.enabled or conversation_id not in self.active_conversations:
                return False
            
            conversation = self.active_conversations[conversation_id]
            
            # ✅ MELHORAR CLASSIFICAÇÃO V2 - Manter compatibilidade
            specific_sender, specific_receiver = self._classify_interaction_v2(
                sender, conversation
            )
            
            # ✅ ESTRUTURA DE MENSAGEM MELHORADA V2
            message = {
                "id": f"msg_{len(conversation['messages']) + 1:03d}",
                "timestamp": datetime.now().isoformat(),
                # ✅ COMPATIBILIDADE: Manter campo original
                "sender": sender,
                "content": content,
                "message_type": message_type,
                "metadata": metadata or {},
                # ✅ NOVOS CAMPOS V2 - Classificação específica
                "sender_specific": specific_sender,
                "receiver_specific": specific_receiver,
                "interaction_type": f"{specific_sender}_{specific_receiver}",
                "phase": conversation["conversation_info"]["current_phase"]
            }
            
            # ✅ ADICIONAR às duas estruturas (compatibilidade + melhoria)
            conversation["messages"].append(message)  # Original
            
            # ✅ ADICIONAR à fase específica
            current_phase = conversation["conversation_info"]["current_phase"]
            if current_phase in conversation["conversation_phases"]["phases"]:
                conversation["conversation_phases"]["phases"][current_phase]["messages"].append(message)
                conversation["conversation_phases"]["phases"][current_phase]["message_count"] += 1
            
            # ✅ ATUALIZAR ESTATÍSTICAS MELHORADAS
            conversation["conversation_summary"]["total_messages"] += 1
            
            # Estatísticas originais (compatibilidade)
            if sender == "ia" or sender == "assistant":
                conversation["conversation_summary"]["ai_messages"] += 1
            else:
                conversation["conversation_summary"]["user_messages"] += 1
            
            # ✅ NOVAS ESTATÍSTICAS V2
            interaction_key = f"{specific_sender}_{specific_receiver}"
            if interaction_key in ["ia_corretor", "ia_cliente", "corretor_ia", "cliente_ia"]:
                conversation["conversation_summary"]["specific_interactions"][interaction_key] += 1
            
            conversation["conversation_info"]["last_updated"] = datetime.now().isoformat()
            
            # Salvar atualização
            conversation_type = conversation["conversation_info"]["type"]
            self._save_conversation(conversation_id, conversation_type)
            
            logger.info(f"💬 Mensagem V2 registrada: {conversation_id} ({specific_sender}→{specific_receiver})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao registrar mensagem: {str(e)}")
            return False
    
    def _classify_interaction_v2(self, original_sender: str, conversation: Dict) -> tuple:
        """
        ✅ NOVO V2: Classifica de forma específica quem está falando com quem
        
        Args:
            original_sender (str): Sender original do sistema
            conversation (Dict): Dados da conversa
            
        Returns:
            tuple: (sender_specific, receiver_specific)
        """
        current_phase = conversation["conversation_info"]["current_phase"]
        
        # Mapeamento inteligente baseado no contexto
        if original_sender in ["user"]:
            if current_phase == "ia_corretor":
                return ("corretor", "ia")
            elif current_phase == "ia_cliente":
                # NOVO: Garantir que mensagens do cliente são classificadas corretamente
                return ("cliente", "ia")
            else:
                return ("corretor", "ia")  # Default para compatibilidade
                
        elif original_sender in ["assistant", "ia"]:
            if current_phase == "ia_corretor":
                return ("ia", "corretor")
            elif current_phase == "ia_cliente":
                return ("ia", "cliente")
            else:
                return ("ia", "corretor")  # Default para compatibilidade
                
        elif original_sender == "system":
            return ("system", "all")
            
        elif original_sender == "corretor":
            return ("corretor", "ia")
            
        elif original_sender == "cliente":
            # NOVO: Garantir classificação cliente_ia
            return ("cliente", "ia")
            
        else:
            # Fallback para tipos não mapeados
            return (original_sender, "unknown")
    
    def transition_phase(self, conversation_id: str, new_phase: str, reason: str = "automatic") -> bool:
        """
        ✅ NOVO V2: Gerencia transição entre fases da conversa
        
        Args:
            conversation_id (str): ID da conversa
            new_phase (str): Nova fase ("ia_cliente", "ia_corretor")
            reason (str): Motivo da transição
            
        Returns:
            bool: True se transição foi bem-sucedida
        """
        try:
            if conversation_id not in self.active_conversations:
                return False
            
            conversation = self.active_conversations[conversation_id]
            old_phase = conversation["conversation_info"]["current_phase"]
            
            if old_phase == new_phase:
                return True  # Já está na fase correta
            
            # Finalizar fase atual
            if old_phase in conversation["conversation_phases"]["phases"]:
                conversation["conversation_phases"]["phases"][old_phase]["ended_at"] = datetime.now().isoformat()
            
            # Iniciar nova fase
            conversation["conversation_info"]["current_phase"] = new_phase
            conversation["conversation_phases"]["current"] = new_phase
            
            if new_phase not in conversation["conversation_phases"]["phases"]:
                conversation["conversation_phases"]["phases"][new_phase] = {
                    "started_at": datetime.now().isoformat(),
                    "ended_at": None,
                    "message_count": 0,
                    "classification": conversation["conversation_info"]["type"],
                    "messages": []
                }
                conversation["conversation_summary"]["phases_count"] += 1
            
            # Registrar transição
            conversation["conversation_summary"]["classification_changes"].append({
                "timestamp": datetime.now().isoformat(),
                "from_phase": old_phase,
                "to_phase": new_phase,
                "reason": reason,
                "type": "phase_transition"
            })
            
            conversation["conversation_info"]["last_updated"] = datetime.now().isoformat()
            
            # Salvar atualização
            conversation_type = conversation["conversation_info"]["type"]
            self._save_conversation(conversation_id, conversation_type)
            
            logger.info(f"🔄 Transição de fase: {conversation_id} ({old_phase} → {new_phase}) - {reason}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro na transição de fase: {str(e)}")
            return False
    
    def finalize_conversation(self, conversation_id: str, finalization_reason: str = "completed") -> bool:
        """
        Finaliza uma conversa e move para pasta apropriada
        
        Args:
            conversation_id (str): ID da conversa
            finalization_reason (str): Motivo da finalização
            
        Returns:
            bool: True se finalizou com sucesso
        """
        try:
            if conversation_id not in self.active_conversations:
                return False
            
            conversation = self.active_conversations[conversation_id]
            conversation_type = conversation["conversation_info"]["type"]
            current_phase = conversation["conversation_info"]["current_phase"]
            
            # NOVO: Não finalizar se apenas iniciou contato com cliente
            if finalization_reason == "client_contact_initiated" and current_phase == "ia_cliente":
                # Apenas atualizar status e manter em andamento
                conversation["conversation_info"]["last_updated"] = datetime.now().isoformat()
                self._save_conversation(conversation_id, "em_andamento")
                return True
            
            # Atualizar dados de finalização
            conversation["conversation_info"]["status"] = "completed"
            conversation["conversation_info"]["end_time"] = datetime.now().isoformat()
            conversation["conversation_info"]["finalization_reason"] = finalization_reason
            
            # Calcular duração
            start_time = datetime.fromisoformat(conversation["conversation_info"]["start_time"])
            end_time = datetime.now()
            duration_seconds = (end_time - start_time).total_seconds()
            conversation["conversation_summary"]["duration_seconds"] = duration_seconds
            
            # Mover para pasta apropriada
            if conversation_type == "em_andamento":
                # Fechamento completo - move para finalizadas
                self._save_conversation(conversation_id, "finalizadas")
                
                # Remover da pasta em_andamento
                old_file = os.path.join(self.base_path, "em_andamento", f"{conversation_id}.json")
                if os.path.exists(old_file):
                    os.remove(old_file)
                
            elif conversation_type == "duvidas":
                # Dúvida resolvida - permanece em duvidas
                self._save_conversation(conversation_id, "duvidas")
            
            # Remover da memória ativa
            del self.active_conversations[conversation_id]
            
            logger.info(f"✅ Conversa finalizada: {conversation_id} (Motivo: {finalization_reason})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao finalizar conversa: {str(e)}")
            return False
    
    def _save_conversation(self, conversation_id: str, folder: str) -> bool:
        """
        Salva a conversa no arquivo JSON
        
        Args:
            conversation_id (str): ID da conversa
            folder (str): Pasta de destino
            
        Returns:
            bool: True se salvou com sucesso
        """
        try:
            logger.info(f"💾 Iniciando salvamento: {conversation_id} → {folder}/")
            
            if conversation_id not in self.active_conversations:
                logger.warning(f"⚠️ Conversa não encontrada para salvar: {conversation_id}")
                return False
            
            conversation_data = self.active_conversations[conversation_id]
            
            # 🔥 LOG: Estado dos participants antes do salvamento
            logger.info(f"📊 Participants no momento do salvamento: {conversation_data.get('participants', {})}")
            
            # Determinar caminho do arquivo
            filename = f"{conversation_id}.json"
            filepath = self.base_path / folder / filename
            
            logger.info(f"📁 Salvando em: {filepath}")
            
            # Salvar arquivo
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(conversation_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Conversa salva com sucesso: {conversation_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao salvar conversa: {str(e)}")
            return False
    
    def is_enabled(self) -> bool:
        """Verifica se o logging está ativo"""
        return self.enabled
    
    def update_conversation_type(self, conversation_id: str, new_type: str) -> bool:
        """
        Atualiza o tipo de conversa (duvidas ou fechamento)
        
        Args:
            conversation_id (str): ID da conversa
            new_type (str): Novo tipo ("duvidas" ou "fechamento")
            
        Returns:
            bool: True se atualizou com sucesso
        """
        try:
            if conversation_id not in self.active_conversations:
                return False
            
            conversation = self.active_conversations[conversation_id]
            old_type = conversation["conversation_info"]["type"]
            conversation["conversation_info"]["type"] = new_type
            conversation["conversation_info"]["last_updated"] = datetime.now().isoformat()
            
            # Registrar mudança de classificação
            conversation["conversation_summary"]["classification_changes"].append({
                "timestamp": datetime.now().isoformat(),
                "from_type": old_type,
                "to_type": new_type,
                "reason": "menu_selection"
            })
            
            # Salvar atualização
            self._save_conversation(conversation_id, new_type)
            
            logger.info(f"🔄 Tipo de conversa atualizado: {conversation_id} ({old_type} → {new_type})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar tipo de conversa: {str(e)}")
            return False
    
    def update_participant_data(self, 
                               conversation_id: str,
                               participant_type: str,
                               participant_data: Dict[str, Any]) -> bool:
        """
        Atualiza dados de um participante da conversa
        
        Args:
            conversation_id (str): ID da conversa
            participant_type (str): "client" ou "broker"
            participant_data (dict): Dados do participante
            
        Returns:
            bool: True se atualizou com sucesso
        """
        try:
            logger.info(f"📝 Iniciando atualização de dados: {conversation_id} - {participant_type}")
            logger.info(f"🔍 Dados a serem atualizados: {participant_data}")
            
            if conversation_id not in self.active_conversations:
                logger.warning(f"⚠️ Conversa não encontrada na memória: {conversation_id}")
                return False
            
            conversation = self.active_conversations[conversation_id]
            
            # 🔥 LOG: Estado antes da atualização
            logger.info(f"📊 Estado anterior do {participant_type}: {conversation['participants'].get(participant_type, 'NÃO EXISTE')}")
            
            conversation["participants"][participant_type] = participant_data
            conversation["conversation_info"]["last_updated"] = datetime.now().isoformat()
            
            # 🔥 LOG: Estado após atualização
            logger.info(f"✅ Estado atualizado do {participant_type}: {conversation['participants'][participant_type]}")
            
            # Salvar atualização
            conversation_type = conversation["conversation_info"]["type"]
            save_success = self._save_conversation(conversation_id, conversation_type)
            
            if save_success:
                logger.info(f"👤 Dados do {participant_type} atualizados e salvos: {conversation_id}")
                return True
            else:
                logger.error(f"❌ Falha ao salvar dados do {participant_type}: {conversation_id}")
                return False
            
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar participante: {str(e)}")
            return False
    
    def get_conversation_stats(self) -> Dict[str, Any]:
        """
        Retorna estatísticas das conversas
        
        Returns:
            dict: Estatísticas das conversas
        """
        try:
            stats = {
                "active_conversations": len(self.active_conversations),
                "conversations_by_type": {},
                "total_messages": 0
            }
            
            # Contar por tipo
            for conv in self.active_conversations.values():
                conv_type = conv["conversation_info"]["type"]
                if conv_type not in stats["conversations_by_type"]:
                    stats["conversations_by_type"][conv_type] = 0
                stats["conversations_by_type"][conv_type] += 1
                stats["total_messages"] += len(conv["messages"])
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter estatísticas: {str(e)}")
            return {}
    
    def add_related_phone(self, conversation_id: str, phone_number: str) -> bool:
        """
        ✅ NOVO: Adiciona telefone relacionado à conversa
        
        Args:
            conversation_id (str): ID da conversa
            phone_number (str): Telefone a ser relacionado
            
        Returns:
            bool: True se adicionou com sucesso
        """
        try:
            if conversation_id not in self.active_conversations:
                return False
            
            conversation = self.active_conversations[conversation_id]
            
            # Criar array de telefones relacionados se não existir
            if "related_phones" not in conversation["conversation_info"]:
                conversation["conversation_info"]["related_phones"] = []
            
            # Adicionar telefone se não existir
            if phone_number not in conversation["conversation_info"]["related_phones"]:
                conversation["conversation_info"]["related_phones"].append(phone_number)
                conversation["conversation_info"]["last_updated"] = datetime.now().isoformat()
                
                # Salvar conversa atualizada
                conversation_type = conversation["conversation_info"]["type"]
                self._save_conversation(conversation_id, conversation_type)
                
                logger.info(f"🔗 Telefone relacionado adicionado: {phone_number} → {conversation_id}")
                return True
            
            return True  # Já existe
            
        except Exception as e:
            logger.error(f"❌ Erro ao adicionar telefone relacionado: {e}")
            return False

    def add_message_enhanced(self, conversation_id: str, sender: str, receiver: str, content: str, phase: str = None) -> bool:
        """
        ✅ MÉTODO PRINCIPAL: Registra mensagem com classificação específica
        
        Args:
            conversation_id (str): ID da conversa
            sender (str): Quem envia ("ia", "corretor", "cliente")
            receiver (str): Quem recebe ("ia", "corretor", "cliente") 
            content (str): Conteúdo da mensagem
            phase (str): Fase específica (opcional)
            
        Returns:
            bool: True se adicionou com sucesso
        """
        try:
            # Se fase especificada, fazer transição se necessário
            if phase and conversation_id in self.active_conversations:
                current_phase = self.active_conversations[conversation_id]["conversation_info"]["current_phase"]
                if current_phase != phase:
                    self.transition_phase(conversation_id, phase, "explicit_phase_change")
            
            # Usar log_message com sender específico
            metadata = {
                "receiver_explicit": receiver,
                "enhanced_method": True
            }
            
            return self.log_message(conversation_id, sender, content, "text", metadata)
            
        except Exception as e:
            logger.error(f"❌ Erro no add_message_enhanced: {str(e)}")
            return False
    
    def get_active_conversation_id(self, phone_number: str) -> Optional[str]:
        """
        Retorna o ID da conversa ativa para um telefone
        
        Args:
            phone_number (str): Número do telefone
            
        Returns:
            str: ID da conversa ou None se não encontrar
        """
        try:
            for conv_id, conv_data in self.active_conversations.items():
                if conv_data["conversation_info"]["phone_number"] == phone_number:
                    return conv_id
            return None
        except Exception as e:
            logger.error(f"❌ Erro ao buscar conversa ativa: {e}")
            return None
    
    def sincronizar_conversa_supabase(self, conversation_id: str, negotiation_id: str) -> Dict[str, Any]:
        """
        ✅ NOVO V2: Sincroniza conversa do JSON para Supabase
        
        Esta função é chamada após a criação da negociação para sincronizar
        todas as mensagens da conversa com a tabela ai_conversations do Supabase.
        
        Args:
            conversation_id (str): ID da conversa no JSON
            negotiation_id (str): ID da negociação no Supabase
            
        Returns:
            Dict: Resultado da sincronização
        """
        try:
            logger.info(f"🔄 Iniciando sincronização: {conversation_id} → {negotiation_id}")
            
            # 1. Buscar conversa (primeiro na memória, depois no arquivo)
            conversation = None
            
            # Tentar buscar na memória primeiro
            if conversation_id in self.active_conversations:
                conversation = self.active_conversations[conversation_id]
                logger.info(f"📋 Conversa encontrada na memória: {conversation_id}")
            else:
                # Buscar no arquivo (finalizadas ou em_andamento)
                conversation = self._carregar_conversa_do_arquivo(conversation_id)
                if conversation:
                    logger.info(f"📁 Conversa carregada do arquivo: {conversation_id}")
            
            if not conversation:
                return {
                    'sucesso': False,
                    'erro': 'Conversa não encontrada na memória nem no arquivo',
                    'mensagens_sincronizadas': 0
                }
            
            # 2. Importar Supabase
            try:
                from src.services.buscar_usuarios_supabase import obter_cliente_supabase
                supabase = obter_cliente_supabase()
            except Exception as e:
                logger.error(f"❌ Erro ao conectar Supabase: {e}")
                return {
                    'sucesso': False,
                    'erro': f'Erro conexão Supabase: {str(e)}',
                    'mensagens_sincronizadas': 0
                }
            
            # 3. Extrair mensagens de todas as fases
            mensagens_para_sincronizar = []
            mensagens_processadas = set()  # Para evitar duplicação por ID
            
            # Usar APENAS o array principal 'messages' (já contém todas as mensagens)
            if 'messages' in conversation:
                for msg in conversation['messages']:
                    # Verificar se já foi sincronizada e se não é duplicada
                    msg_id = msg.get('id', f"msg_{msg.get('timestamp', 'unknown')}")
                    if not msg.get('supabase_synced', False) and msg_id not in mensagens_processadas:
                        mensagens_para_sincronizar.append(msg)
                        mensagens_processadas.add(msg_id)
            
            logger.info(f"📊 Encontradas {len(mensagens_para_sincronizar)} mensagens únicas para sincronizar")
            
            # 4. Preparar dados para inserção
            conversas_supabase = []
            
            for msg in mensagens_para_sincronizar:
                # Mapear sender do JSON para formato Supabase - CORRIGIDO
                sender_mapping = {
                    'ia': 'ia',
                    'corretor': 'corretor',
                    'cliente': 'cliente',
                    'system': 'sistema',  # Corrigido: system -> sistema
                    'user': 'cliente',    # Compatibilidade
                    'assistant': 'ia'     # Compatibilidade
                }
                
                # Determinar conversation_type baseado no PHASE da mensagem (correção principal)
                msg_phase = msg.get('phase', msg.get('interaction_type', 'ia_cliente'))
                
                if msg_phase in ['ia_corretor', 'corretor_ia']:
                    conversation_type = 'ia_corretor'
                elif msg_phase in ['ia_cliente', 'cliente_ia']:
                    conversation_type = 'ia_cliente'
                else:
                    # Fallback para compatibilidade
                    sender_original = msg.get('sender', msg.get('role', 'unknown'))
                    if sender_original in ['user', 'cliente_ia'] or 'cliente' in sender_original:
                        conversation_type = 'ia_cliente'
                    else:
                        conversation_type = 'ia_cliente'  # Default seguro
                
                # CORREÇÃO 1: Usar sender_specific quando disponível para classificação correta
                sender_original = msg.get('sender_specific', msg.get('sender', msg.get('role', 'unknown')))
                sender_supabase = sender_mapping.get(sender_original, sender_original)
                
                # Preparar dados da conversa
                conversa_data = {
                    "negotiation_id": negotiation_id,
                    "conversation_type": conversation_type,  # Agora baseado no phase
                    "sender": sender_supabase,
                    "message": self._limpar_formatacao_mensagem(msg.get('content', msg.get('message', ''))),  # Limpar asteriscos
                    "metadata": {
                        "conversation_id": conversation_id,
                        "sender_original": sender_original,
                        "timestamp_original": msg.get('timestamp', datetime.now().isoformat()),
                        "message_type": msg.get('message_type', 'text'),
                        "phase": msg_phase,
                        "interaction_type": msg.get('interaction_type', 'unknown'),
                        "sync_timestamp": datetime.now().isoformat(),
                        "msg_id": msg.get('id', 'unknown')
                    }
                }
                
                # Adicionar timestamp se disponível
                if 'timestamp' in msg:
                    conversa_data['timestamp'] = msg['timestamp']
                
                conversas_supabase.append(conversa_data)
            
            # CORREÇÃO 3: Filtrar duplicatas baseado em content + sender + timestamp
            conversas_unicas = []
            mensagens_vistas = set()
            
            for conversa in conversas_supabase:
                # Criar chave única baseada no conteúdo, sender e timestamp
                chave_unica = f"{conversa['sender']}_{conversa['message'][:50]}_{conversa.get('timestamp', '')}"
                
                if chave_unica not in mensagens_vistas:
                    mensagens_vistas.add(chave_unica)
                    conversas_unicas.append(conversa)
            
            # Usar lista filtrada
            conversas_supabase = conversas_unicas
            
            # 5. Inserir no Supabase (em lote) - COM LOGS DETALHADOS
            if conversas_supabase:
                # LOG DETALHADO: Mostrar cada mensagem que será inserida
                logger.info(f"🔄 PREPARANDO INSERÇÃO NO SUPABASE:")
                logger.info(f"📊 Total de mensagens: {len(conversas_supabase)}")
                
                for i, conversa in enumerate(conversas_supabase, 1):
                    logger.info(f"📝 MENSAGEM {i}/{len(conversas_supabase)}:")
                    logger.info(f"   🔹 Sender: {conversa['sender']}")
                    logger.info(f"   🔹 Type: {conversa['conversation_type']}")
                    logger.info(f"   🔹 Content: {conversa['message'][:100]}{'...' if len(conversa['message']) > 100 else ''}")
                    logger.info(f"   🔹 Phase: {conversa['metadata']['phase']}")
                    logger.info(f"   🔹 Original Sender: {conversa['metadata']['sender_original']}")
                
                # Inserir no Supabase
                logger.info(f"🚀 EXECUTANDO INSERÇÃO NO SUPABASE...")
                result = supabase.table('ai_conversations').insert(conversas_supabase).execute()
                
                if result.data:
                    # LOG DETALHADO: Confirmar inserção
                    logger.info(f"✅ INSERÇÃO CONCLUÍDA COM SUCESSO!")
                    logger.info(f"📊 Mensagens inseridas: {len(result.data)}")
                    
                    # Log de cada mensagem inserida
                    for i, msg_inserida in enumerate(result.data, 1):
                        logger.info(f"✅ SALVA {i}: [{msg_inserida.get('sender', 'N/A')}] {msg_inserida.get('conversation_type', 'N/A')} - {msg_inserida.get('message', '')[:50]}{'...' if len(msg_inserida.get('message', '')) > 50 else ''}")
                    
                    # 6. Marcar mensagens como sincronizadas
                    self._marcar_mensagens_sincronizadas_arquivo(conversation_id, len(result.data), conversation)
                    
                    logger.info(f"✅ Sincronização concluída: {len(result.data)} mensagens inseridas")
                    
                    return {
                        'sucesso': True,
                        'mensagens_sincronizadas': len(result.data),
                        'negotiation_id': negotiation_id,
                        'conversation_id': conversation_id
                    }
                else:
                    logger.error("❌ Nenhuma mensagem foi inserida no Supabase")
                    return {
                        'sucesso': False,
                        'erro': 'Nenhuma mensagem inserida',
                        'mensagens_sincronizadas': 0
                    }
            else:
                logger.info("ℹ️ Nenhuma mensagem nova para sincronizar")
                return {
                    'sucesso': True,
                    'mensagens_sincronizadas': 0,
                    'negotiation_id': negotiation_id,
                    'conversation_id': conversation_id,
                    'motivo': 'Nenhuma mensagem nova'
                }
                
        except Exception as e:
            logger.error(f"❌ Erro na sincronização: {str(e)}")
            return {
                'sucesso': False,
                'erro': str(e),
                'mensagens_sincronizadas': 0
            }
    
    def _carregar_conversa_do_arquivo(self, conversation_id: str) -> Optional[Dict]:
        """
        Carrega conversa do arquivo (finalizadas ou em_andamento)
        
        Args:
            conversation_id (str): ID da conversa
            
        Returns:
            Optional[Dict]: Dados da conversa ou None se não encontrar
        """
        try:
            # Buscar em finalizadas primeiro
            finalizadas_path = self.base_path / "finalizadas" / f"{conversation_id}.json"
            if finalizadas_path.exists():
                with open(finalizadas_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            
            # Buscar em em_andamento
            em_andamento_path = self.base_path / "em_andamento" / f"{conversation_id}.json"
            if em_andamento_path.exists():
                with open(em_andamento_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Erro ao carregar conversa do arquivo {conversation_id}: {e}")
            return None

    def _marcar_mensagens_sincronizadas_arquivo(self, conversation_id: str, quantidade: int, conversation: Dict):
        """
        Marca mensagens como sincronizadas no arquivo
        
        Args:
            conversation_id (str): ID da conversa
            quantidade (int): Quantidade de mensagens sincronizadas
            conversation (Dict): Dados da conversa
        """
        try:
            contador = 0
            
            # Marcar mensagens APENAS no array principal (evita duplicação)
            if 'messages' in conversation:
                for msg in conversation['messages']:
                    if not msg.get('supabase_synced', False) and contador < quantidade:
                        msg['supabase_synced'] = True
                        msg['supabase_sync_timestamp'] = datetime.now().isoformat()
                        contador += 1
            
            # Salvar arquivo atualizado
            self._salvar_conversa_arquivo(conversation_id, conversation)
            
            logger.info(f"✅ {contador} mensagens marcadas como sincronizadas no arquivo")
            
        except Exception as e:
            logger.error(f"❌ Erro ao marcar mensagens sincronizadas no arquivo: {e}")

    def _salvar_conversa_arquivo(self, conversation_id: str, conversation: Dict):
        """
        Salva conversa no arquivo correto (finalizadas ou em_andamento)
        
        Args:
            conversation_id (str): ID da conversa
            conversation (Dict): Dados da conversa
        """
        try:
            # Determinar pasta baseada no status
            status = conversation.get('conversation_info', {}).get('status', 'active')
            
            if status == 'finalized':
                pasta = "finalizadas"
            else:
                pasta = "em_andamento"
            
            arquivo_path = self.base_path / pasta / f"{conversation_id}.json"
            
            with open(arquivo_path, 'w', encoding='utf-8') as f:
                json.dump(conversation, f, ensure_ascii=False, indent=2)
            
            logger.info(f"💾 Conversa salva em {pasta}: {conversation_id}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao salvar conversa no arquivo: {e}")

    def obter_conversa_ativa_por_telefone(self, telefone: str) -> Optional[str]:
        """
        ✅ MELHORADO: Busca conversa por telefone principal OU relacionado
        
        Args:
            telefone (str): Número do telefone
            
        Returns:
            Optional[str]: ID da conversa ou None se não encontrar
        """
        try:
            # Buscar em em_andamento primeiro
            em_andamento_path = self.base_path / "em_andamento"
            if em_andamento_path.exists():
                for arquivo in em_andamento_path.glob("*.json"):
                    try:
                        with open(arquivo, 'r', encoding='utf-8') as f:
                            conversa = json.load(f)
                            conv_info = conversa.get('conversation_info', {})
                            
                            # Buscar por telefone principal
                            if conv_info.get('phone_number') == telefone:
                                return conv_info['id']
                            
                            # ✅ NOVO: Buscar por telefones relacionados
                            related_phones = conv_info.get('related_phones', [])
                            if telefone in related_phones:
                                logger.info(f"🔗 Conversa encontrada por telefone relacionado: {telefone}")
                                return conv_info['id']
                                
                    except Exception as e:
                        logger.warning(f"⚠️ Erro ao ler arquivo {arquivo}: {e}")
                        continue
            
            # Buscar em finalizadas se não encontrou em em_andamento
            finalizadas_path = self.base_path / "finalizadas"
            if finalizadas_path.exists():
                for arquivo in finalizadas_path.glob("*.json"):
                    try:
                        with open(arquivo, 'r', encoding='utf-8') as f:
                            conversa = json.load(f)
                            conv_info = conversa.get('conversation_info', {})
                            
                            # Buscar por telefone principal
                            if conv_info.get('phone_number') == telefone:
                                return conv_info['id']
                            
                            # ✅ NOVO: Buscar por telefones relacionados
                            related_phones = conv_info.get('related_phones', [])
                            if telefone in related_phones:
                                logger.info(f"🔗 Conversa encontrada por telefone relacionado: {telefone}")
                                return conv_info['id']
                                
                    except Exception as e:
                        logger.warning(f"⚠️ Erro ao ler arquivo {arquivo}: {e}")
                        continue
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar conversa por telefone {telefone}: {e}")
            return None

    def finalizar_conversa_por_telefone(self, telefone: str) -> Dict[str, Any]:
        """
        ✅ MELHORADO: Finaliza conversa por telefone principal OU relacionado
        
        Args:
            telefone (str): Número do telefone
            
        Returns:
            Dict: Resultado da operação com sucesso, erro e conversation_id
        """
        try:
            # Buscar conversa em em_andamento
            em_andamento_path = self.base_path / "em_andamento"
            conversa_encontrada = None
            arquivo_origem = None
            
            if em_andamento_path.exists():
                for arquivo in em_andamento_path.glob("*.json"):
                    try:
                        with open(arquivo, 'r', encoding='utf-8') as f:
                            conversa = json.load(f)
                            conv_info = conversa.get('conversation_info', {})
                            
                            # Buscar por telefone principal
                            if conv_info.get('phone_number') == telefone:
                                conversa_encontrada = conversa
                                arquivo_origem = arquivo
                                break
                            
                            # ✅ NOVO: Buscar por telefones relacionados
                            related_phones = conv_info.get('related_phones', [])
                            if telefone in related_phones:
                                logger.info(f"🔗 Conversa encontrada por telefone relacionado para finalizar: {telefone}")
                                conversa_encontrada = conversa
                                arquivo_origem = arquivo
                                break
                                
                    except Exception as e:
                        logger.warning(f"⚠️ Erro ao ler arquivo {arquivo}: {e}")
                        continue
            
            if not conversa_encontrada:
                return {
                    'sucesso': False,
                    'erro': f'Nenhuma conversa em andamento encontrada para telefone {telefone}',
                    'conversation_id': None
                }
            
            # Atualizar status da conversa para finalizada
            conversation_id = conversa_encontrada['conversation_info']['id']
            conversa_encontrada['conversation_info']['status'] = 'finalized'
            conversa_encontrada['conversation_info']['end_time'] = datetime.now().isoformat()
            conversa_encontrada['conversation_info']['last_updated'] = datetime.now().isoformat()
            
            # Finalizar fase atual se existir
            if 'conversation_phases' in conversa_encontrada:
                current_phase = conversa_encontrada['conversation_phases'].get('current')
                if current_phase and current_phase in conversa_encontrada['conversation_phases']['phases']:
                    conversa_encontrada['conversation_phases']['phases'][current_phase]['ended_at'] = datetime.now().isoformat()
            
            # Salvar na pasta finalizadas
            finalizadas_path = self.base_path / "finalizadas"
            finalizadas_path.mkdir(exist_ok=True)
            
            arquivo_destino = finalizadas_path / arquivo_origem.name
            
            with open(arquivo_destino, 'w', encoding='utf-8') as f:
                json.dump(conversa_encontrada, f, ensure_ascii=False, indent=2)
            
            # Remover arquivo original de em_andamento
            arquivo_origem.unlink()
            
            logger.info(f"✅ Conversa finalizada e movida: {conversation_id} (telefone: {telefone})")
            
            return {
                'sucesso': True,
                'conversation_id': conversation_id,
                'arquivo_destino': str(arquivo_destino),
                'mensagem': f'Conversa {conversation_id} finalizada com sucesso'
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao finalizar conversa por telefone {telefone}: {e}")
            return {
                'sucesso': False,
                'erro': str(e),
                'conversation_id': None
            }

    def _limpar_formatacao_mensagem(self, mensagem: str) -> str:
        """
        Remove formatação de asteriscos e outros caracteres das mensagens para o banco
        
        Args:
            mensagem (str): Mensagem original com formatação
            
        Returns:
            str: Mensagem limpa sem asteriscos
        """
        try:
            if not mensagem:
                return ""
            
            # Remover asteriscos de formatação (negrito)
            mensagem_limpa = mensagem.replace('*', '')
            
            # Remover outros caracteres de formatação se necessário
            # mensagem_limpa = mensagem_limpa.replace('_', '')  # itálico
            # mensagem_limpa = mensagem_limpa.replace('~', '')  # riscado
            
            return mensagem_limpa.strip()
            
        except Exception as e:
            logger.warning(f"⚠️ Erro ao limpar formatação da mensagem: {e}")
            return mensagem  # Retornar original em caso de erro 

    def limpar_conversa_com_openai(self, conversation_id: str) -> Dict[str, Any]:
        """
        🧠 NOVA FUNÇÃO: Limpa conversa usando OpenAI antes da sincronização
        
        Remove duplicatas, logs técnicos e formata mensagens naturalmente
        para otimizar inserção no banco de dados.
        
        Args:
            conversation_id (str): ID da conversa
            
        Returns:
            Dict: Resultado da limpeza
        """
        try:
            logger.info(f"🧹 Iniciando limpeza OpenAI da conversa: {conversation_id}")
            
            # Buscar conversa
            conversation = None
            
            # Tentar buscar na memória primeiro
            if conversation_id in self.active_conversations:
                conversation = self.active_conversations[conversation_id]
                logger.info(f"📋 Conversa encontrada na memória: {conversation_id}")
            else:
                # Buscar no arquivo
                conversation = self._carregar_conversa_do_arquivo(conversation_id)
                if conversation:
                    logger.info(f"📁 Conversa carregada do arquivo: {conversation_id}")
            
            if not conversation:
                return {
                    'sucesso': False,
                    'erro': 'Conversa não encontrada na memória nem no arquivo',
                    'conversation_id': conversation_id
                }
            
            # Verificar se já foi limpa
            if conversation.get('ai_cleaning'):
                logger.info(f"ℹ️ Conversa já foi limpa anteriormente: {conversation_id}")
                return {
                    'sucesso': True,
                    'conversation_id': conversation_id,
                    'ja_limpa': True,
                    'limpeza_anterior': conversation['ai_cleaning']
                }
            
            # Importar OpenAI Service
            try:
                from src.services.openai_service import OpenAIService
                openai_service = OpenAIService()
            except Exception as e:
                logger.error(f"❌ Erro ao conectar OpenAI Service: {e}")
                return {
                    'sucesso': False,
                    'erro': f'Erro conexão OpenAI: {str(e)}',
                    'conversation_id': conversation_id
                }
            
            # Usar OpenAI para limpar a conversa
            conversa_limpa = openai_service.analisar_e_limpar_conversa_json(conversation)
            
            if not conversa_limpa:
                return {
                    'sucesso': False,
                    'erro': 'OpenAI retornou conversa vazia',
                    'conversation_id': conversation_id
                }
            
            # Verificar se houve mudanças
            original_count = len(conversation.get('messages', []))
            cleaned_count = len(conversa_limpa.get('messages', []))
            
            if original_count == cleaned_count and not conversa_limpa.get('ai_cleaning', {}).get('reformatted_count', 0):
                logger.info(f"ℹ️ Nenhuma mudança necessária na conversa: {conversation_id}")
                
                # Adicionar flag de que foi analisada mas não precisou de limpeza
                conversation['ai_cleaning'] = {
                    "cleaned_at": datetime.now().isoformat(),
                    "original_message_count": original_count,
                    "cleaned_message_count": cleaned_count,
                    "justificativa": "Conversa já estava limpa - nenhuma mudança necessária",
                    "removed_indices": [],
                    "reformatted_count": 0
                }
                conversa_limpa = conversation
            
            # Salvar conversa limpa
            self._salvar_conversa_arquivo(conversation_id, conversa_limpa)
            
            # Atualizar na memória se existir
            if conversation_id in self.active_conversations:
                self.active_conversations[conversation_id] = conversa_limpa
            
            ai_cleaning_info = conversa_limpa.get('ai_cleaning', {})
            
            logger.info(f"✅ Limpeza OpenAI concluída: {conversation_id}")
            logger.info(f"📊 Mensagens: {ai_cleaning_info.get('original_message_count')} → {ai_cleaning_info.get('cleaned_message_count')}")
            logger.info(f"📝 Justificativa: {ai_cleaning_info.get('justificativa', 'N/A')}")
            
            return {
                'sucesso': True,
                'conversation_id': conversation_id,
                'original_message_count': ai_cleaning_info.get('original_message_count'),
                'cleaned_message_count': ai_cleaning_info.get('cleaned_message_count'),
                'removed_count': len(ai_cleaning_info.get('removed_indices', [])),
                'inserted_count': ai_cleaning_info.get('inserted_count', 0),
                'reformatted_count': ai_cleaning_info.get('reformatted_count', 0),
                'justificativa': ai_cleaning_info.get('justificativa'),
                'cleaned_at': ai_cleaning_info.get('cleaned_at')
            }
            
        except Exception as e:
            logger.error(f"❌ Erro na limpeza OpenAI da conversa {conversation_id}: {str(e)}")
            return {
                'sucesso': False,
                'erro': str(e),
                'conversation_id': conversation_id
            }
    
    def sincronizar_conversa_supabase_com_limpeza(self, conversation_id: str, negotiation_id: str) -> Dict[str, Any]:
        """
        ✅ NOVA FUNÇÃO: Sincroniza conversa com Supabase aplicando limpeza OpenAI primeiro
        
        Fluxo:
        1. Limpa conversa com OpenAI (remove duplicatas, formata menus)
        2. Sincroniza versão limpa com Supabase
        
        Args:
            conversation_id (str): ID da conversa no JSON
            negotiation_id (str): ID da negociação no Supabase
            
        Returns:
            Dict: Resultado da sincronização com informações da limpeza
        """
        try:
            logger.info(f"🔄 Iniciando sincronização com limpeza: {conversation_id} → {negotiation_id}")
            
            # Passo 1: Limpar conversa com OpenAI
            resultado_limpeza = self.limpar_conversa_com_openai(conversation_id)
            
            if not resultado_limpeza['sucesso']:
                logger.warning(f"⚠️ Falha na limpeza, prosseguindo com sincronização normal")
                # Se limpeza falhar, usar método normal
                return self.sincronizar_conversa_supabase(conversation_id, negotiation_id)
            
            # Passo 2: Sincronizar versão limpa
            resultado_sync = self.sincronizar_conversa_supabase(conversation_id, negotiation_id)
            
            # Adicionar informações da limpeza ao resultado
            if resultado_sync['sucesso']:
                resultado_sync['limpeza_aplicada'] = True
                resultado_sync['mensagens_removidas'] = resultado_limpeza.get('removed_count', 0)
                resultado_sync['mensagens_inseridas'] = resultado_limpeza.get('inserted_count', 0)  
                resultado_sync['mensagens_reformatadas'] = resultado_limpeza.get('reformatted_count', 0)
                resultado_sync['limpeza_detalhes'] = {
                    'mensagens_removidas': resultado_limpeza.get('removed_count', 0),
                    'mensagens_inseridas': resultado_limpeza.get('inserted_count', 0),
                    'mensagens_reformatadas': resultado_limpeza.get('reformatted_count', 0),
                    'justificativa': resultado_limpeza.get('justificativa', 'N/A')
                }
                
                logger.info(f"✅ Sincronização com limpeza concluída:")
                logger.info(f"🧹 Limpeza: {resultado_limpeza.get('removed_count', 0)} removidas, {resultado_limpeza.get('reformatted_count', 0)} reformatadas")
                logger.info(f"💾 Sync: {resultado_sync.get('mensagens_sincronizadas', 0)} mensagens inseridas no Supabase")
            
            return resultado_sync
            
        except Exception as e:
            logger.error(f"❌ Erro na sincronização com limpeza: {str(e)}")
            # Fallback para sincronização normal
            return self.sincronizar_conversa_supabase(conversation_id, negotiation_id) 
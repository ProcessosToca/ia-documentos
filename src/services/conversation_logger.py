"""
Módulo ConversationLogger - Sistema de Captura de Conversas (V2)
================================================================

VERSÃO 2.0 - MELHORIAS INCREMENTAIS:
- ✅ Classificação específica de sender/receiver
- ✅ Fases de conversa separadas  
- ✅ Contexto melhorado
- ✅ 100% compatível com código existente

Responsável por capturar, estruturar e salvar todas as conversas entre:
- IA ↔ Cliente  
- IA ↔ Corretor

Funcionalidades:
- Captura em tempo real
- Classificação automática ESPECÍFICA
- Salvamento em JSON estruturado com FASES
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
    
    Gerencia todo o ciclo de vida das conversas:
    1. Criação de nova conversa
    2. Captura de mensagens em tempo real
    3. Classificação automática (dúvidas/fechamento)
    4. Salvamento estruturado em JSON
    5. Movimentação entre pastas conforme status
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
        
        logger.info("🗂️ ConversationLogger V2.0 inicializado com melhorias")
    
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
            if conversation_id not in self.active_conversations:
                return False
            
            conversation_data = self.active_conversations[conversation_id]
            
            # Determinar caminho do arquivo
            filename = f"{conversation_id}.json"
            filepath = self.base_path / folder / filename
            
            # Salvar arquivo
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(conversation_data, f, indent=2, ensure_ascii=False)
            
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
            if conversation_id not in self.active_conversations:
                return False
            
            conversation = self.active_conversations[conversation_id]
            conversation["participants"][participant_type] = participant_data
            conversation["conversation_info"]["last_updated"] = datetime.now().isoformat()
            
            # Salvar atualização
            conversation_type = conversation["conversation_info"]["type"]
            self._save_conversation(conversation_id, conversation_type)
            
            logger.info(f"👤 Dados do {participant_type} atualizados: {conversation_id}")
            return True
            
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
    
    def add_message(self, conversation_id: str, role: str, content: str) -> bool:
        """
        ✅ COMPATIBILIDADE V2: Alias para log_message com parâmetros simplificados
        
        Args:
            conversation_id (str): ID da conversa
            role (str): "user", "assistant", "system"
            content (str): Conteúdo da mensagem
            
        Returns:
            bool: True se adicionou com sucesso
        """
        return self.log_message(conversation_id, role, content)
    
    def add_message_enhanced(self, conversation_id: str, sender: str, receiver: str, content: str, phase: str = None) -> bool:
        """
        ✅ NOVO V2: Método avançado com classificação específica
        
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
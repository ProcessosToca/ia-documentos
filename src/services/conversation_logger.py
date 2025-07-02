"""
Módulo ConversationLogger - Sistema de Captura de Conversas
===========================================================

Responsável por capturar, estruturar e salvar todas as conversas entre:
- IA ↔ Cliente  
- IA ↔ Corretor

Funcionalidades:
- Captura em tempo real
- Classificação automática
- Salvamento em JSON estruturado
- Gestão de arquivos por tipo
- Integração não-invasiva

Autor: Sistema IA Toca Imóveis
Data:  JUlho/2025
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
    Sistema profissional de captura de conversas
    
    Gerencia todo o ciclo de vida das conversas:
    1. Criação de nova conversa
    2. Captura de mensagens em tempo real
    3. Classificação automática (dúvidas/fechamento)
    4. Salvamento estruturado em JSON
    5. Movimentação entre pastas conforme status
    """
    
    def __init__(self, base_path: str = "conversations_logs"):
        """
        Inicializa o ConversationLogger
        
        Args:
            base_path (str): Caminho base para salvamento dos JSONs
        """
        self.base_path = Path(base_path)
        self.enabled = True
        self.active_conversations = {}  # Cache de conversas ativas
        
        # Garantir que as pastas existem
        self._ensure_directories()
        
        logger.info("🗂️ ConversationLogger inicializado")
    
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
            
            # Estrutura base do JSON
            conversation_data = {
                "conversation_info": {
                    "id": conversation_id,
                    "type": conversation_type,
                    "status": "active",
                    "start_time": datetime.now().isoformat(),
                    "last_updated": datetime.now().isoformat(),
                    "phone_number": phone_number
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
                    "classification_changes": []
                },
                "messages": [],
                "metadata": {
                    "platform": "whatsapp",
                    "system_version": "1.0",
                    "created_by": "conversation_logger"
                }
            }
            
            # Armazenar no cache
            self.active_conversations[conversation_id] = conversation_data
            
            # Salvar arquivo inicial
            self._save_conversation(conversation_id, conversation_type)
            
            logger.info(f"🆕 Nova conversa iniciada: {conversation_id} (tipo: {conversation_type})")
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
        Registra uma nova mensagem na conversa
        
        Args:
            conversation_id (str): ID da conversa
            sender (str): Quem enviou ("cliente", "corretor", "ia")
            content (str): Conteúdo da mensagem
            message_type (str): Tipo da mensagem
            metadata (dict): Metadados adicionais
            
        Returns:
            bool: True se registrou com sucesso
        """
        try:
            if not self.enabled or conversation_id not in self.active_conversations:
                return False
            
            # Criar estrutura da mensagem
            message = {
                "id": f"msg_{len(self.active_conversations[conversation_id]['messages']) + 1:03d}",
                "timestamp": datetime.now().isoformat(),
                "sender": sender,
                "content": content,
                "message_type": message_type,
                "metadata": metadata or {}
            }
            
            # Adicionar à conversa
            conversation = self.active_conversations[conversation_id]
            conversation["messages"].append(message)
            
            # Atualizar estatísticas
            conversation["conversation_summary"]["total_messages"] += 1
            if sender == "ia":
                conversation["conversation_summary"]["ai_messages"] += 1
            else:
                conversation["conversation_summary"]["user_messages"] += 1
            
            conversation["conversation_info"]["last_updated"] = datetime.now().isoformat()
            
            # Salvar atualização
            conversation_type = conversation["conversation_info"]["type"]
            self._save_conversation(conversation_id, conversation_type)
            
            logger.info(f"💬 Mensagem registrada: {conversation_id} ({sender})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao registrar mensagem: {str(e)}")
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
        Alias para log_message com parâmetros simplificados
        
        Args:
            conversation_id (str): ID da conversa
            role (str): "user", "assistant", "system"
            content (str): Conteúdo da mensagem
            
        Returns:
            bool: True se adicionou com sucesso
        """
        return self.log_message(conversation_id, role, content)
    
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
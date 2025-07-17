"""
Serviço de Verificação de Consentimento LGPD
===========================================

Responsável por verificar se o cliente já possui consentimento
registrado antes de solicitar dados pessoais adicionais.

Funcionalidades:
- Busca consentimento por CPF
- Verificação de status (completo/parcial/revogado)
- Integração com Supabase
- Validação LGPD

Autor: Sistema IA Toca Imóveis
Data: Julho 2025
"""

import re
import os
import logging
from typing import Dict, Optional, Tuple, Any
from supabase import create_client, Client

# Configuração de logging
logger = logging.getLogger(__name__)

class ConsentimentoService:
    """
    Serviço profissional para verificação de consentimentos LGPD
    
    Verifica se o cliente já possui consentimento registrado antes
    de solicitar dados pessoais adicionais (e-mail, data nascimento, etc.)
    """
    
    def __init__(self):
        """Inicializa o serviço de consentimento"""
        try:
            # Configurações do Supabase
            self.supabase_url = "https://rqyyoofuwrwwfcuxfjwu.supabase.co"
            self.supabase_key = os.getenv('SUPABASE_KEY')
            
            if not self.supabase_key:
                logger.warning("⚠️ SUPABASE_KEY não encontrada no ambiente")
                self.enabled = False
                return
            
            # Inicializar cliente Supabase
            self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
            self.enabled = True
            
            logger.info("✅ ConsentimentoService inicializado")
            
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar ConsentimentoService: {e}")
            self.enabled = False
    
    def is_enabled(self) -> bool:
        """Verifica se o serviço está ativo"""
        return self.enabled
    
    def normalizar_cpf(self, cpf: str) -> str:
        """
        Remove pontos, traços e espaços do CPF
        
        Args:
            cpf (str): CPF com ou sem formatação
            
        Returns:
            str: CPF apenas com números
        """
        return re.sub(r'\D', '', cpf)
    
    def buscar_consentimento_por_cpf(self, cpf: str) -> Tuple[bool, Optional[Dict]]:
        """
        Busca consentimento do cliente pelo CPF
        
        Args:
            cpf (str): CPF do cliente (com ou sem formatação)
            
        Returns:
            Tuple contendo:
            - bool: True se encontrou consentimento, False se não encontrou
            - Dict ou None: Dados do consentimento se encontrado
        """
        if not self.enabled:
            logger.warning("⚠️ ConsentimentoService desabilitado")
            return False, None
        
        try:
            # Normalizar CPF (remover pontos, traços, espaços)
            cpf_limpo = self.normalizar_cpf(cpf)
            
            logger.info(f"🔍 Buscando consentimento para CPF: {cpf_limpo[:3]}***")
            
            # Buscar na tabela client_consents
            response = self.supabase.table('client_consents').select('*').eq('client_cpf', cpf_limpo).execute()
            
            # Verificar se encontrou dados
            if response.data and len(response.data) > 0:
                logger.info(f"✅ Consentimento encontrado para CPF: {cpf_limpo[:3]}***")
                return True, response.data[0]  # Retorna o primeiro registro encontrado
            else:
                logger.info(f"❌ Nenhum consentimento encontrado para CPF: {cpf_limpo[:3]}***")
                return False, None
                
        except Exception as e:
            logger.error(f"❌ Erro ao buscar consentimento: {e}")
            return False, None
    
    def verificar_status_consentimento(self, cpf: str) -> Dict:
        """
        Verifica status detalhado do consentimento
        
        Args:
            cpf (str): CPF do cliente
            
        Returns:
            Dict: Informações completas do consentimento
        """
        if not self.enabled:
            return {
                'tem_consentimento': False,
                'status': 'servico_indisponivel',
                'mensagem': 'Serviço de consentimento temporariamente indisponível',
                'pode_coletar_dados': True,  # Fallback seguro
                'dados': None
            }
        
        tem_consentimento, dados = self.buscar_consentimento_por_cpf(cpf)
        
        if not tem_consentimento:
            return {
                'tem_consentimento': False,
                'status': 'nao_encontrado',
                'mensagem': 'Cliente não possui consentimento registrado - pode coletar dados',
                'pode_coletar_dados': True,  # Pode coletar se não tem registro
                'dados': None
            }
        
        # Analisar os dados do consentimento
        status = dados.get('status', 'pending')
        
        # Verificar se pode coletar dados baseado no status e consentimentos
        pode_coletar = self._pode_coletar_dados(dados)
        
        resultado = {
            'tem_consentimento': True,
            'status': status,
            'pode_coletar_dados': pode_coletar,
            'cliente_nome': dados.get('client_name'),
            'cliente_telefone': dados.get('client_phone'),
            'data_criacao': dados.get('created_at'),
            'consentimentos': {
                'dados_pessoais': dados.get('data_processing_consent', False),
                'envio_documentos': dados.get('document_sharing_consent', False),
                'concordancia_completa': dados.get('complete_consent', False)
            },
            'revogacoes': {
                'dados_pessoais_revogado': dados.get('data_processing_revoked', False),
                'documentos_revogado': dados.get('document_sharing_revoked', False),
                'completo_revogado': dados.get('complete_consent_revoked', False)
            },
            'origem_consentimento': dados.get('consent_origin', 'whatsapp'),
            'versao_politica': dados.get('privacy_policy_version', '1.0'),
            'dados_completos': dados
        }
        
        # Determinar mensagem baseada no status
        resultado['mensagem'] = self._gerar_mensagem_status(status, pode_coletar)
        
        return resultado
    
    def _pode_coletar_dados(self, dados: Dict) -> bool:
        """
        Determina se pode coletar dados baseado nos consentimentos
        
        Args:
            dados (Dict): Dados do consentimento
            
        Returns:
            bool: True se pode coletar, False se não pode
        """
        # Se foi revogado completamente, não pode coletar
        if dados.get('complete_consent_revoked', False):
            return False
        
        # Se dados pessoais foram revogados, não pode coletar
        if dados.get('data_processing_revoked', False):
            return False
        
        # Se status é revoked, não pode coletar
        if dados.get('status') == 'revoked':
            return False
        
        # Se tem consentimento para dados pessoais, pode coletar
        if dados.get('data_processing_consent', False):
            return True
        
        # Se tem consentimento completo, pode coletar
        if dados.get('complete_consent', False):
            return True
        
        # Casos default: se não tem revogação explícita, pode coletar
        return True
    
    def _gerar_mensagem_status(self, status: str, pode_coletar: bool) -> str:
        """
        Gera mensagem baseada no status e permissão de coleta
        
        Args:
            status (str): Status do consentimento
            pode_coletar (bool): Se pode coletar dados
            
        Returns:
            str: Mensagem explicativa
        """
        if not pode_coletar:
            if status == 'revoked':
                return '❌ Cliente revogou consentimento - não pode coletar dados'
            else:
                return '⛔ Cliente não autorizou coleta de dados pessoais'
        
        if status == 'complete':
            return '✅ Cliente possui consentimento completo para coleta de dados'
        elif status == 'partial':
            return '⚠️ Cliente possui consentimento parcial - pode coletar dados básicos'
        elif status == 'pending':
            return '⏳ Consentimento pendente - pode coletar dados'
        else:
            return f'📋 Status: {status} - coleta autorizada'
    
    def gerar_mensagem_para_cliente(self, resultado_consentimento: Dict[str, Any]) -> str:
        """
        Gera mensagem personalizada para o cliente baseada no resultado da verificação
        
        Args:
            resultado_consentimento (Dict): Resultado da verificação de consentimento
            
        Returns:
            str: Mensagem para enviar ao cliente
        """
        try:
            pode_coletar = resultado_consentimento.get('pode_coletar_dados', False)
            
            if pode_coletar:
                return """✅ *Dados Verificados*

O cliente já possui consentimento ativo e pode prosseguir com a coleta de dados."""
            
            else:
                return """⚠️ *Restrição de Dados*

O cliente revogou seu consentimento. Não é possível coletar dados pessoais automaticamente."""
                
        except Exception as e:
            logger.error(f"❌ Erro ao gerar mensagem para cliente: {e}")
            return "Vou conectar você com um de nossos atendentes."

    def salvar_consentimento_lgpd(
        self,
        client_cpf: str,
        client_name: str,
        client_phone: str,
        tipo_consentimento: str = "complete",
        consent_origin: str = "whatsapp",
        whatsapp_message_id: str = None,
        notes: str = None
    ) -> Dict[str, Any]:
        """
        Salva consentimento LGPD no Supabase após cliente concordar
        
        Args:
            client_cpf (str): CPF do cliente
            client_name (str): Nome do cliente  
            client_phone (str): Telefone do cliente
            tipo_consentimento (str): Tipo de consentimento ("complete", "data_only", "docs_only")
            consent_origin (str): Origem do consentimento
            whatsapp_message_id (str): ID da mensagem WhatsApp
            notes (str): Observações adicionais
            
        Returns:
            Dict: Resultado da operação
        """
        try:
            if not self.is_enabled():
                logger.warning("⚠️ Supabase não disponível - não foi possível salvar consentimento")
                return {
                    "success": False,
                    "error": "Supabase não disponível",
                    "message": "Consentimento não salvo - serviço indisponível"
                }
            
            # 1. Normalizar dados
            cpf_limpo = self._normalizar_cpf(client_cpf)
            telefone_limpo = self._normalizar_telefone(client_phone)
            
            # 2. Determinar tipos de consentimento
            if tipo_consentimento == "complete":
                data_consent = True
                doc_consent = True
                complete_consent = True
                status = "complete"
            elif tipo_consentimento == "data_only":
                data_consent = True
                doc_consent = False
                complete_consent = False
                status = "partial"
            elif tipo_consentimento == "docs_only":
                data_consent = False
                doc_consent = True
                complete_consent = False
                status = "partial"
            else:
                data_consent = False
                doc_consent = False
                complete_consent = False
                status = "pending"
            
            # 3. Preparar timestamp atual
            from datetime import datetime
            agora = datetime.now().isoformat()
            
            # 4. Montar dados para inserção
            dados_consentimento = {
                # Dados do cliente
                "client_cpf": cpf_limpo,
                "client_name": client_name.strip(),
                "client_phone": telefone_limpo,
                
                # Tipos de consentimento
                "data_processing_consent": data_consent,
                "document_sharing_consent": doc_consent,
                "complete_consent": complete_consent,
                
                # Datas de consentimento (só preenche se True)
                "data_processing_consent_date": agora if data_consent else None,
                "document_sharing_consent_date": agora if doc_consent else None,
                "complete_consent_date": agora if complete_consent else None,
                
                # Metadados
                "consent_origin": consent_origin,
                "privacy_policy_version": "1.0",
                "whatsapp_message_id": whatsapp_message_id,
                "notes": notes,
                "status": status
            }
            
            # 5. Verificar se já existe consentimento ativo
            consentimento_existente = self._buscar_consentimento_ativo(cpf_limpo)
            
            if consentimento_existente:
                # Atualizar existente
                resultado = self._atualizar_consentimento_existente(
                    consentimento_existente['id'], 
                    dados_consentimento
                )
                acao = "atualizado"
            else:
                # Criar novo
                resultado = self._criar_novo_consentimento(dados_consentimento)
                acao = "criado"
            
            logger.info(f"✅ Consentimento {acao} para CPF: {cpf_limpo[:3]}*** - Status: {status}")
            
            return {
                "success": True,
                "data": resultado,
                "message": f"Consentimento {acao} com sucesso",
                "action": acao,
                "status": status
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao salvar consentimento: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "message": "Erro ao salvar consentimento"
            }

    def _normalizar_cpf(self, cpf: str) -> str:
        """Remove caracteres especiais do CPF"""
        return ''.join(filter(str.isdigit, cpf))
    
    def _normalizar_telefone(self, telefone: str) -> str:
        """Remove caracteres especiais do telefone"""
        return ''.join(filter(str.isdigit, telefone))
    
    def _buscar_consentimento_ativo(self, cpf: str) -> Optional[Dict]:
        """Busca consentimento ativo existente para o CPF"""
        try:
            response = self.supabase.table('client_consents')\
                .select('*')\
                .eq('client_cpf', cpf)\
                .neq('status', 'revoked')\
                .maybeSingle()\
                .execute()
            
            return response.data if response.data else None
            
        except Exception as e:
            logger.warning(f"⚠️ Erro ao buscar consentimento existente: {e}")
            return None
    
    def _criar_novo_consentimento(self, dados: Dict) -> Dict:
        """Cria um novo registro de consentimento"""
        response = self.supabase.table('client_consents')\
            .insert(dados)\
            .execute()
        
        return response.data[0] if response.data else None
    
    def _atualizar_consentimento_existente(self, consent_id: str, dados: Dict) -> Dict:
        """Atualiza consentimento existente"""
        # Remove campos que não devem ser atualizados
        dados_para_update = dados.copy()
        dados_para_update.pop('client_cpf', None)  # CPF não muda
        
        response = self.supabase.table('client_consents')\
            .update(dados_para_update)\
            .eq('id', consent_id)\
            .execute()
        
        return response.data[0] if response.data else None

    def salvar_consentimento_rapido(
        self,
        cpf: str,
        nome: str,
        telefone: str,
        tipo_consentimento: str = "complete"
    ) -> bool:
        """
        Função simplificada para salvar consentimento rapidamente
        
        Args:
            cpf (str): CPF do cliente
            nome (str): Nome do cliente
            telefone (str): Telefone do cliente
            tipo_consentimento (str): "complete", "data_only", "docs_only"
            
        Returns:
            bool: True se salvou com sucesso, False caso contrário
        """
        resultado = self.salvar_consentimento_lgpd(
            client_cpf=cpf,
            client_name=nome,
            client_phone=telefone,
            tipo_consentimento=tipo_consentimento
        )
        
        return resultado["success"]

    def buscar_politica_privacidade(self) -> Dict[str, Any]:
        """
        Busca a política de privacidade ativa no Supabase
        
        Returns:
            Dict: Dados da política de privacidade ou erro
        """
        try:
            if not self.is_enabled():
                logger.warning("⚠️ Supabase não disponível - usando política padrão")
                return {
                    "success": False,
                    "error": "Supabase não disponível",
                    "link_padrao": "https://tocaimoveis.com.br/politica-privacidade",
                    "message": "Política padrão retornada"
                }
            
            # Buscar política ativa na tabela privacy_policy
            response = self.supabase.table('privacy_policy')\
                .select('id, content, updated_at, link')\
                .eq('is_active', True)\
                .order('updated_at', desc=True)\
                .limit(1)\
                .execute()
            
            if response.data and len(response.data) > 0:
                politica = response.data[0]
                
                # Verificar se tem link da coluna 'link'
                link_politica = politica.get('link', '').strip() if politica.get('link') else ''
                
                logger.info(f"✅ Política de privacidade encontrada - Link: {'Sim' if link_politica else 'Não'}")
                
                return {
                    "success": True,
                    "data": {
                        "id": politica["id"],
                        "content": politica.get("content", ""),
                        "updated_at": politica["updated_at"],
                        "public_link": link_politica,  # Usar a coluna 'link'
                        "version": "1.0"    # Versão padrão
                    },
                    "message": f"Política encontrada {'com link' if link_politica else 'sem link'}"
                }
            else:
                logger.warning("⚠️ Nenhuma política de privacidade ativa encontrada")
                return {
                    "success": False,
                    "error": "Política não encontrada",
                    "link_padrao": "https://tocaimoveis.com.br/politica-privacidade",
                    "message": "Nenhuma política ativa no banco"
                }
                
        except Exception as e:
            logger.error(f"❌ Erro ao buscar política de privacidade: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "link_padrao": "https://tocaimoveis.com.br/politica-privacidade",
                "message": "Erro ao buscar política - link padrão retornado"
            }

    def gerar_mensagem_politica_privacidade(self) -> str:
        """
        Gera mensagem com link da política de privacidade ou texto completo
        
        Returns:
            str: Mensagem formatada com link da política ou texto completo
        """
        try:
            resultado_politica = self.buscar_politica_privacidade()
            
            if resultado_politica["success"]:
                # Política encontrada no Supabase
                dados_politica = resultado_politica["data"]
                link_politica = dados_politica.get("public_link", "")
                versao = dados_politica.get("version", "1.0")
                data_atualizacao = dados_politica.get("updated_at", "")
                
                if link_politica:
                    return f"""📄 *Política de Privacidade - Toca Imóveis*

🔗 *Link para acesso*: {link_politica}

📋 *Versão*: {versao}
📅 *Última atualização*: {data_atualizacao[:10] if data_atualizacao else 'N/A'}

Nossa política detalha como tratamos seus dados pessoais conforme a LGPD.

⬅️ *Volte para continuar seu atendimento após a leitura.*"""
                
            # Fallback: enviar política completa em texto
            return self._gerar_politica_texto_completo()
            
        except Exception as e:
            logger.error(f"❌ Erro ao gerar mensagem de política: {e}")
            return self._gerar_politica_texto_completo()

    def _gerar_politica_texto_completo(self) -> str:
        """
        Gera política de privacidade completa em texto
        
        Returns:
            str: Política de privacidade completa formatada
        """
        return """📄 *Política de Privacidade para Coleta de Dados e Documentos via WhatsApp*

*1. Introdução*
Esta Política de Privacidade tem como objetivo informar como coletamos, utilizamos, armazenamos e protegemos os dados pessoais e documentos enviados por nossos clientes através do WhatsApp, em conformidade com a Lei nº 13.709/2018 (LGPD).

*2. Dados Coletados*
Coletamos informações pessoais e documentos que podem incluir:
• Nome completo
• CPF/RG ou outros documentos de identificação
• Endereço
• Dados de contato (telefone, e-mail, etc.)
• Outros dados e documentos necessários para a prestação dos nossos serviços

*3. Finalidade da Coleta*
Os dados e documentos coletados via WhatsApp serão utilizados exclusivamente para:
• Identificação do cliente
• Análise de informações para prestação de serviços contratados
• Cumprimento de obrigações legais e regulatórias
• Comunicação relacionada aos serviços prestados

*4. Compartilhamento de Dados*
Seus dados poderão ser compartilhados apenas com terceiros necessários para a execução do serviço, sempre observando a confidencialidade e segurança das informações.

*5. Armazenamento e Segurança*
Seus dados e documentos serão armazenados em ambiente seguro e controlado, sendo adotadas medidas técnicas e administrativas para proteger suas informações contra acessos não autorizados, situações acidentais ou ilícitas de destruição, perda, alteração, comunicação ou difusão.

*6. Direitos dos Titulares*
Você pode, a qualquer momento, solicitar:
• Confirmação da existência de tratamento
• Acesso aos seus dados
• Correção de dados incompletos, inexatos ou desatualizados
• Anonimização, bloqueio ou eliminação de dados desnecessários ou excessivos
• Portabilidade dos dados a outro fornecedor de serviço, mediante requisição expressa
• Eliminação dos dados tratados com seu consentimento, exceto nas hipóteses previstas em lei

*7. Contato*
Para exercer seus direitos ou em caso de dúvidas sobre esta Política, entre em contato conosco através do WhatsApp.

*8. Atualizações*
Esta Política pode ser atualizada a qualquer momento para garantir nossa conformidade com a LGPD.

⬅️ *Volte para continuar seu atendimento após a leitura.*""" 
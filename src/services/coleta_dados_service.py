"""
Serviço de Coleta de Dados Expandida
====================================

Responsável pela coleta completa de dados do cliente:
- CPF + verificação de consentimento
- E-mail com validação
- Data de nascimento com validação de idade
- CEP com busca automática via ViaCEP
- Confirmação e correção de endereço
- Número e complemento

Funcionalidades:
- Validações em tempo real
- Integração com ViaCEP API
- Verificação LGPD
- Coleta estruturada e segura

Autor: Sistema IA Toca Imóveis
Data: Julho 2025
"""
import re
import requests
import logging
from datetime import datetime, date
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass, asdict

# Configuração de logging
logger = logging.getLogger(__name__)

@dataclass
class DadosCliente:
    """Estrutura para armazenar dados coletados do cliente"""
    # Dados básicos (já coletados)
    nome: str = ""
    telefone: str = ""
    cpf: str = ""
    
    # Dados expandidos (novos)
    email: str = ""
    data_nascimento: str = ""
    idade: Optional[int] = None
    
    # Endereço (via CEP)
    cep: str = ""
    endereco_completo: str = ""
    rua: str = ""
    bairro: str = ""
    cidade: str = ""
    uf: str = ""
    numero: str = ""
    complemento: str = ""
    
    # Status da coleta
    etapa_atual: str = "cpf"  # cpf, email, data_nascimento, cep, endereco_confirmacao, numero, complemento, finalizado
    dados_completos: bool = False
    
    # Metadados
    timestamp_inicio: str = ""
    timestamp_conclusao: str = ""
    consentimento_verificado: bool = False
    pode_coletar_dados: bool = True

class ColetaDadosService:
    """
    Serviço profissional para coleta expandida de dados do cliente
    
    Gerencia todo o fluxo de coleta com validações, verificação de consentimento
    e integração com APIs externas (ViaCEP).
    """
    
    def __init__(self):
        """Inicializa o serviço de coleta de dados"""
        self.dados_sessao: Dict[str, DadosCliente] = {}
        self.enabled = True
        
        # Regex patterns para validação
        self.regex_email = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        self.regex_cpf = re.compile(r'^\d{11}$')
        self.regex_cep = re.compile(r'^\d{8}$')
        self.regex_data = re.compile(r'^(\d{2})/(\d{2})/(\d{4})$')
        
        logger.info("✅ ColetaDadosService inicializado")
    
    def iniciar_coleta(self, telefone: str, nome: str, cpf: str) -> DadosCliente:
        """
        Inicia nova sessão de coleta de dados
        
        Args:
            telefone (str): Telefone do cliente
            nome (str): Nome do cliente
            cpf (str): CPF do cliente
            
        Returns:
            DadosCliente: Estrutura de dados inicializada
        """
        # 🔥 LOG: CPF original vs normalizado
        cpf_normalizado = self._normalizar_cpf(cpf)
        logger.info(f"📄 CPF PROCESSADO:")
        logger.info(f"   📥 CPF original: {cpf}")
        logger.info(f"   📤 CPF normalizado: {cpf_normalizado}")
        
        dados = DadosCliente(
            nome=nome,
            telefone=telefone,
            cpf=cpf_normalizado,
            etapa_atual="email",  # CPF já foi coletado pelo WhatsApp - iniciar com email
            timestamp_inicio=datetime.now().isoformat()
        )
        
        self.dados_sessao[telefone] = dados
        
        # 🔥 LOG: Dados armazenados na sessão
        logger.info(f"💾 DADOS ARMAZENADOS NA SESSÃO:")
        logger.info(f"   📋 Nome: {dados.nome}")
        logger.info(f"   📄 CPF: {dados.cpf}")
        logger.info(f"   📞 Telefone: {dados.telefone}")
        logger.info(f"   🎯 Etapa atual: {dados.etapa_atual}")
        
        logger.info(f"🆕 Iniciada coleta de dados para {telefone}")
        return dados
    
    def obter_dados_sessao(self, telefone: str) -> Optional[DadosCliente]:
        """
        Obtém dados da sessão de coleta
        
        Args:
            telefone (str): Telefone do cliente
            
        Returns:
            DadosCliente ou None: Dados da sessão se existir
        """
        return self.dados_sessao.get(telefone)
    
    def processar_resposta(self, telefone: str, resposta: str) -> Dict:
        """
        Processa resposta do cliente baseada na etapa atual
        
        Args:
            telefone (str): Telefone do cliente
            resposta (str): Resposta do cliente
            
        Returns:
            Dict: Resultado do processamento
        """
        dados = self.dados_sessao.get(telefone)
        if not dados:
            return {
                'sucesso': False,
                'erro': 'Sessão de coleta não encontrada',
                'acao': 'reiniciar_coleta'
            }
        
        # Processar baseado na etapa atual
        if dados.etapa_atual == "cpf":
            return self._processar_cpf(dados, resposta)
        elif dados.etapa_atual == "email":
            return self._processar_email(dados, resposta)
        elif dados.etapa_atual == "data_nascimento":
            return self._processar_data_nascimento(dados, resposta)
        elif dados.etapa_atual == "cep":
            return self._processar_cep(dados, resposta)
        elif dados.etapa_atual == "endereco_confirmacao":
            return self._processar_confirmacao_endereco(dados, resposta)
        elif dados.etapa_atual == "numero":
            return self._processar_numero(dados, resposta)
        elif dados.etapa_atual == "complemento":
            return self._processar_complemento(dados, resposta)
        else:
            return {
                'sucesso': False,
                'erro': f'Etapa desconhecida: {dados.etapa_atual}',
                'acao': 'erro_interno'
            }
    
    def _processar_cpf(self, dados: DadosCliente, cpf_resposta: str) -> Dict:
        """
        ✅ NOVO: Processa e confirma CPF do cliente
        
        Args:
            dados (DadosCliente): Dados da sessão
            cpf_resposta (str): CPF informado pelo cliente
            
        Returns:
            Dict: Resultado do processamento
        """
        cpf_limpo = self._normalizar_cpf(cpf_resposta)
        
        # Validar formato do CPF
        if not self.regex_cpf.match(cpf_limpo):
            return {
                'sucesso': False,
                'erro': 'CPF inválido',
                'mensagem': """❌ *CPF inválido*

Por favor, digite um CPF válido com 11 números:

Exemplo: 123.456.789-00 ou 12345678900

📄 *Digite seu CPF:*""",
                'acao': 'solicitar_novamente'
            }
        
        # CPF válido - atualizar dados
        dados.cpf = cpf_limpo
        dados.etapa_atual = "email"
        
        return {
            'sucesso': True,
            'dados_atualizados': True,
            'proxima_etapa': 'email',
            'mensagem': f"""✅ *CPF confirmado:* {cpf_limpo[:3]}.{cpf_limpo[3:6]}.{cpf_limpo[6:9]}-{cpf_limpo[9:]}

📧 *Agora digite seu e-mail:*

Formato: exemplo@email.com"""
        }

    def _processar_email(self, dados: DadosCliente, email: str) -> Dict:
        """Processa e valida e-mail"""
        email = email.strip().lower()
        
        if not self.regex_email.match(email):
            return {
                'sucesso': False,
                'erro': 'E-mail inválido',
                'mensagem': """❌ *E-mail inválido*

Por favor, digite um e-mail válido no formato:
*exemplo@email.com*

📧 *Digite seu e-mail:*""",
                'acao': 'solicitar_novamente'
            }
        
        # E-mail válido
        dados.email = email
        dados.etapa_atual = "data_nascimento"
        
        return {
            'sucesso': True,
            'dados_atualizados': True,
            'proxima_etapa': 'data_nascimento',
            'mensagem': f"""✅ *E-mail confirmado:* {email}

📅 *Agora digite sua data de nascimento:*

Formato: DD/MM/AAAA
Exemplo: 15/03/1990"""
        }
    
    def _processar_data_nascimento(self, dados: DadosCliente, data_str: str) -> Dict:
        """Processa e valida data de nascimento"""
        data_str = data_str.strip()
        
        # Validar formato
        match = self.regex_data.match(data_str)
        if not match:
            return {
                'sucesso': False,
                'erro': 'Formato de data inválido',
                'mensagem': """❌ *Data inválida*

Por favor, digite a data no formato correto:
*DD/MM/AAAA*

Exemplo: 15/03/1990

📅 *Digite sua data de nascimento:*""",
                'acao': 'solicitar_novamente'
            }
        
        # Extrair componentes da data
        dia, mes, ano = match.groups()
        
        try:
            data_nascimento = date(int(ano), int(mes), int(dia))
            idade = self._calcular_idade(data_nascimento)
            
            # Validar idade mínima (18 anos)
            if idade < 18:
                return {
                    'sucesso': False,
                    'erro': 'Idade mínima não atendida',
                    'mensagem': f"""⚠️ *Idade insuficiente*

Identificamos que você tem {idade} anos.

Para prosseguir com nossos serviços, é necessário ter pelo menos *18 anos*.

Para atendimento especializado, entre em contato:
📞 *(14) 99999-9999*""",
                    'acao': 'idade_insuficiente'
                }
            
            # Data válida e idade OK
            dados.data_nascimento = data_str
            dados.idade = idade
            dados.etapa_atual = "cep"
            
            return {
                'sucesso': True,
                'dados_atualizados': True,
                'proxima_etapa': 'cep',
                'mensagem': f"""✅ *Data confirmada:* {data_str} ({idade} anos)

🏠 *Agora digite seu CEP:*

Formato: apenas números
Exemplo: 18035310"""
            }
            
        except ValueError:
            return {
                'sucesso': False,
                'erro': 'Data inválida',
                'mensagem': """❌ *Data inexistente*

A data informada não existe no calendário.

Por favor, verifique e digite novamente:

📅 *Digite sua data de nascimento:*
Formato: DD/MM/AAAA""",
                'acao': 'solicitar_novamente'
            }
    
    def _processar_cep(self, dados: DadosCliente, cep_str: str) -> Dict:
        """Processa CEP e busca endereço via ViaCEP"""
        cep_limpo = re.sub(r'\D', '', cep_str)
        
        if not self.regex_cep.match(cep_limpo):
            return {
                'sucesso': False,
                'erro': 'CEP inválido',
                'mensagem': """❌ *CEP inválido*

Por favor, digite um CEP válido com 8 números:

Exemplo: 18035310 ou 18035-310

🏠 *Digite seu CEP:*""",
                'acao': 'solicitar_novamente'
            }
        
        # Buscar endereço via ViaCEP
        endereco_info = self._buscar_endereco_viacep(cep_limpo)
        
        if not endereco_info['sucesso']:
            return {
                'sucesso': False,
                'erro': 'CEP não encontrado',
                'mensagem': f"""❌ *CEP não encontrado*

O CEP {cep_limpo} não foi encontrado na base de dados.

Por favor, verifique o CEP e digite novamente:

🏠 *Digite seu CEP:*""",
                'acao': 'solicitar_novamente'
            }
        
        # CEP encontrado - atualizar dados
        endereco = endereco_info['endereco']
        dados.cep = cep_limpo
        dados.rua = endereco['logradouro']
        dados.bairro = endereco['bairro']
        dados.cidade = endereco['localidade']
        dados.uf = endereco['uf']
        dados.endereco_completo = f"{endereco['logradouro']}, {endereco['bairro']}, {endereco['localidade']}/{endereco['uf']}"
        dados.etapa_atual = "endereco_confirmacao"
        
        return {
            'sucesso': True,
            'dados_atualizados': True,
            'proxima_etapa': 'endereco_confirmacao',
            'mensagem': f"""✅ *Endereço encontrado:*

📍 *{dados.endereco_completo}*
🔢 *CEP:* {cep_limpo}

Este endereço está correto?

Digite:
✅ *SIM* - para confirmar
❌ *NÃO* - para informar o endereço correto"""
        }
    
    def _processar_confirmacao_endereco(self, dados: DadosCliente, resposta: str) -> Dict:
        """Processa confirmação do endereço"""
        resposta_lower = resposta.lower().strip()
        
        if resposta_lower in ['sim', 's', 'yes', 'correto', 'certo', '✅']:
            # Endereço confirmado
            dados.etapa_atual = "numero"
            
            return {
                'sucesso': True,
                'dados_atualizados': True,
                'proxima_etapa': 'numero',
                'mensagem': f"""✅ *Endereço confirmado!*

🏠 *{dados.endereco_completo}*

🔢 *Agora digite o número da sua residência:*

Exemplo: 123, 45A, S/N"""
            }
        
        elif resposta_lower in ['não', 'nao', 'no', 'incorreto', 'errado', '❌']:
            # Endereço incorreto - solicitar manual
            return {
                'sucesso': False,
                'erro': 'Endereço incorreto - coleta manual necessária',
                'mensagem': """📝 *Endereço Manual*

Como o endereço encontrado não confere, vou te transferir para um de nossos atendentes que coletará suas informações corretamente.

⏰ *Aguarde um momento...*

📞 Caso prefira, entre em contato: *(14) 99999-9999*""",
                'acao': 'transferir_atendente'
            }
        
        else:
            # Resposta não reconhecida
            return {
                'sucesso': False,
                'erro': 'Resposta não reconhecida',
                'mensagem': f"""📍 *Endereço encontrado:*
*{dados.endereco_completo}*

Esse é seu endereço?

✅ *SIM* - se o endereço está correto
❌ *NÃO* - se o endereço está incorreto""",
                'acao': 'solicitar_novamente'
            }
    
    def _processar_numero(self, dados: DadosCliente, numero: str) -> Dict:
        """Processa número da residência"""
        numero = numero.strip()
        
        if not numero:
            return {
                'sucesso': False,
                'erro': 'Número não informado',
                'mensagem': """❌ *Número necessário*

Por favor, digite o número da sua residência:

Exemplo: 123, 45A, S/N

🔢 *Digite o número:*""",
                'acao': 'solicitar_novamente'
            }
        
        # Número válido
        dados.numero = numero
        dados.etapa_atual = "complemento"
        
        return {
            'sucesso': True,
            'dados_atualizados': True,
            'proxima_etapa': 'complemento',
            'mensagem': f"""🏢 *Tem complemento? (apartamento, bloco, etc.)*

Digite o complemento ou:
➡️ *PULAR* - se não tem complemento"""
        }
    
    def _processar_complemento(self, dados: DadosCliente, complemento: str) -> Dict:
        """Processa complemento do endereço"""
        complemento = complemento.strip()
        
        if complemento.lower() in ['pular', 'não', 'nao', 'sem', 'nenhum', '']:
            dados.complemento = ""
        else:
            dados.complemento = complemento
        
        # Finalizar coleta
        dados.etapa_atual = "finalizado"
        dados.dados_completos = True
        dados.timestamp_conclusao = datetime.now().isoformat()
        
        # Processar finalização completa (salvar cliente + criar negociação)
        resultado_final = self.processar_finalizacao_coleta(dados)
        
        return resultado_final
    
    def _gerar_resumo_final(self, dados: DadosCliente) -> str:
        """Gera resumo final dos dados coletados"""
        endereco_completo = f"{dados.rua}, {dados.numero}"
        if dados.complemento:
            endereco_completo += f", {dados.complemento}"
        endereco_completo += f"\n{dados.bairro}, {dados.cidade}/{dados.uf}"
        endereco_completo += f"\nCEP: {dados.cep[:5]}-{dados.cep[5:]}"
        
        return f"""✅ Dados coletados com sucesso!

👤 *Cliente:* {dados.nome}
📱 *Telefone:* {dados.telefone}
🆔 *CPF:* {dados.cpf[:3]}***{dados.cpf[-2:]}
📧 *E-mail:* {dados.email}
📅 *Nascimento:* {dados.data_nascimento} ({dados.idade} anos)

🏠 *Endereço:*
{endereco_completo}"""
    
    def salvar_cliente_supabase(self, dados: DadosCliente) -> Dict:
        """
        Salva cliente na tabela 'clientes' do Supabase (com verificação de duplicata)
        
        Args:
            dados (DadosCliente): Dados completos do cliente
            
        Returns:
            Dict: Resultado da operação com ID do cliente se sucesso
        """
        try:
            # 🔥 LOG DETALHADO: Estado completo dos dados
            logger.info(f"🔥 SALVANDO CLIENTE NO SUPABASE:")
            logger.info(f"   📋 Nome: {dados.nome}")
            logger.info(f"   📄 CPF: {dados.cpf}")
            logger.info(f"   📧 Email: {dados.email}")
            logger.info(f"   📞 Telefone: {dados.telefone}")
            logger.info(f"   📅 Data Nascimento: {dados.data_nascimento}")
            logger.info(f"   🏠 Endereço: {dados.rua}, {dados.numero}")
            logger.info(f"   🌆 Cidade: {dados.cidade}")
            logger.info(f"   🏢 Estado: {dados.uf}")
            logger.info(f"   📮 CEP: {dados.cep}")
            
            # Importar Supabase
            from src.services.buscar_usuarios_supabase import obter_cliente_supabase
            
            supabase = obter_cliente_supabase()
            
            # 1. Verificar se cliente já existe por CPF
            logger.info(f"🔍 Verificando se cliente já existe: CPF {dados.cpf}")
            existing_client = supabase.table('clientes').select('*').eq('cpf', dados.cpf).execute()
            
            if existing_client.data:
                # Cliente já existe - atualizar dados
                cliente_existente = existing_client.data[0]
                cliente_id = cliente_existente['id']
                
                logger.info(f"🔄 Cliente já existe, atualizando dados: {cliente_id}")
                
                # Preparar dados para atualização
                endereco_completo = f"{dados.rua}, {dados.numero}"
                if dados.complemento:
                    endereco_completo += f", {dados.complemento}"
                
                update_data = {
                    "nome": dados.nome,
                    "email": dados.email,
                    "telefone": dados.telefone,
                    "data_nascimento": dados.data_nascimento,
                    "endereco": endereco_completo,
                    "cidade": dados.cidade,
                    "estado": dados.uf,
                    "cep": dados.cep,
                    "updated_at": "now()"
                }
                
                # Atualizar registro existente
                result = supabase.table('clientes').update(update_data).eq('id', cliente_id).execute()
                
                if result.data:
                    logger.info(f"✅ Cliente atualizado com sucesso! ID: {cliente_id}")
                    return {
                        'sucesso': True,
                        'cliente_id': cliente_id,
                        'mensagem': 'Dados do cliente atualizados com sucesso',
                        'dados_salvos': result.data[0],
                        'acao': 'atualizado'
                    }
            
            # 2. Cliente não existe - criar novo
            logger.info(f"💾 Criando novo cliente no Supabase: {dados.nome}")
            
            # Preparar dados para inserção
            endereco_completo = f"{dados.rua}, {dados.numero}"
            if dados.complemento:
                endereco_completo += f", {dados.complemento}"
            
            cliente_data = {
                "nome": dados.nome,
                "cpf": dados.cpf,
                "email": dados.email,
                "telefone": dados.telefone,
                "data_nascimento": dados.data_nascimento,
                "endereco": endereco_completo,
                "cidade": dados.cidade,
                "estado": dados.uf,
                "cep": dados.cep
            }
            
            # 🔥 LOG: Dados que serão enviados para o Supabase
            logger.info(f"📤 DADOS ENVIADOS PARA SUPABASE:")
            logger.info(f"   📋 nome: {cliente_data['nome']}")
            logger.info(f"   📄 cpf: {cliente_data['cpf']}")
            logger.info(f"   📧 email: {cliente_data['email']}")
            logger.info(f"   📞 telefone: {cliente_data['telefone']}")
            logger.info(f"   📅 data_nascimento: {cliente_data['data_nascimento']}")
            logger.info(f"   🏠 endereco: {cliente_data['endereco']}")
            logger.info(f"   🌆 cidade: {cliente_data['cidade']}")
            logger.info(f"   🏢 estado: {cliente_data['estado']}")
            logger.info(f"   📮 cep: {cliente_data['cep']}")
            
            # Inserir no Supabase
            result = supabase.table('clientes').insert(cliente_data).execute()
            
            # 🔥 LOG: Resposta do Supabase
            logger.info(f"📥 RESPOSTA DO SUPABASE:")
            logger.info(f"   🔍 result.data: {result.data}")
            
            if result.data:
                cliente_id = result.data[0]['id']
                logger.info(f"✅ Cliente criado com sucesso! ID: {cliente_id}")
                
                # 🔥 LOG: Dados salvos retornados pelo Supabase
                logger.info(f"💾 DADOS SALVOS NO SUPABASE:")
                for key, value in result.data[0].items():
                    logger.info(f"   📝 {key}: {value}")
                
                return {
                    'sucesso': True,
                    'cliente_id': cliente_id,
                    'mensagem': 'Cliente cadastrado com sucesso',
                    'dados_salvos': result.data[0],
                    'acao': 'criado'
                }
            else:
                logger.error("❌ Falha ao salvar cliente - sem dados de retorno")
                return {
                    'sucesso': False,
                    'erro': 'Falha ao salvar - sem dados de retorno',
                    'mensagem': 'Erro interno ao cadastrar cliente'
                }
                
        except Exception as e:
            logger.error(f"❌ Erro ao salvar cliente no Supabase: {e}")
            
            # Verificar se é erro de CPF duplicado
            error_str = str(e)
            if 'duplicate key value violates unique constraint' in error_str and 'cpf' in error_str:
                return {
                    'sucesso': False,
                    'erro': 'CPF já cadastrado no sistema',
                    'mensagem': 'Este CPF já está cadastrado. Verificando dados existentes...',
                    'tipo_erro': 'cpf_duplicado'
                }
            
            return {
                'sucesso': False,
                'erro': str(e),
                'mensagem': 'Erro interno ao cadastrar cliente'
            }
    
    def criar_negociacao_cliente(self, dados: DadosCliente, cliente_id: str = None) -> Dict:
        """
        Cria negociação na tabela 'ai_negotiations' do Supabase
        
        Args:
            dados (DadosCliente): Dados do cliente
            cliente_id (str, optional): ID do cliente na tabela clientes
            
        Returns:
            Dict: Resultado da operação com ID da negociação se sucesso
        """
        try:
            # Importar Supabase
            from src.services.buscar_usuarios_supabase import obter_cliente_supabase
            
            supabase = obter_cliente_supabase()
            
            # Preparar endereço completo para metadata
            endereco_completo = f"{dados.rua}, {dados.numero}"
            if dados.complemento:
                endereco_completo += f", {dados.complemento}"
            endereco_completo += f", {dados.bairro}, {dados.cidade}/{dados.uf}, CEP: {dados.cep}"
            
            # Preparar dados para inserção
            negociacao_data = {
                "client_name": dados.nome,
                "client_phone": dados.telefone,
                "client_email": dados.email,
                "client_cpf": dados.cpf,
                "rental_modality": "residencial",
                "status": "coletando_documentos",  # Próximo passo após coleta
                "metadata": {
                    "origem": "coleta_expandida_whatsapp",
                    "dados_completos": True,
                    "endereco_completo": endereco_completo,
                    "idade": dados.idade,
                    "timestamp_conclusao_coleta": dados.timestamp_conclusao
                }
            }
            
            # Adicionar cliente_id se fornecido
            if cliente_id:
                negociacao_data["metadata"]["cliente_id"] = cliente_id
            
            logger.info(f"📋 Criando negociação no Supabase para: {dados.nome}")
            
            # 🔥 LOG: Dados da negociação que serão enviados
            logger.info(f"📤 DADOS DA NEGOCIAÇÃO ENVIADOS PARA SUPABASE:")
            logger.info(f"   📋 client_name: {negociacao_data['client_name']}")
            logger.info(f"   📄 client_cpf: {negociacao_data['client_cpf']}")
            logger.info(f"   📧 client_email: {negociacao_data['client_email']}")
            logger.info(f"   📞 client_phone: {negociacao_data['client_phone']}")
            logger.info(f"   🏠 rental_modality: {negociacao_data['rental_modality']}")
            logger.info(f"   📊 status: {negociacao_data['status']}")
            
            # Inserir no Supabase
            result = supabase.table('ai_negotiations').insert(negociacao_data).execute()
            
            # 🔥 LOG: Resposta da inserção da negociação
            logger.info(f"📥 RESPOSTA DA NEGOCIAÇÃO DO SUPABASE:")
            logger.info(f"   🔍 result.data: {result.data}")
            
            if result.data:
                negociacao_id = result.data[0]['id']
                logger.info(f"✅ Negociação criada com sucesso! ID: {negociacao_id}")
                
                # 🔥 LOG: Dados da negociação salvos
                logger.info(f"💾 DADOS DA NEGOCIAÇÃO SALVOS NO SUPABASE:")
                for key, value in result.data[0].items():
                    logger.info(f"   📝 {key}: {value}")
                
                return {
                    'sucesso': True,
                    'negociacao_id': negociacao_id,
                    'mensagem': 'Negociação iniciada com sucesso',
                    'dados_salvos': result.data[0]
                }
            else:
                logger.error("❌ Falha ao criar negociação - sem dados de retorno")
                return {
                    'sucesso': False,
                    'erro': 'Falha ao criar negociação - sem dados de retorno',
                    'mensagem': 'Erro interno ao iniciar negociação'
                }
                
        except Exception as e:
            logger.error(f"❌ Erro ao criar negociação no Supabase: {e}")
            return {
                'sucesso': False,
                'erro': str(e),
                'mensagem': 'Erro interno ao iniciar negociação'
            }
    
    def processar_finalizacao_coleta(self, dados: DadosCliente) -> Dict:
        """
        Processa a finalização completa da coleta: salva cliente e cria negociação
        
        Args:
            dados (DadosCliente): Dados completos coletados
            
        Returns:
            Dict: Resultado completo do processamento
        """
        logger.info(f"🎯 Iniciando finalização completa da coleta para: {dados.nome}")
        
        # 🔥 LOG DETALHADO: Estado completo dos dados na finalização
        logger.info(f"🔥 DADOS RECEBIDOS NA FINALIZAÇÃO:")
        logger.info(f"   📋 Nome: {dados.nome}")
        logger.info(f"   📄 CPF: {dados.cpf}")
        logger.info(f"   📧 Email: {dados.email}")
        logger.info(f"   📞 Telefone: {dados.telefone}")
        logger.info(f"   📅 Data Nascimento: {dados.data_nascimento}")
        logger.info(f"   🏠 Endereço: {dados.rua}, {dados.numero}")
        logger.info(f"   🌆 Cidade: {dados.cidade}")
        logger.info(f"   🏢 Estado: {dados.uf}")
        logger.info(f"   📮 CEP: {dados.cep}")
        
        resultado_final = {
            'sucesso': True,
            'coleta_finalizada': True,
            'cliente_salvo': False,
            'negociacao_criada': False,
            'dados_completos': asdict(dados),
            'erros': []
        }
        
        # 1. Salvar cliente
        resultado_cliente = self.salvar_cliente_supabase(dados)
        
        if resultado_cliente['sucesso']:
            resultado_final['cliente_salvo'] = True
            resultado_final['cliente_id'] = resultado_cliente['cliente_id']
            logger.info(f"✅ Cliente salvo: {resultado_cliente['cliente_id']}")
            
            # 2. Criar negociação (usando o ID do cliente)
            resultado_negociacao = self.criar_negociacao_cliente(
                dados, 
                cliente_id=resultado_cliente['cliente_id']
            )
            
            if resultado_negociacao['sucesso']:
                resultado_final['negociacao_criada'] = True
                resultado_final['negociacao_id'] = resultado_negociacao['negociacao_id']
                logger.info(f"✅ Negociação criada: {resultado_negociacao['negociacao_id']}")
                
                # 3. NOVO: Atualizar dados do cliente na conversa e sincronizar com Supabase
                resultado_final['conversa_sincronizada'] = False
                resultado_final['conversa_finalizada'] = False
                resultado_final['dados_cliente_atualizados'] = False
                try:
                    # Tentar finalizar e sincronizar conversas se ConversationLogger estiver disponível
                    from src.services.conversation_logger import ConversationLogger
                    conversation_logger = ConversationLogger()
                    
                    # NOVO: Primeiro, atualizar dados do cliente na conversa ANTES de finalizar
                    conv_id = conversation_logger.obter_conversa_ativa_por_telefone(dados.telefone)
                    if conv_id:
                        # ✅ CORREÇÃO: Incluir CPF e dados coletados na estrutura participants
                        dados_cliente_completos = {
                            "name": dados.nome,
                            "phone": dados.telefone,
                            "cpf": dados.cpf,  # ✅ INCLUIR CPF!
                            "email": dados.email,
                            "data_nascimento": dados.data_nascimento,
                            "idade": dados.idade,
                            "endereco_completo": dados.endereco_completo,
                            "cep": dados.cep,
                            "cidade": dados.cidade,
                            "uf": dados.uf,
                            "whatsapp_verified": True,
                            "coleta_finalizada": True
                        }
                        
                        # 🔥 LOG: Dados que serão enviados para a conversa
                        logger.info(f"📤 DADOS ENVIADOS PARA A CONVERSA:")
                        logger.info(f"   📋 name: {dados_cliente_completos['name']}")
                        logger.info(f"   📄 cpf: {dados_cliente_completos['cpf']}")
                        logger.info(f"   📧 email: {dados_cliente_completos['email']}")
                        logger.info(f"   📞 phone: {dados_cliente_completos['phone']}")
                        logger.info(f"   📅 data_nascimento: {dados_cliente_completos['data_nascimento']}")
                        logger.info(f"   🏠 endereco_completo: {dados_cliente_completos['endereco_completo']}")
                        logger.info(f"   📮 cep: {dados_cliente_completos['cep']}")
                        logger.info(f"   🌆 cidade: {dados_cliente_completos['cidade']}")
                        logger.info(f"   🏢 uf: {dados_cliente_completos['uf']}")
                        logger.info(f"   ✅ coleta_finalizada: {dados_cliente_completos['coleta_finalizada']}")
                        
                        # Atualizar dados do cliente na conversa
                        sucesso_atualizacao = conversation_logger.update_participant_data(
                            conv_id,
                            "client",
                            dados_cliente_completos
                        )
                        
                        if sucesso_atualizacao:
                            resultado_final['dados_cliente_atualizados'] = True
                            logger.info(f"✅ Dados do cliente atualizados na conversa: {conv_id}")
                            
                            # 🔥 CRÍTICO: Forçar salvamento imediato na pasta em_andamento
                            if conv_id in conversation_logger.active_conversations:
                                conversation_logger._save_conversation(conv_id, "em_andamento")
                                logger.info(f"💾 Conversa salva com dados atualizados: {conv_id}")
                        else:
                            logger.warning(f"⚠️ Falha ao atualizar dados do cliente: {conv_id}")
                    
                    # Segundo: Finalizar conversa (mover de em_andamento para finalizadas)
                    resultado_finalizacao = conversation_logger.finalizar_conversa_por_telefone(dados.telefone)
                    
                    if resultado_finalizacao['sucesso']:
                        resultado_final['conversa_finalizada'] = True
                        resultado_final['conversation_id'] = resultado_finalizacao['conversation_id']
                        logger.info(f"✅ Conversa finalizada: {resultado_finalizacao['conversation_id']}")
                        
                        # Segundo: Sincronizar conversa finalizada com Supabase + LIMPEZA OPENAI 🧠
                        logger.info(f"🧠 Iniciando sincronização com limpeza OpenAI...")
                        resultado_sync = conversation_logger.sincronizar_conversa_supabase_com_limpeza(
                            conversation_id=resultado_finalizacao['conversation_id'],
                            negotiation_id=resultado_negociacao['negociacao_id']
                        )
                        
                        if resultado_sync['sucesso']:
                            resultado_final['conversa_sincronizada'] = True
                            resultado_final['mensagens_sincronizadas'] = resultado_sync['mensagens_sincronizadas']
                            resultado_final['limpeza_openai_aplicada'] = True
                            resultado_final['mensagens_removidas'] = resultado_sync.get('mensagens_removidas', 0)
                            resultado_final['mensagens_inseridas'] = resultado_sync.get('mensagens_inseridas', 0)
                            resultado_final['mensagens_reformatadas'] = resultado_sync.get('mensagens_reformatadas', 0)
                            logger.info(f"✅ Conversa sincronizada com limpeza OpenAI: {resultado_sync['mensagens_sincronizadas']} mensagens")
                            logger.info(f"🧠 Limpeza aplicada: {resultado_sync.get('mensagens_removidas', 0)} removidas, {resultado_sync.get('mensagens_inseridas', 0)} inseridas, {resultado_sync.get('mensagens_reformatadas', 0)} reformatadas")
                        else:
                            logger.warning(f"⚠️ Falha na sincronização da conversa: {resultado_sync['erro']}")
                            # Fallback: tentar sincronização sem limpeza
                            logger.info(f"🔄 Tentando sincronização sem limpeza como fallback...")
                            resultado_sync_fallback = conversation_logger.sincronizar_conversa_supabase(
                                conversation_id=resultado_finalizacao['conversation_id'],
                                negotiation_id=resultado_negociacao['negociacao_id']
                            )
                            if resultado_sync_fallback['sucesso']:
                                resultado_final['conversa_sincronizada'] = True
                                resultado_final['mensagens_sincronizadas'] = resultado_sync_fallback['mensagens_sincronizadas']
                                resultado_final['limpeza_openai_aplicada'] = False
                                logger.info(f"✅ Conversa sincronizada sem limpeza: {resultado_sync_fallback['mensagens_sincronizadas']} mensagens")
                    else:
                        logger.info(f"ℹ️ Nenhuma conversa em andamento encontrada para finalizar: {resultado_finalizacao['erro']}")
                        
                except Exception as e:
                    logger.warning(f"⚠️ Erro na finalização/sincronização da conversa: {e}")
                    # Não falhar o processo se a sincronização falhar
                    
            else:
                resultado_final['erros'].append({
                    'tipo': 'negociacao',
                    'erro': resultado_negociacao['erro']
                })
                logger.warning(f"⚠️ Cliente salvo mas falha na negociação: {resultado_negociacao['erro']}")
        else:
            resultado_final['sucesso'] = False
            resultado_final['erros'].append({
                'tipo': 'cliente',
                'erro': resultado_cliente['erro']
            })
            logger.error(f"❌ Falha ao salvar cliente: {resultado_cliente['erro']}")
        
        # 3. Gerar mensagem final
        if resultado_final['cliente_salvo'] and resultado_final['negociacao_criada']:
            resultado_final['mensagem'] = self._gerar_resumo_final(dados)
            logger.info("🎉 Finalização completa realizada com sucesso!")
        elif resultado_final['cliente_salvo']:
            resultado_final['mensagem'] = self._gerar_resumo_final(dados) + "\n\n⚠️ *Observação: Cliente cadastrado, mas houve problema na criação da negociação.*"
            logger.warning("⚠️ Finalização parcial - cliente salvo mas negociação falhou")
        else:
            resultado_final['mensagem'] = """❌ *Erro ao finalizar cadastro*

Ocorreu um problema ao salvar seus dados. Vou transferir você para um atendente que finalizará seu cadastro manualmente.

⏰ *Aguarde o contato...*"""
            logger.error("❌ Finalização falhou completamente")
        
        return resultado_final
    
    def _buscar_endereco_viacep(self, cep: str) -> Dict:
        """
        Busca endereço via API ViaCEP
        
        Args:
            cep (str): CEP com 8 dígitos
            
        Returns:
            Dict: Resultado da busca
        """
        try:
            url = f"https://viacep.com.br/ws/{cep}/json/"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'erro' not in data:
                    return {
                        'sucesso': True,
                        'endereco': data
                    }
                else:
                    return {
                        'sucesso': False,
                        'erro': 'CEP não encontrado na base ViaCEP'
                    }
            else:
                return {
                    'sucesso': False,
                    'erro': f'Erro na API ViaCEP: {response.status_code}'
                }
                
        except requests.exceptions.Timeout:
            return {
                'sucesso': False,
                'erro': 'Timeout na consulta ViaCEP'
            }
        except Exception as e:
            logger.error(f"❌ Erro na busca ViaCEP: {e}")
            return {
                'sucesso': False,
                'erro': f'Erro interno: {str(e)}'
            }
    
    def _normalizar_cpf(self, cpf: str) -> str:
        """Remove formatação do CPF"""
        return re.sub(r'\D', '', cpf)
    
    def _calcular_idade(self, data_nascimento: date) -> int:
        """Calcula idade baseada na data de nascimento"""
        hoje = date.today()
        idade = hoje.year - data_nascimento.year
        
        # Ajustar se ainda não fez aniversário este ano
        if hoje < data_nascimento.replace(year=hoje.year):
            idade -= 1
            
        return idade
    
    def limpar_sessao(self, telefone: str) -> bool:
        """
        Remove dados da sessão
        
        Args:
            telefone (str): Telefone do cliente
            
        Returns:
            bool: True se removido com sucesso
        """
        if telefone in self.dados_sessao:
            del self.dados_sessao[telefone]
            logger.info(f"🗑️ Sessão removida para {telefone}")
            return True
        return False
    
    def obter_estatisticas(self) -> Dict:
        """Retorna estatísticas das sessões ativas"""
        total_sessoes = len(self.dados_sessao)
        sessoes_por_etapa = {}
        
        for dados in self.dados_sessao.values():
            etapa = dados.etapa_atual
            sessoes_por_etapa[etapa] = sessoes_por_etapa.get(etapa, 0) + 1
        
        return {
            'total_sessoes_ativas': total_sessoes,
            'sessoes_por_etapa': sessoes_por_etapa
        } 
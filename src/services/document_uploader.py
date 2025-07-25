import os
import mimetypes
from datetime import datetime
import re
from supabase import create_client, Client
from dotenv import load_dotenv
from typing import Optional, Dict, Any
import requests
import base64
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.graphics.shapes import Drawing, Circle, String, Line, Rect
from reportlab.lib.styles import ParagraphStyle

load_dotenv()

class DocumentUploader:
    def __init__(self):
        """Inicializa o cliente Supabase"""
        self.supabase: Client = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY")
        )
        self.bucket_name = "ai-negotiations"
        
        # Tipos de arquivo permitidos
        self.allowed_types = {
            'pdf': ['application/pdf'],
            'image': ['image/jpeg', 'image/jpg', 'image/png'],
            'document': ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
        }
        
        # Tamanho máximo: 10MB
        self.max_size = 10 * 1024 * 1024

    def sanitize_filename(self, filename: str) -> str:
        sanitized = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        sanitized = re.sub(r'_{2,}', '_', sanitized)
        return sanitized.lower()

    def generate_unique_filename(self, negotiation_id: str, document_type_name: str, original_filename: str) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        doc_type_clean = self.sanitize_filename(document_type_name.replace(' ', '_'))
        original_clean = self.sanitize_filename(original_filename)
        return f"{negotiation_id}/documents/{timestamp}_{doc_type_clean}_{original_clean}"

    def validate_file(self, file_path: str) -> Dict[str, Any]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
        file_size = os.path.getsize(file_path)
        if file_size > self.max_size:
            raise ValueError(f"Arquivo muito grande. Máximo: {self.max_size/1024/1024:.1f}MB")
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            raise ValueError("Não foi possível detectar o tipo do arquivo")
        is_allowed = any(mime_type in types for types in self.allowed_types.values())
        if not is_allowed:
            allowed_list = [t for types in self.allowed_types.values() for t in types]
            raise ValueError(f"Tipo de arquivo não permitido. Permitidos: {allowed_list}")
        return {
            'size': file_size,
            'mime_type': mime_type,
            'filename': os.path.basename(file_path)
        }

    def get_negotiation_info(self, negotiation_id: str) -> Optional[Dict]:
        response = self.supabase.table('ai_negotiations').select('*').eq('id', negotiation_id).execute()
        if not response.data:
            raise ValueError(f"Negociação não encontrada: {negotiation_id}")
        return response.data[0]

    def get_document_type_info(self, document_type_id: str) -> Optional[Dict]:
        response = self.supabase.table('ai_document_types').select('*').eq('id', document_type_id).execute()
        if not response.data:
            raise ValueError(f"Tipo de documento não encontrado: {document_type_id}")
        return response.data[0]

    def upload_document(self, 
                       file_path: str, 
                       negotiation_id: str, 
                       document_type_id: str) -> Dict[str, Any]:
        try:
            print(f"🚀 Iniciando upload do documento: {file_path}")
            file_info = self.validate_file(file_path)
            print(f"✅ Arquivo validado: {file_info['size']} bytes, {file_info['mime_type']}")
            negotiation = self.get_negotiation_info(negotiation_id)
            print(f"✅ Negociação encontrada: {negotiation['client_name']}")
            doc_type = self.get_document_type_info(document_type_id)
            print(f"✅ Tipo de documento: {doc_type['name']}")
            unique_filename = self.generate_unique_filename(
                negotiation_id, 
                doc_type['name'], 
                file_info['filename']
            )
            print(f"📂 Nome do arquivo no storage: {unique_filename}")
            with open(file_path, 'rb') as file:
                storage_response = self.supabase.storage.from_(self.bucket_name).upload(
                    unique_filename, 
                    file,
                    file_options={
                        "content-type": file_info['mime_type']
                    }
                )
            if storage_response.status_code not in [200, 201]:
                raise Exception(f"Erro no upload: {storage_response}")
            print(f"☁️ Arquivo enviado para o storage com sucesso")
            
            # NOVO: Gerar resumo automático do documento
            resumo_ia = gerar_resumo_documento(file_path) or ""
            if resumo_ia:
                print(f"📝 Resumo IA gerado ({len(resumo_ia)} caracteres)")
            else:
                print(f"⚠️ Resumo IA não foi gerado")
            
            document_data = {
                'negotiation_id': negotiation_id,
                'document_type_id': document_type_id,
                'file_name': file_info['filename'],
                'file_path': unique_filename,
                'file_size': file_info['size'],
                'mime_type': file_info['mime_type'],
                'status': 'recebido',
                'client_name': negotiation['client_name'],
                'client_cpf': negotiation.get('client_cpf', ''),
                'resumo_ia': resumo_ia
            }
            db_response = self.supabase.table('ai_documents').insert(document_data).execute()
            if not db_response.data:
                self.supabase.storage.from_(self.bucket_name).remove([unique_filename])
                raise Exception("Erro ao salvar no banco de dados")
            document_saved = db_response.data[0]
            print(f"💾 Documento salvo no banco com ID: {document_saved['id']}")
            
            # NOVO: Gerar relatório de crédito (só se tiver CPF E não existir ainda)
            if negotiation.get('client_cpf'):
                try:
                    # Verificar se já existe relatório de crédito para esta negociação
                    credito_existente = self.supabase.table('ai_documents')\
                        .select('id')\
                        .eq('negotiation_id', negotiation_id)\
                        .eq('document_type_id', '62b19876-ae49-4803-952e-4a40471afd8e')\
                        .execute()
                    
                    if not credito_existente.data:
                        print("🏢 Gerando relatório de crédito...")
                        resultado_credito = analisar_credito_cliente(
                            nome=negotiation['client_name'],
                            cpf=negotiation.get('client_cpf', ''),
                            telefone=negotiation.get('client_phone', ''),
                            email=negotiation.get('client_email', '')
                        )
                        
                        if resultado_credito['success']:
                            # Upload do PDF para mesma pasta
                            pdf_filename = f"relatorio_credito_{negotiation_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                            storage_path = f"{negotiation_id}/{pdf_filename}"
                            
                            with open(resultado_credito['pdf_path'], 'rb') as pdf_file:
                                storage_response = self.supabase.storage.from_(self.bucket_name).upload(
                                    storage_path, 
                                    pdf_file,
                                    file_options={"content-type": "application/pdf"}
                                )
                            
                            if storage_response.status_code in [200, 201]:
                                print(f"✅ PDF de crédito salvo: {storage_path}")
                                
                                # Registrar na tabela ai_documents
                                credito_data = {
                                    'negotiation_id': negotiation_id,
                                    'document_type_id': '62b19876-ae49-4803-952e-4a40471afd8e',
                                    'file_name': pdf_filename,
                                    'file_path': storage_path,
                                    'file_size': os.path.getsize(resultado_credito['pdf_path']),
                                    'client_cpf': negotiation.get('client_cpf', ''),
                                    'resumo_ia': f"Score: {resultado_credito['score_credito']['pontos']} pontos ({resultado_credito['score_credito']['classe']})\nRenda: {resultado_credito['renda_presumida']['formato']}\nProtestos: {resultado_credito['protestos_publicos']['quantidade']}"
                                }
                                
                                db_response = self.supabase.table('ai_documents').insert(credito_data).execute()
                                if db_response.data:
                                    print(f"✅ Relatório de crédito registrado na tabela")
                                else:
                                    print(f"⚠️ Erro ao registrar relatório")
                            else:
                                print(f"⚠️ Erro ao salvar PDF no storage")
                                
                        else:
                            print(f"⚠️ Geração falhou: {resultado_credito.get('error', 'Erro desconhecido')}")
                    else:
                        print("✅ Relatório de crédito já existe para esta negociação")
                        
                except Exception as e:
                    print(f"⚠️ Erro na verificação/geração: {e}")
            else:
                print("⚠️ CPF não encontrado - relatório de crédito não gerado")
            
            return {
                'success': True,
                'document_id': document_saved['id'],
                'file_path': unique_filename,
                'storage_url': f"{os.getenv('SUPABASE_URL')}/storage/v1/object/public/{self.bucket_name}/{unique_filename}",
                'document_data': document_saved
            }
        except Exception as e:
            print(f"❌ Erro no upload: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

def get_negotiation_id_by_phone(phone: str) -> Optional[str]:
    """
    Busca o negotiation_id mais recente e ativo pelo telefone do cliente.
    
    Args:
        phone (str): Telefone do cliente (com ou sem formatação)
        
    Returns:
        Optional[str]: ID da negociação mais recente e ativa, ou None se não encontrada
    """
    try:
        # Limpa o telefone (deixa só números)
        clean_phone = re.sub(r'\D', '', phone) if phone else ""
        if not clean_phone:
            print(f"❌ Telefone inválido ou vazio: {phone}")
            return None
            
        print(f"🔍 Buscando negociação ativa por telefone: {clean_phone}")
        
        # Cria cliente Supabase
        supabase: Client = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY")
        )
        
        # Busca negociação mais recente e ativa pelo telefone
        response = supabase.table('ai_negotiations')\
            .select('id, client_name, created_at, status')\
            .eq('client_phone', clean_phone)\
            .neq('status', 'cancelada')\
            .order('created_at', desc=True)\
            .limit(1)\
            .execute()
            
        if not response.data:
            print(f"❌ Nenhuma negociação ativa encontrada para telefone: {clean_phone}")
            return None
            
        negotiation = response.data[0]
        print(f"✅ Negociação ativa encontrada: ID {negotiation['id']} - Cliente: {negotiation['client_name']} - Status: {negotiation['status']} - Criada em: {negotiation['created_at']}")
        return negotiation['id']
        
    except Exception as e:
        print(f"❌ Erro ao buscar negociação por telefone: {str(e)}")
        return None

def limpar_e_formatar_texto(texto: str) -> str:
    """
    Limpa e formata o texto extraído do PDF.
    Remove caracteres especiais e formata, mantendo tudo intacto.
    """
    import re
    
    # Remove caracteres especiais e símbolos
    texto = re.sub(r'[#|X*_\-=+~`@#$%^&*()\[\]{}|\\:;"\'<>?,./]', ' ', texto)
    
    # Remove códigos estranhos (como AU0562AB0501146, goo 25 FEV 2025)
    texto = re.sub(r'\b[A-Z]{2,}\d{2,}[A-Z0-9]*\b', '', texto)  # Remove códigos alfanuméricos
    texto = re.sub(r'\bgoo\s+\d+\s+[A-Z]+\s+\d+\b', '', texto)  # Remove "goo 25 FEV 2025"
    texto = re.sub(r'\b[A-Z]{2,}\d{2,}\b', '', texto)  # Remove códigos curtos
    
    # Remove caracteres gregos e estranhos
    texto = re.sub(r'[α-ωΑ-Ω]', '', texto)  # Remove caracteres gregos
    texto = re.sub(r'[ΚΥΚΛΙΚΗ]', '', texto)  # Remove palavras gregas específicas
    
    # Remove múltiplos espaços
    texto = re.sub(r'\s+', ' ', texto)
    
    # Remove espaços no início e fim
    texto = texto.strip()
    
    # Formata primeira letra maiúscula
    if texto:
        texto = texto[0].upper() + texto[1:]
    
    return texto


def traduzir_com_gpt(texto: str, max_chars: int = 50000) -> str:
    """
    Traduz e estrutura o texto do documento em uma única operação.
    Args:
        texto (str): Texto a ser traduzido e estruturado
        max_chars (int): Tamanho máximo do texto a processar
    Returns:
        str: Texto traduzido e estruturado ou original se falhar
    """
    try:
        import urllib.request
        import json
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("⚠️ OPENAI_API_KEY não encontrada")
            return texto[:max_chars] + "..." if len(texto) > max_chars else texto
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        # Prompt otimizado que combina tradução e estruturação SEM TABELAS
        prompt = f"""Você é um especialista em análise de documentos. Siga estas instruções:

1. TRADUÇÃO: Traduza este documento para português brasileiro.
2. ESTRUTURAÇÃO: Organize o texto traduzido identificando o tipo de documento e suas informações principais.

DOCUMENTO:
{texto[:max_chars]}

ESTRUTURA:
TIPO DE DOCUMENTO:
[Identificar: Relatório de Crédito, Comprovante de Residência, Comprovante de Renda, RG/CNH, Certidão]

IDENTIFICAÇÃO PESSOAL:
- Nome: [nome completo]
- CPF: [CPF formatado]
- RG: [se aplicável]
- Data Nascimento: [se aplicável]

ENDEREÇO E CONTATO:
- Endereço: [endereço completo]
- CEP: [CEP]
- Cidade/Estado: [localização]

DADOS ESPECÍFICOS:
[Informações específicas do tipo de documento identificado]

INFORMAÇÕES COMPLEMENTARES:
[Outras informações relevantes]

REGRAS IMPORTANTES:
- Manter TODAS as informações importantes
- Formatar datas como DD/MM/AAAA
- Formatar valores como R$ X.XXX,XX
- SEMPRE incluir CPF e endereço se disponíveis
- DEIXAR uma linha em branco entre cada seção
- NÃO usar ** nos títulos das seções
- NUNCA usar tabelas com pipes (|) ou hífens (---)
- SEMPRE usar apenas listas simples com hífen (-)
- Para valores múltiplos, use formato: "Item: Valor - Descrição: Detalhes"
- Mantenha formatação simples e legível para banco de dados

EXEMPLO DE FORMATAÇÃO CORRETA PARA DADOS TABULARES:
Em vez de tabelas, use listas simples assim:
- Código 101: Salário Base - 220h - Proventos: R$ 3.000,00
- Código 102: Hora Extra - 50h - Proventos: R$ 272,73
- Código 201: INSS - Descontos: R$ 330,00
- Código 202: Vale Transporte - Descontos: R$ 150,00
- Total Proventos: R$ 3.272,73
- Total Descontos: R$ 555,00
- Salário Líquido: R$ 2.717,73"""

        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": "Você é um especialista em análise de documentos. Traduza e estruture documentos em português brasileiro mantendo todas as informações importantes. IMPORTANTE: Use APENAS listas simples, NUNCA tabelas com pipes ou formatação complexa."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 4000,  # Reduzido para evitar erro HTTP 400
            "temperature": 0.3
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers=headers
        )
        
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            traducao = result['choices'][0]['message']['content'].strip()
            return traducao
            
    except Exception as e:
        print(f"⚠️ Erro na tradução GPT: {e}")
        return texto[:max_chars] + "..." if len(texto) > max_chars else texto


def gerar_resumo_documento(file_path: str) -> Optional[str]:
    """
    Extrai e traduz o texto completo do PDF usando Google Document AI + GPT.
    Args:
        file_path (str): Caminho para o arquivo PDF
    Returns:
        Optional[str]: Texto traduzido ou None se falhar
    """
    try:
        if not file_path.lower().endswith('.pdf'):
            print(f"⚠️ Arquivo não é PDF: {file_path}")
            return None
        print(f"🤖 Extraindo e traduzindo documento: {os.path.basename(file_path)}")
        credentials_path = "projeto-de-dados-440815-d498449cf1be.json"
        if not os.path.exists(credentials_path):
            print(f"❌ Arquivo de credenciais não encontrado: {credentials_path}")
            return None
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
        try:
            from google.api_core.client_options import ClientOptions
            from google.cloud import documentai
        except ImportError:
            print("❌ Google Document AI não instalado. Execute: pip install google-cloud-documentai")
            return None
        project_id = "889354502971"
        location = "us"
        processor_id = "c1b018153e86135e"
        opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
        client = documentai.DocumentProcessorServiceClient(client_options=opts)
        name = client.processor_path(project_id, location, processor_id)
        with open(file_path, "rb") as f:
            content = f.read()
        raw_doc = documentai.RawDocument(content=content, mime_type="application/pdf")
        process_options = documentai.ProcessOptions(
            individual_page_selector=documentai.ProcessOptions.IndividualPageSelector(
                pages=[1]
            )
        )
        request = documentai.ProcessRequest(
            name=name, 
            raw_document=raw_doc,
            field_mask="text,entities",
            process_options=process_options
        )
        result = client.process_document(request=request)
        document = result.document
        texto_extraido = document.text.strip()
        if not texto_extraido:
            print("⚠️ Nenhum texto extraído do documento")
            return None
        
        # NOVO: Limpar e formatar o texto antes da tradução
        print("🧹 Limpando e formatando texto...")
        texto_limpo = limpar_e_formatar_texto(texto_extraido)
        print(f"✅ Texto limpo e formatado ({len(texto_limpo)} caracteres)")
        
        traducao = traduzir_com_gpt(texto_limpo)
        print(f"✅ Tradução gerada com sucesso ({len(traducao)} caracteres)")
        return traducao
    except Exception as e:
        print(f"❌ Erro ao extrair/traduzir documento: {str(e)}")
        return None


def upload_negotiation_document(file_path: str, negotiation_id: str, document_type_id: str) -> Dict[str, Any]:
    uploader = DocumentUploader()
    return uploader.upload_document(file_path, negotiation_id, document_type_id) 

# ============================================================================
# CLASSE ASSERTIVA CLIENT
# ============================================================================

class AssertivaClient:
    def __init__(self):
        self.base_url = os.getenv('ASSERTIVA_BASE_URL', 'https://api.assertivasolucoes.com.br')
        self.auth_url = os.getenv('ASSERTIVA_AUTH_URL', 'https://api.assertivasolucoes.com.br/oauth2/v3/token')
        self.score_url = os.getenv('ASSERTIVA_SCORE_URL', 'https://api.assertivasolucoes.com.br/score/v3/pf/credito')
        self.access_token = None
        self.token_expiry = None

    def authenticate(self):
        """Autentica com a API Assertiva usando OAuth2 com Basic Auth"""
        try:
            print(" Autenticando com a API Assertiva...")
            
            # Criar Basic Auth com client_id e client_secret
            client_id = os.getenv('ASSERTIVA_CLIENT_ID')
            client_secret = os.getenv('ASSERTIVA_TOKEN')
            
            if not client_id or not client_secret:
                raise Exception("Credenciais não configuradas no arquivo .env")
            
            credentials = f"{client_id}:{client_secret}"
            base64_credentials = base64.b64encode(credentials.encode()).decode()
            
            auth_data = {
                'grant_type': 'client_credentials'
            }

            headers = {
                'Authorization': f'Basic {base64_credentials}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }

            response = requests.post(self.auth_url, data=auth_data, headers=headers)
            response.raise_for_status()

            data = response.json()
            if 'access_token' in data:
                self.access_token = data['access_token']
                # Token expira em 1 hora (3600 segundos)
                self.token_expiry = datetime.now().timestamp() + data.get('expires_in', 3600)
                print("✅ Autenticação realizada com sucesso!")
                return self.access_token
            else:
                raise Exception("Token de acesso não encontrado na resposta")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Erro na autenticação: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Resposta: {e.response.text}")
            raise

    def is_token_valid(self):
        """Verifica se o token ainda é válido"""
        return self.access_token and self.token_expiry and datetime.now().timestamp() < self.token_expiry

    def get_valid_token(self):
        """Obtém um token válido (renova se necessário)"""
        if not self.is_token_valid():
            self.authenticate()
        return self.access_token

    def consultar_score_credito(self, cpf, id_finalidade='2', opcoes='ACOES,POSITIVO'):
        """Consulta score de crédito restritivo por CPF"""
        try:
            print(f"🔍 Consultando score de crédito restritivo para CPF: {cpf}")
            print(f"📋 Finalidade: {id_finalidade} ({'Ciclo de crédito' if id_finalidade == '2' else 'Execução de contrato'})")
            print(f"🔧 Opções: {opcoes}")
            
            token = self.get_valid_token()
            url = f"{self.score_url}/{cpf}?idFinalidade={id_finalidade}&opcoes={opcoes}"
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }

            response = requests.get(url, headers=headers)
            response.raise_for_status()

            print("✅ Consulta realizada com sucesso!")
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Erro na consulta: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Resposta: {e.response.text}")
            raise

    def formatar_cpf(self, cpf):
        """Formata CPF para exibição (XXX.XXX.XXX-XX)"""
        cpf_limpo = ''.join(filter(str.isdigit, cpf))
        if len(cpf_limpo) == 11:
            return f"{cpf_limpo[:3]}.{cpf_limpo[3:6]}.{cpf_limpo[6:9]}-{cpf_limpo[9:]}"
        return cpf

# ============================================================================
# CLASSE PDF GENERATOR
# ============================================================================

class PDFGeneratorPro:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.setup_custom_styles()
        self.colors = {
            'primary': colors.HexColor('#1a365d'),
            'secondary': colors.HexColor('#2d3748'),
            'accent': colors.HexColor('#3182ce'),
            'success': colors.HexColor('#38a169'),
            'warning': colors.HexColor('#d69e2e'),
            'danger': colors.HexColor('#e53e3e'),
            'light': colors.HexColor('#f7fafc'),
            'gray': colors.HexColor('#4a5568'),
            'light_gray': colors.HexColor('#718096')
        }

    def setup_custom_styles(self):
        """Configura estilos customizados profissionais com tipografia moderna"""
        # Título principal moderno e centralizado
        if 'ModernTitle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='ModernTitle',
                parent=self.styles['Heading1'],
                fontSize=24,
                spaceAfter=8,
                alignment=TA_CENTER,
                textColor=colors.HexColor('#1a365d'),
                fontName='Helvetica-Bold',
                leading=28
            ))

        # Subtítulo elegante
        if 'ModernSubtitle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='ModernSubtitle',
                parent=self.styles['Heading2'],
                fontSize=14,
                spaceAfter=6,
                alignment=TA_CENTER,
                textColor=colors.HexColor('#4a5568'),
                fontName='Helvetica',
                leading=16
            ))

        # Seções modernas
        if 'ModernSection' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='ModernSection',
                parent=self.styles['Heading2'],
                fontSize=13,
                spaceAfter=12,
                spaceBefore=20,
                textColor=colors.HexColor('#2d3748'),
                fontName='Helvetica-Bold',
                leading=15
            ))

        # Títulos de tabela centralizados
        if 'TableHeader' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='TableHeader',
                parent=self.styles['Normal'],
                fontSize=11,
                fontName='Helvetica-Bold',
                alignment=TA_CENTER,
                textColor=colors.white,
                leading=13
            ))

        # Dados de tabela
        if 'TableData' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='TableData',
                parent=self.styles['Normal'],
                fontSize=10,
                fontName='Helvetica',
                leading=12
            ))

        # Valores monetários alinhados à direita
        if 'TableMoney' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='TableMoney',
                parent=self.styles['Normal'],
                fontSize=10,
                fontName='Helvetica-Bold',
                alignment=TA_RIGHT,
                textColor=colors.HexColor('#38a169'),
                leading=12
            ))

        # Rodapé discreto
        if 'Footer' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='Footer',
                parent=self.styles['Normal'],
                fontSize=8,
                fontName='Helvetica',
                alignment=TA_RIGHT,
                textColor=colors.HexColor('#718096'),
                leading=10
            ))

    def get_score_color(self, classe):
        """Retorna cor baseada na classe do score com gradientes"""
        colors_map = {
            'A': colors.HexColor('#38a169'),  # Verde
            'B': colors.HexColor('#3182ce'),  # Azul
            'C': colors.HexColor('#d69e2e'),  # Amarelo
            'D': colors.HexColor('#e53e3e'),  # Vermelho
            'E': colors.HexColor('#805ad5')   # Roxo
        }
        return colors_map.get(classe, colors.HexColor('#4a5568'))

    def create_score_gauge(self, score_value, max_score=1000):
        """Cria um gráfico de gauge moderno para o score"""
        drawing = Drawing(400, 180)
        
        # Calcular porcentagem
        percentage = min(score_value / max_score, 1.0)
        
        # Cores baseadas no score com gradiente azul
        if percentage >= 0.8:
            primary_color = colors.HexColor('#10B981')  # Verde esmeralda (ALTO = BOM)
            secondary_color = colors.HexColor('#059669')
        elif percentage >= 0.6:
            primary_color = colors.HexColor('#3B82F6')  # Azul moderno (MÉDIO-ALTO)
            secondary_color = colors.HexColor('#2563EB')
        elif percentage >= 0.4:
            primary_color = colors.HexColor('#F59E0B')  # Âmbar (MÉDIO)
            secondary_color = colors.HexColor('#D97706')
        elif percentage >= 0.2:
            primary_color = colors.HexColor('#F97316')  # Laranja (MÉDIO-BAIXO)
            secondary_color = colors.HexColor('#EA580C')
        else:
            primary_color = colors.HexColor('#EF4444')  # Vermelho (BAIXO = RUIM)
            secondary_color = colors.HexColor('#DC2626')
        
        # Círculo de fundo maior
        drawing.add(Circle(200, 90, 80, fillColor=colors.white, strokeColor=colors.HexColor('#E2E8F0'), strokeWidth=3))
        
        # Círculo interno com gradiente
        drawing.add(Circle(200, 90, 75, fillColor=primary_color, strokeColor=secondary_color, strokeWidth=2))
        
        # Efeito de gradiente (círculo interno mais claro)
        highlight_radius = 65
        drawing.add(Circle(200, 90, highlight_radius, fillColor=colors.HexColor('#FFFFFF'), strokeColor=colors.HexColor('#FFFFFF'), strokeWidth=0))
        
        # Valor do score em destaque no centro
        drawing.add(String(200, 90, f"{score_value} pontos", fontSize=18, fillColor=colors.HexColor('#64748B'), textAnchor='middle', fontName='Helvetica-Bold'))
        
        # Label "Score" abaixo
        drawing.add(String(200, 65, "Score", fontSize=14, fillColor=colors.white, textAnchor='middle', fontName='Helvetica-Bold'))
        
        return drawing

    def create_risk_chart(self, score_data):
        """Cria gráfico de risco ultra-moderno com design 3D e gradientes"""
        drawing = Drawing(450, 180)
        
        # Dados para o gráfico
        score_value = score_data.get('pontos', 0)
        max_score = 1000
        percentage = min(score_value / max_score, 1.0)
        
        # Cores modernas CORRIGIDAS (verde para alto, vermelho para baixo)
        if percentage >= 0.8:
            primary_color = colors.HexColor('#10B981')  # Verde esmeralda (ALTO = BOM)
            secondary_color = colors.HexColor('#059669')
        elif percentage >= 0.6:
            primary_color = colors.HexColor('#3B82F6')  # Azul moderno (MÉDIO-ALTO)
            secondary_color = colors.HexColor('#2563EB')
        elif percentage >= 0.4:
            primary_color = colors.HexColor('#F59E0B')  # Âmbar (MÉDIO)
            secondary_color = colors.HexColor('#D97706')
        elif percentage >= 0.2:
            primary_color = colors.HexColor('#F97316')  # Laranja (MÉDIO-BAIXO)
            secondary_color = colors.HexColor('#EA580C')
        else:
            primary_color = colors.HexColor('#EF4444')  # Vermelho (BAIXO = RUIM)
            secondary_color = colors.HexColor('#DC2626')
        
        # Grid moderno com linhas muito sutis
        for i in range(1, 6):
            y_pos = 30 + (i * 22)
            drawing.add(Line(25, y_pos, 475, y_pos, strokeColor=colors.HexColor('#F1F5F9'), strokeWidth=0.3))
        
        # Barra principal 3D com gradiente
        bar_width = 80
        bar_height = (score_value / max_score) * 110
        bar_x = 250 - (bar_width / 2)
        bar_y = 30 + (110 - bar_height)
        
        # Sombra da barra (mais sutil)
        bar_shadow_offset = 2
        drawing.add(Rect(bar_x + bar_shadow_offset, bar_y + bar_shadow_offset, bar_width, bar_height, 
                        fillColor=colors.HexColor('#E2E8F0'), strokeColor=colors.HexColor('#E2E8F0')))
        
        # Barra principal simples
        drawing.add(Rect(bar_x, bar_y, bar_width, bar_height, 
                        fillColor=primary_color, strokeColor=secondary_color, strokeWidth=1))
        
        # Efeito 3D - borda superior mais clara
        highlight_height = min(bar_height * 0.25, 6)
        drawing.add(Rect(bar_x, bar_y, bar_width, highlight_height, 
                        fillColor=colors.HexColor('#FFFFFF'), strokeColor=colors.HexColor('#FFFFFF'), strokeWidth=0))
        
        # Valor do score na barra
        if bar_height > 25:
            drawing.add(String(250, bar_y + (bar_height / 2), f"Score = {score_value}", 
                              fontSize=12, fillColor=colors.white, textAnchor='middle', fontName='Helvetica-Bold'))
        
        # Indicadores de faixa de risco
        risk_zones = [
            (0, 200, "BAIXO", colors.HexColor('#EF4444')),
            (200, 400, "MÉDIO-BAIXO", colors.HexColor('#F97316')),
            (400, 600, "MÉDIO", colors.HexColor('#F59E0B')),
            (600, 800, "MÉDIO-ALTO", colors.HexColor('#3B82F6')),
            (800, 1000, "ALTO", colors.HexColor('#10B981'))
        ]
        
        zone_width = 450 / 5
        
        for i, (min_val, max_val, label, color) in enumerate(risk_zones):
            zone_x = 25 + (i * zone_width)
            zone_height = 6
            zone_y = 25
            
            # Zona de risco
            drawing.add(Rect(zone_x, zone_y, zone_width, zone_height, 
                            fillColor=color, strokeColor=color))
            
            # Label da zona
            drawing.add(String(zone_x + (zone_width / 2), zone_y - 5, label, 
                              fontSize=8, fillColor=colors.HexColor('#4A5568'), textAnchor='middle', fontName='Helvetica-Bold'))
        
        return drawing

    def formatar_texto_longo(self, texto, max_chars=60):
        """Formata texto longo para caber em tabelas"""
        if not texto or len(texto) <= max_chars:
            return texto
        
        # Dividir em palavras e criar quebras naturais
        palavras = texto.split()
        linhas = []
        linha_atual = ""
        for palavra in palavras:
            if len(linha_atual + " " + palavra) <= max_chars:
                linha_atual += " " + palavra if linha_atual else palavra
            else:
                if linha_atual:
                    linhas.append(linha_atual)
                linha_atual = palavra
        if linha_atual:
            linhas.append(linha_atual)
        return "<br/>".join(linhas)

    def gerar_relatorio(self, cliente, dados_consulta, output_path=None):
        """Gera PDF profissional moderno com margens generosas e encoding UTF-8"""
        try:
            # Definir caminho de saída
            if not output_path:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"relatorio_credito_{cliente['documento'].replace('.', '').replace('-', '').replace('/', '')}_{timestamp}.pdf"
                output_path = os.path.join('relatorios', filename)

            # Criar diretório se não existir
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Criar documento PDF com margens generosas
            doc = SimpleDocTemplate(
                output_path, 
                pagesize=A4,
                leftMargin=1*inch,
                rightMargin=1*inch,
                topMargin=0.8*inch,
                bottomMargin=0.8*inch
            )
            story = []

            # Gerar conteúdo profissional
            story.extend(self.gerar_cabecalho_pro(cliente))
            story.extend(self.gerar_dashboard_executivo(dados_consulta))
            story.extend(self.gerar_analise_score(dados_consulta))
            story.extend(self.gerar_indicadores_financeiros(dados_consulta))
            story.extend(self.gerar_analise_risco(dados_consulta))
            story.extend(self.gerar_rodape_pro(dados_consulta))

            # Construir PDF
            doc.build(story)
            print(f"✅ PDF Profissional gerado com sucesso: {output_path}")
            return output_path

        except Exception as e:
            print(f"❌ Erro ao gerar PDF Profissional: {e}")
            raise

    def gerar_cabecalho_pro(self, cliente):
        """Gera cabeçalho profissional moderno com título centralizado e linha separadora"""
        elements = []

        # Título principal centralizado com fonte moderna
        elements.append(Paragraph('ASSERTIVA SOLUÇÕES', self.styles['ModernTitle']))
        elements.append(Paragraph('Relatório de Análise de Crédito', self.styles['ModernSubtitle']))
        elements.append(Paragraph('Score de Crédito Restritivo', self.styles['ModernSubtitle']))
        
        # Linha horizontal sutil para separar
        elements.append(Paragraph('<hr width="80%" color="#e2e8f0" thickness="1"/>', self.styles['Normal']))
        elements.append(Spacer(1, 20))

        # Dados do cliente com tabela moderna
        elements.append(Paragraph('DADOS DO CLIENTE', self.styles['ModernSection']))

        client_data = [
            ['Nome:', cliente['nome']],
            ['CPF:', cliente['documento']],
            ['Telefone:', cliente['telefone']],
            ['E-mail:', cliente['email']]
        ]
        
        client_table = Table(client_data, colWidths=[2.2*inch, 3.8*inch])
        client_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#4a5568')),
            ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#2d3748')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),
        ]))
        
        elements.append(client_table)
        elements.append(Spacer(1, 20))

        return elements

    def gerar_dashboard_executivo(self, dados_consulta):
        """Gera dashboard executivo moderno com tabelas legíveis e efeito zebra"""
        elements = []

        score = dados_consulta.get('resposta', {}).get('score')
        if score:
            # Card principal do score com design moderno
            score_value = score.get('pontos', 0)
            score_class = score.get('classe', 'N/A')
            score_color = self.get_score_color(score_class)
            
            # Dados do score em tabela moderna com quebras de linha
            descricao = self.formatar_texto_longo(score.get('faixa', {}).get('descricao', 'N/A'))
            
            score_data = [
                ['SCORE DE CRÉDITO'],
                ['Pontuação:', f"{score_value} pontos"],
                ['Classe:', f"{score_class}"],
                ['Faixa de Risco:', score.get('faixa', {}).get('titulo', 'N/A')],
                ['Descrição:', Paragraph(descricao, self.styles['Normal'])]
            ]

            score_table = Table(score_data, colWidths=[2.2*inch, 3.8*inch])
            score_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a365d')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('SPAN', (0, 0), (1, 0)),
                ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 1), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('TEXTCOLOR', (0, 1), (0, -1), colors.HexColor('#4a5568')),
                ('TEXTCOLOR', (1, 1), (1, -1), colors.HexColor('#2d3748')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
            ]))

            elements.append(score_table)
            elements.append(Spacer(1, 20))

            # Gráfico de score
            try:
                gauge = self.create_score_gauge(score_value)
                elements.append(gauge)
                elements.append(Spacer(1, 15))
            except Exception as e:
                print(f"Aviso: Não foi possível gerar gráfico: {e}")

        return elements

    def gerar_analise_score(self, dados_consulta):
        """Gera análise detalhada do score"""
        elements = []

        score = dados_consulta.get('resposta', {}).get('score')
        if score:
            # Detalhes técnicos em tabela moderna com quebras de linha
            descricao = self.formatar_texto_longo(score.get('faixa', {}).get('descricao', 'N/A'))
            
            details_data = [
                ['Pontuação Atual:', f"{score.get('pontos', 'N/A')} pontos"],
                ['Classe de Risco:', f"{score.get('classe', 'N/A')}"],
                ['Faixa:', score.get('faixa', {}).get('titulo', 'N/A')],
                ['Descrição:', Paragraph(descricao, self.styles['Normal'])]
            ]

            details_table = Table(details_data, colWidths=[2.2*inch, 3.8*inch])
            details_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#4a5568')),
                ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#2d3748')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),
            ]))

            elements.append(details_table)
            elements.append(Spacer(1, 20))

            # Gráfico de análise centralizado
            try:
                elements.append(Spacer(1, 15))
                chart = self.create_risk_chart(score)
                elements.append(chart)
                elements.append(Spacer(1, 20))
            except Exception as e:
                print(f"Aviso: Não foi possível gerar gráfico de análise: {e}")

        return elements

    def gerar_indicadores_financeiros(self, dados_consulta):
        """Gera indicadores financeiros com design moderno e valores monetários alinhados"""
        elements = []

        renda = dados_consulta.get('resposta', {}).get('rendaPresumida')
        if renda and renda.get('valor'):
            # Card de renda com design moderno
            renda_value = f"R$ {renda['valor']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            
            renda_data = [
                ['RENDA PRESUMIDA'],
                ['Valor Estimado:', renda_value]
            ]

            renda_table = Table(renda_data, colWidths=[2.2*inch, 3.8*inch])
            renda_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#38a169')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('SPAN', (0, 0), (1, 0)),
                ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 1), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('TEXTCOLOR', (0, 1), (0, -1), colors.HexColor('#4a5568')),
                ('TEXTCOLOR', (1, 1), (1, -1), colors.HexColor('#38a169')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
            ]))

            elements.append(renda_table)
            elements.append(Spacer(1, 20))

        return elements

    def gerar_analise_risco(self, dados_consulta):
        """Gera análise de risco com protestos públicos"""
        elements = []

        protestos = dados_consulta.get('resposta', {}).get('protestosPublicos')
        if protestos:
            qtd_protestos = protestos.get('qtdProtestos', 0)
            
            # Determinar nível de risco
            if qtd_protestos == 0:
                risk_level = "BAIXO"
                risk_color = colors.HexColor('#38a169')
                risk_status = "Sem pendências"
            elif qtd_protestos <= 2:
                risk_level = "MÉDIO"
                risk_color = colors.HexColor('#d69e2e')
                risk_status = "Pendências encontradas"
            else:
                risk_level = "ALTO"
                risk_color = colors.HexColor('#e53e3e')
                risk_status = "Múltiplas pendências"

            risk_data = [
                ['PROTESTOS PÚBLICOS'],
                ['Quantidade:', f"{qtd_protestos} protestos"],
                ['Nível de Risco:', risk_level],
                ['Status:', risk_status]
            ]

            if qtd_protestos > 0:
                risk_data.extend([
                    ['Primeira Ocorrência:', protestos.get('primeiraOcorrencia', 'N/A')],
                    ['Última Ocorrência:', protestos.get('ultimaOcorrencia', 'N/A')]
                ])

            risk_table = Table(risk_data, colWidths=[2.2*inch, 3.8*inch])
            risk_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), risk_color),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('SPAN', (0, 0), (1, 0)),
                ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 1), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('TEXTCOLOR', (0, 1), (0, -1), colors.HexColor('#4a5568')),
                ('TEXTCOLOR', (1, 1), (1, -1), colors.HexColor('#2d3748')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
            ]))

            elements.append(risk_table)
            elements.append(Spacer(1, 20))

        return elements

    def gerar_rodape_pro(self, dados_consulta):
        """Gera rodapé profissional moderno com data/hora de geração"""
        elements = []
        
        # Linha separadora elegante
        elements.append(Paragraph('<hr width="100%" color="#e2e8f0" thickness="1"/>', self.styles['Normal']))
        elements.append(Spacer(1, 15))

        # Copyright profissional
        elements.append(Paragraph('© 2025 | Relatório gerado automaticamente', self.styles['Footer']))

        return elements

# ============================================================================
# FUNÇÃO PRINCIPAL DE ANÁLISE DE CRÉDITO
# ============================================================================

def analisar_credito_cliente(nome: str, cpf: str, telefone: str, email: str) -> Dict[str, Any]:
    """
    Analisa crédito do cliente e gera relatório PDF profissional.
    
    Args:
        nome (str): Nome completo do cliente
        cpf (str): CPF do cliente (com ou sem formatação)
        telefone (str): Telefone do cliente
        email (str): Email do cliente
        
    Returns:
        Dict[str, Any]: Resultado da análise com dados do score e caminho do PDF
    """
    try:
        print(f"🏢 INICIANDO ANÁLISE DE CRÉDITO")
        print(f" Cliente: {nome}")
        print(f"🔍 CPF: {cpf}")
        print(f"📞 Telefone: {telefone}")
        print(f"📧 Email: {email}")
        print()
        
        # Limpar CPF (deixar só números)
        cpf_limpo = ''.join(filter(str.isdigit, cpf))
        if len(cpf_limpo) != 11:
            raise ValueError("CPF inválido")
        
        # Formatar CPF para exibição
        cpf_formatado = f"{cpf_limpo[:3]}.{cpf_limpo[3:6]}.{cpf_limpo[6:9]}-{cpf_limpo[9:]}"
        
        # Preparar dados do cliente
        cliente = {
            'nome': nome,
            'documento': cpf_formatado,
            'documento_limpo': cpf_limpo,
            'telefone': telefone,
            'email': email
        }
        
        # 1. CONSULTAR SCORE NA ASSERTIVA
        print("🔐 Consultando score de crédito na Assertiva...")
        client_assertiva = AssertivaClient()
        dados_consulta = client_assertiva.consultar_score_credito(
            cpf_limpo, 
            '2',  # Finalidade: Ciclo de crédito
            'ACOES,POSITIVO'  # Opções
        )
        
        print("✅ Consulta realizada com sucesso!")
        
        # 2. GERAR PDF PROFISSIONAL
        print("📄 Gerando relatório PDF profissional...")
        pdf_gen = PDFGeneratorPro()
        pdf_path = pdf_gen.gerar_relatorio(cliente, dados_consulta)
        
        print("✅ PDF gerado com sucesso!")
        
        # 3. PREPARAR RESULTADO
        score = dados_consulta.get('resposta', {}).get('score', {})
        renda = dados_consulta.get('resposta', {}).get('rendaPresumida', {})
        protestos = dados_consulta.get('resposta', {}).get('protestosPublicos', {})
        
        resultado = {
            'success': True,
            'cliente': cliente,
            'score_credito': {
                'pontos': score.get('pontos', 0),
                'classe': score.get('classe', 'N/A'),
                'faixa_risco': score.get('faixa', {}).get('titulo', 'N/A'),
                'descricao': score.get('faixa', {}).get('descricao', 'N/A')
            },
            'renda_presumida': {
                'valor': renda.get('valor', 0),
                'formato': f"R$ {renda.get('valor', 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') if renda.get('valor') else 'N/A'
            },
            'protestos_publicos': {
                'quantidade': protestos.get('qtdProtestos', 0),
                'primeira_ocorrencia': protestos.get('primeiraOcorrencia', 'N/A'),
                'ultima_ocorrencia': protestos.get('ultimaOcorrencia', 'N/A')
            },
            'pdf_path': pdf_path,
            'dados_completos': dados_consulta
        }
        
        print(f" Análise de crédito concluída com sucesso!")
        print(f"📊 Score: {resultado['score_credito']['pontos']} pontos ({resultado['score_credito']['classe']})")
        print(f"💰 Renda: {resultado['renda_presumida']['formato']}")
        print(f"⚠️ Protestos: {resultado['protestos_publicos']['quantidade']}")
        print(f" PDF: {pdf_path}")
        
        return resultado
        
    except Exception as e:
        print(f"❌ Erro na análise de crédito: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'cliente': {
                'nome': nome,
                'documento': cpf,
                'telefone': telefone,
                'email': email
            }
        }


    
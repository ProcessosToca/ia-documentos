import os
import mimetypes
from datetime import datetime
import re
from supabase import create_client, Client
from dotenv import load_dotenv
from typing import Optional, Dict, Any

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

def traduzir_com_gpt(texto: str, max_chars: int = 50000) -> str:
    """
    Traduz texto para português usando GPT-3.5-turbo.
    Args:
        texto (str): Texto a ser traduzido
        max_chars (int): Tamanho máximo do texto a traduzir (50.000 chars)
    Returns:
        str: Texto traduzido ou original se falhar
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
        prompt = f"Traduza o texto abaixo para português brasileiro, mantendo a formatação e todas as informações:\n\n{texto[:max_chars]}"
        data = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {
                    "role": "system",
                    "content": "Você é um tradutor profissional. Traduza fielmente o texto para português brasileiro, sem omitir informações."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 18000,  # Aumentado para suportar textos maiores
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
        traducao = traduzir_com_gpt(texto_extraido)
        print(f"✅ Tradução gerada com sucesso ({len(traducao)} caracteres)")
        return traducao
    except Exception as e:
        print(f"❌ Erro ao extrair/traduzir documento: {str(e)}")
        return None

def gerar_resumo_gpt(texto: str, max_chars: int = 500) -> str:
    """
    Gera resumo do texto usando GPT-3.5-turbo.
    Args:
        texto (str): Texto a ser resumido
        max_chars (int): Tamanho máximo do resumo
    Returns:
        str: Resumo do texto
    """
    try:
        import urllib.request
        import json
        # Verificar API Key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("⚠️ OPENAI_API_KEY não encontrada")
            return texto[:max_chars] + "..." if len(texto) > max_chars else texto
        # Configurar requisição
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        # Preparar prompt
        prompt = f"""Analise este documento e crie um resumo conciso em português brasileiro.\n\nDocumento:\n{texto[:13000]}  # Limitar para não exceder tokens\n\nResumo (máximo {max_chars} caracteres):"""
        data = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {
                    "role": "system",
                    "content": "Você é um assistente especializado em análise de documentos. Crie resumos concisos e informativos sem perder informações importantes."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 300,
            "temperature": 0.3
        }
        # Fazer requisição
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers=headers
        )
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            resumo = result['choices'][0]['message']['content'].strip()
            # Limitar tamanho se necessário
            if len(resumo) > max_chars:
                resumo = resumo[:max_chars-3] + "..."
            return resumo
    except Exception as e:
        print(f"⚠️ Erro na geração de resumo GPT: {e}")
        # Fallback: retorna texto truncado
        return texto[:max_chars] + "..." if len(texto) > max_chars else texto


def upload_negotiation_document(file_path: str, negotiation_id: str, document_type_id: str) -> Dict[str, Any]:
    uploader = DocumentUploader()
    return uploader.upload_document(file_path, negotiation_id, document_type_id) 
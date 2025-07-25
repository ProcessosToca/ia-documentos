import os
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from supabase import create_client, Client
from dotenv import load_dotenv
import re

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
        """Sanitiza o nome do arquivo removendo caracteres especiais"""
        # Remove caracteres especiais, mantém apenas letras, números, pontos e underscores
        sanitized = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        # Remove múltiplos underscores consecutivos
        sanitized = re.sub(r'_{2,}', '_', sanitized)
        return sanitized.lower()

    def generate_unique_filename(self, negotiation_id: str, document_type_name: str, original_filename: str) -> str:
        """Gera nome único para o arquivo seguindo o padrão estabelecido"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Sanitiza o nome do tipo de documento
        doc_type_clean = self.sanitize_filename(document_type_name.replace(' ', '_'))
        
        # Sanitiza o nome original
        original_clean = self.sanitize_filename(original_filename)
        
        # Padrão: negotiation_id/documents/timestamp_doctype_originalname
        return f"{negotiation_id}/documents/{timestamp}_{doc_type_clean}_{original_clean}"

    def validate_file(self, file_path: str) -> Dict[str, Any]:
        """Valida o arquivo antes do upload"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
        
        # Verifica tamanho
        file_size = os.path.getsize(file_path)
        if file_size > self.max_size:
            raise ValueError(f"Arquivo muito grande. Máximo: {self.max_size/1024/1024:.1f}MB")
        
        # Detecta tipo MIME
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            raise ValueError("Não foi possível detectar o tipo do arquivo")
        
        # Verifica se o tipo é permitido
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
        """Busca informações da negociação"""
        response = self.supabase.table('ai_negotiations').select('*').eq('id', negotiation_id).execute()
        
        if not response.data:
            raise ValueError(f"Negociação não encontrada: {negotiation_id}")
        
        return response.data[0]

    def get_document_type_info(self, document_type_id: str) -> Optional[Dict]:
        """Busca informações do tipo de documento"""
        response = self.supabase.table('ai_document_types').select('*').eq('id', document_type_id).execute()
        
        if not response.data:
            raise ValueError(f"Tipo de documento não encontrado: {document_type_id}")
        
        return response.data[0]

    def upload_document(self, 
                       file_path: str, 
                       negotiation_id: str, 
                       document_type_id: str) -> Dict[str, Any]:
        """
        Função principal para upload de documento
        
        Args:
            file_path: Caminho local do arquivo
            negotiation_id: ID da negociação
            document_type_id: ID do tipo de documento
        
        Returns:
            Dict com informações do documento salvo
        """
        try:
            print(f"🚀 Iniciando upload do documento: {file_path}")
            
            # 1. Validar arquivo
            file_info = self.validate_file(file_path)
            print(f"✅ Arquivo validado: {file_info['size']} bytes, {file_info['mime_type']}")
            
            # 2. Verificar se negociação existe
            negotiation = self.get_negotiation_info(negotiation_id)
            print(f"✅ Negociação encontrada: {negotiation['client_name']}")
            
            # 3. Verificar tipo de documento
            doc_type = self.get_document_type_info(document_type_id)
            print(f"✅ Tipo de documento: {doc_type['name']}")
            
            # 4. Gerar nome único
            unique_filename = self.generate_unique_filename(
                negotiation_id, 
                doc_type['name'], 
                file_info['filename']
            )
            print(f"📂 Nome do arquivo no storage: {unique_filename}")
            
            # 5. Fazer upload para o storage
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
            
            # 6. Salvar metadados na tabela ai_documents
            document_data = {
                'negotiation_id': negotiation_id,
                'document_type_id': document_type_id,
                'file_name': file_info['filename'],
                'file_path': unique_filename,
                'file_size': file_info['size'],
                'mime_type': file_info['mime_type'],
                'status': 'recebido',  # Status inicial
                'client_name': negotiation['client_name'],
                'client_cpf': negotiation.get('client_cpf', '')
            }
            
            db_response = self.supabase.table('ai_documents').insert(document_data).execute()
            
            if not db_response.data:
                # Se falhou o banco, tenta remover do storage
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

# Função de conveniência para uso direto
def upload_negotiation_document(file_path: str, negotiation_id: str, document_type_id: str) -> Dict[str, Any]:
    """
    Função simplificada para upload de documento
    
    Exemplo de uso:
    result = upload_negotiation_document(
        file_path="./documento.pdf",
        negotiation_id="123e4567-e89b-12d3-a456-426614174000",
        document_type_id="456e7890-e89b-12d3-a456-426614174000"
    )
    """
    uploader = DocumentUploader()
    return uploader.upload_document(file_path, negotiation_id, document_type_id)

def test_upload_real_document():
    """
    Teste com dados reais: upload de documento da pasta Clientes/Documentos
    para a negociação do cliente Amadeu Silva
    """
    print("🚀 TESTE DE UPLOAD COM DADOS REAIS")
    print("=" * 60)
    
    # Dados reais da negociação
    negotiation_id = "756cd770-2186-481d-a378-2d8274be2bbe"
    client_name = "Amadeu Silva Filho"
    client_phone = "5514996960709"
    
    print(f"📋 NEGOCIAÇÃO: {negotiation_id}")
    print(f"👤 CLIENTE: {client_name}")
    print(f"📞 TELEFONE: {client_phone}")
    print()
    
    try:
        # 1. Inicializar uploader
        uploader = DocumentUploader()
        
        # 2. Buscar tipo de documento "RG" no Supabase
        print("🔍 Buscando tipo de documento 'RG'...")
        try:
            doc_type_response = uploader.supabase.table('ai_document_types').select('*').eq('name', 'RG').execute()
            if not doc_type_response.data:
                print("❌ Tipo de documento 'RG' não encontrado. Tentando 'RG / CNH'...")
                doc_type_response = uploader.supabase.table('ai_document_types').select('*').eq('name', 'RG / CNH').execute()
            
            if not doc_type_response.data:
                print("❌ Nenhum tipo de documento RG encontrado. Usando primeiro tipo disponível...")
                doc_type_response = uploader.supabase.table('ai_document_types').select('*').limit(1).execute()
            
            if not doc_type_response.data:
                raise Exception("Nenhum tipo de documento encontrado no sistema")
            
            document_type = doc_type_response.data[0]
            document_type_id = document_type['id']
            print(f"✅ Tipo de documento encontrado: {document_type['name']} (ID: {document_type_id})")
            
        except Exception as e:
            print(f"❌ Erro ao buscar tipo de documento: {e}")
            return
        
        # 3. Listar arquivos na pasta Clientes/Documentos
        documentos_path = "Clientes/Documentos"
        if not os.path.exists(documentos_path):
            print(f"❌ Pasta não encontrada: {documentos_path}")
            return
        
        arquivos = [f for f in os.listdir(documentos_path) if f.endswith('.pdf')]
        if not arquivos:
            print(f"❌ Nenhum arquivo PDF encontrado em {documentos_path}")
            return
        
        # Usar o primeiro arquivo
        arquivo_teste = arquivos[0]
        file_path = os.path.join(documentos_path, arquivo_teste)
        
        print(f"📄 Arquivo para teste: {arquivo_teste}")
        print(f"📂 Caminho completo: {file_path}")
        print()
        
        # 4. Fazer upload
        print("📤 Iniciando upload...")
        result = uploader.upload_document(
            file_path=file_path,
            negotiation_id=negotiation_id,
            document_type_id=document_type_id
        )
        
        # 5. Mostrar resultado
        print("\n" + "=" * 60)
        print("📊 RESULTADO DO TESTE")
        print("=" * 60)
        
        if result.get('success'):
            print("✅ UPLOAD REALIZADO COM SUCESSO!")
            print(f"   📄 Documento ID: {result['document_id']}")
            print(f"   📂 Caminho no Storage: {result['file_path']}")
            print(f"   🔗 URL: {result['storage_url']}")
            print(f"   👤 Cliente: {client_name}")
            print(f"   📋 Negociação: {negotiation_id}")
            print(f"   🏷️ Tipo: {document_type['name']}")
        else:
            print("❌ ERRO NO UPLOAD:")
            print(f"   {result.get('error', 'Erro desconhecido')}")
        
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Erro geral no teste: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Executar teste com dados reais
    test_upload_real_document()

import os
from datetime import datetime, date
from supabase import create_client, Client
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Configuração do Supabase
SUPABASE_URL = "https://rqyyoofuwrwwfcuxfjwu.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJxeXlvb2Z1d3J3d2ZjdXhmand1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTAwODk2MjUsImV4cCI6MjA2NTY2NTYyNX0.lBOrYvRIGEhLLMgcaaooS9-w2M8VAZW_4rQYFxc6abE"

def conectar_supabase():
    """Conecta ao Supabase"""
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Conectado ao Supabase com sucesso!")
        return supabase
    except Exception as e:
        print(f"❌ Erro ao conectar ao Supabase: {e}")
        return None

def listar_corretores(supabase):
    """Lista todos os corretores cadastrados"""
    print("\n📋 LISTANDO CORRETORES:")
    print("-" * 50)
    
    try:
        result = supabase.table('system_users').select('*').execute()
        if result.data:
            for i, corretor in enumerate(result.data, 1):
                print(f"{i}. {corretor['full_name']} ({corretor['email']})")
                print(f"   ID: {corretor['id']}")
                print(f"   Role: {corretor['role']}")
                print(f"   Ativo: {'Sim' if corretor['is_active'] else 'Não'}")
                print(f"   Criado em: {corretor['created_at']}")
                print()
            return result.data
        else:
            print("   Nenhum corretor encontrado")
            return []
    except Exception as e:
        print(f"❌ Erro ao listar corretores: {e}")
        return []

def selecionar_corretor(corretores):
    """Permite selecionar um corretor da lista"""
    if not corretores:
        return None
    
    print("🎯 SELECIONANDO CORRETOR:")
    corretor_selecionado = corretores[0]  # Seleciona o primeiro
    print(f"   Selecionado: {corretor_selecionado['full_name']}")
    print(f"   ID: {corretor_selecionado['id']}")
    return corretor_selecionado['id']

def listar_propriedades(supabase):
    """Lista todas as propriedades cadastradas"""
    print("\n🏠 LISTANDO PROPRIEDADES:")
    print("-" * 50)
    
    try:
        result = supabase.table('properties').select('*').execute()
        if result.data:
            for i, prop in enumerate(result.data, 1):
                print(f"{i}. {prop['title']}")
                print(f"   ID: {prop['id']}")
                print(f"   Tipo: {prop['property_type']}")
                print(f"   Preço: R$ {prop['price']}")
                print(f"   Bairro: {prop['neighborhood']}")
                print(f"   Endereço: {prop['address']}")
                print(f"   Status: {prop['status']}")
                print(f"   Quartos: {prop['bedrooms']} | Banheiros: {prop['bathrooms']}")
                print(f"   Área: {prop['area_sqm']}m²")
                print()
            return result.data
        else:
            print("   Nenhuma propriedade encontrada")
            return []
    except Exception as e:
        print(f"❌ Erro ao listar propriedades: {e}")
        return []

def selecionar_propriedade(propriedades):
    """Permite selecionar uma propriedade da lista"""
    if not propriedades:
        return None
    
    print("🎯 SELECIONANDO PROPRIEDADE:")
    prop_selecionada = propriedades[0]  # Seleciona a primeira
    print(f"   Selecionada: {prop_selecionada['title']}")
    print(f"   ID: {prop_selecionada['id']}")
    print(f"   Preço: R$ {prop_selecionada['price']}")
    return prop_selecionada['id']

def listar_tipos_documentos(supabase):
    """Lista todos os tipos de documentos cadastrados"""
    print("\n📄 LISTANDO TIPOS DE DOCUMENTOS:")
    print("-" * 50)
    
    try:
        result = supabase.table('ai_document_types').select('*').execute()
        if result.data:
            for i, doc_type in enumerate(result.data, 1):
                print(f"{i}. {doc_type['name']}")
                print(f"   ID: {doc_type['id']}")
                print(f"   Descrição: {doc_type['description']}")
                print(f"   Obrigatório: {'Sim' if doc_type['required'] else 'Não'}")
                print(f"   Ativo: {'Sim' if doc_type['is_active'] else 'Não'}")
                print()
            return result.data
        else:
            print("   Nenhum tipo de documento encontrado")
            return []
    except Exception as e:
        print(f"❌ Erro ao listar tipos de documentos: {e}")
        return []

def buscar_tipo_documento_por_nome(supabase, nome_documento):
    """Busca um tipo de documento específico pelo nome"""
    print(f"\n🔍 BUSCANDO TIPO DE DOCUMENTO: {nome_documento}")
    print("-" * 50)
    
    try:
        result = supabase.table('ai_document_types').select('*').eq('name', nome_documento).execute()
        if result.data:
            doc_type = result.data[0]
            print(f"✅ Encontrado:")
            print(f"   Nome: {doc_type['name']}")
            print(f"   ID: {doc_type['id']}")
            print(f"   Descrição: {doc_type['description']}")
            print(f"   Obrigatório: {'Sim' if doc_type['required'] else 'Não'}")
            return doc_type['id']
        else:
            print(f"❌ Tipo de documento '{nome_documento}' não encontrado")
            return None
    except Exception as e:
        print(f"❌ Erro ao buscar tipo de documento: {e}")
        return None

def cadastrar_cliente(supabase):
    """Cadastra um novo cliente"""
    cliente_data = {
        "nome": "Vinícius Garcia",
        "cpf": "123.456.789-01",
        "email": "vinicius.garcia@email.com",
        "telefone": "(14) 99999-9999",
        "data_nascimento": "1990-05-15",
        "endereco": "Rua das Flores, 123",
        "cidade": "Marília",
        "estado": "SP",
        "cep": "17500-000"
    }
    
    print("\n👤 CADASTRANDO CLIENTE:")
    print("-" * 50)
    
    try:
        result = supabase.table('clientes').insert(cliente_data).execute()
        if result.data:
            cliente_id = result.data[0]['id']
            print(f"✅ Cliente cadastrado com sucesso!")
            print(f"   Nome: {cliente_data['nome']}")
            print(f"   ID: {cliente_id}")
            print(f"   Email: {cliente_data['email']}")
            print(f"   Telefone: {cliente_data['telefone']}")
            return cliente_id
        return None
    except Exception as e:
        print(f"❌ Erro ao cadastrar cliente: {e}")
        return None

def criar_negociacao(supabase, cliente_id, property_id, broker_id):
    """Cria uma nova negociação"""
    negociacao_data = {
        "client_name": "Vinícius Garcia",
        "client_phone": "(14) 99999-9999",
        "client_email": "vinicius.garcia@email.com",
        "property_id": property_id,
        "rental_modality": "residencial",
        "status": "coletando_documentos",
        "broker_id": broker_id,
        "metadata": {
            "cliente_id": cliente_id,
            "origem": "cadastro_teste",
            "observacoes": "Cliente teste - Vinícius Garcia"
        }
    }
    
    print("\n📋 CRIANDO NEGOCIAÇÃO:")
    print("-" * 50)
    
    try:
        result = supabase.table('ai_negotiations').insert(negociacao_data).execute()
        if result.data:
            negotiation_id = result.data[0]['id']
            print(f"✅ Negociação criada com sucesso!")
            print(f"   ID: {negotiation_id}")
            print(f"   Cliente: {negociacao_data['client_name']}")
            print(f"   Status: {negociacao_data['status']}")
            print(f"   Modalidade: {negociacao_data['rental_modality']}")
            return negotiation_id
        return None
    except Exception as e:
        print(f"❌ Erro ao criar negociação: {e}")
        return None

def inserir_conversas(supabase, negotiation_id):
    """Insere conversas entre IA e cliente"""
    conversas = [
        {
            "negotiation_id": negotiation_id,
            "conversation_type": "ia_cliente",
            "sender": "cliente",
            "message": "Olá! Tenho interesse no imóvel que vocês anunciaram. Gostaria de mais informações.",
            "timestamp": "2024-12-30T10:00:00Z"
        },
        {
            "negotiation_id": negotiation_id,
            "conversation_type": "ia_cliente", 
            "sender": "ia",
            "message": "Olá Vinícius! Fico feliz com seu interesse! Para prosseguirmos, preciso de alguns documentos. Você pode enviar seu RG, CPF e comprovante de renda?",
            "timestamp": "2024-12-30T10:02:00Z"
        },
        {
            "negotiation_id": negotiation_id,
            "conversation_type": "ia_cliente",
            "sender": "cliente", 
            "message": "Claro! Vou enviar meu RG agora. Os outros documentos posso enviar amanhã?",
            "timestamp": "2024-12-30T10:05:00Z"
        },
        {
            "negotiation_id": negotiation_id,
            "conversation_type": "ia_cliente",
            "sender": "ia",
            "message": "Perfeito! Pode enviar o RG agora e os demais documentos até amanhã. Vou aguardar!",
            "timestamp": "2024-12-30T10:06:00Z"
        },
        {
            "negotiation_id": negotiation_id,
            "conversation_type": "ia_cliente",
            "sender": "cliente",
            "message": "Documento enviado! Muito obrigado pelo atendimento.",
            "timestamp": "2024-12-30T10:10:00Z"
        }
    ]
    
    print("\n💬 INSERINDO CONVERSAS:")
    print("-" * 50)
    
    try:
        result = supabase.table('ai_conversations').insert(conversas).execute()
        if result.data:
            print(f"✅ {len(conversas)} conversas inseridas com sucesso!")
            for i, conversa in enumerate(conversas, 1):
                print(f"   {i}. {conversa['sender'].upper()}: {conversa['message'][:50]}...")
            return True
        return False
    except Exception as e:
        print(f"❌ Erro ao inserir conversas: {e}")
        return False

# VERSÃO MAIS SIMPLES - Se tudo falhar
def fazer_upload_documento(supabase, negotiation_id):
    """Versão mais simples do upload"""
    caminho_arquivo = "Documentos Clientes/RG_ViniciusGarcia.pdf"
    
    print("\n📤 UPLOAD SIMPLES:")
    print("-" * 40)
    
    if not os.path.exists(caminho_arquivo):
        print(f"❌ Arquivo não encontrado")
        return None
    
    try:
        with open(caminho_arquivo, 'rb') as file:
            file_content = file.read()
        
        storage_path = f"negotiations/{negotiation_id}/RG_ViniciusGarcia.pdf"
        
        # Método mais direto
        result = supabase.storage.from_('ai-negotiations').upload(
            storage_path,
            file_content
        )
        
        print(f"Resultado: {result}")
        return storage_path if result else None
        
    except Exception as e:
        print(f"Erro: {e}")
        return None



def registrar_documento(supabase, negotiation_id, file_path, document_type_id):
    """Registra o documento na tabela ai_documents"""
    documento_data = {
        "negotiation_id": negotiation_id,
        "document_type_id": document_type_id,
        "file_name": "RG_ViniciusGarcia.pdf",
        "file_path": file_path,
        "file_size": os.path.getsize("Documentos Clientes/RG_ViniciusGarcia.pdf") if os.path.exists("Documentos Clientes/RG_ViniciusGarcia.pdf") else None,
        "mime_type": "application/pdf",
        "status": "recebido",
        "validation_result": {
            "documento": "RG",
            "nome": "Vinícius Garcia",
            "status": "documento_recebido"
        }
    }
    
    print("\n💾 REGISTRANDO DOCUMENTO NO BANCO:")
    print("-" * 50)
    
    try:
        result = supabase.table('ai_documents').insert(documento_data).execute()
        if result.data:
            doc_id = result.data[0]['id']
            print(f"✅ Documento registrado com sucesso!")
            print(f"   ID: {doc_id}")
            print(f"   Arquivo: {documento_data['file_name']}")
            print(f"   Status: {documento_data['status']}")
            print(f"   Tamanho: {documento_data['file_size']} bytes")
            return doc_id
        return None
    except Exception as e:
        print(f"❌ Erro ao registrar documento: {e}")
        return None

def resumo_final(cliente_id, negotiation_id, corretores, propriedades, tipos_documentos):
    """Mostra um resumo final com todas as informações"""
    print("\n" + "=" * 60)
    print("🎉 RESUMO FINAL - CADASTRO COMPLETO")
    print("=" * 60)
    
    print(f"👤 CLIENTE CADASTRADO:")
    print(f"   ID: {cliente_id}")
    print(f"   Nome: Vinícius Garcia")
    print(f"   Email: vinicius.garcia@email.com")
    
    print(f"\n📋 NEGOCIAÇÃO CRIADA:")
    print(f"   ID: {negotiation_id}")
    print(f"   Status: coletando_documentos")
    
    print(f"\n👥 TOTAL DE CORRETORES NO SISTEMA: {len(corretores)}")
    print(f"🏠 TOTAL DE PROPRIEDADES NO SISTEMA: {len(propriedades)}")
    print(f"📄 TOTAL DE TIPOS DE DOCUMENTOS: {len(tipos_documentos)}")
    
    print(f"\n✅ AÇÕES REALIZADAS:")
    print(f"   • Cliente cadastrado na tabela 'clientes'")
    print(f"   • Negociação criada na tabela 'ai_negotiations'")
    print(f"   • 5 conversas inseridas na tabela 'ai_conversations'")
    print(f"   • Documento RG enviado para Supabase Storage")
    print(f"   • Documento registrado na tabela 'ai_documents'")
    
    print("=" * 60)

def main():
    """Função principal"""
    print("🚀 SISTEMA DE CADASTRO COMPLETO - VERSÃO MELHORADA")
    print("=" * 60)
    
    # 1. Conectar ao Supabase
    supabase = conectar_supabase()
    if not supabase:
        return
    
    # 2. Listar e selecionar corretor
    corretores = listar_corretores(supabase)
    broker_id = selecionar_corretor(corretores)
    if not broker_id:
        print("❌ Nenhum corretor disponível")
        return
    
    # 3. Listar e selecionar propriedade
    propriedades = listar_propriedades(supabase)
    property_id = selecionar_propriedade(propriedades)
    if not property_id:
        print("❌ Nenhuma propriedade disponível")
        return
    
    # 4. Listar tipos de documentos e buscar RG
    tipos_documentos = listar_tipos_documentos(supabase)
    document_type_id = buscar_tipo_documento_por_nome(supabase, "RG")
    if not document_type_id:
        print("❌ Tipo de documento RG não encontrado")
        return
    
    # 5. Cadastrar cliente
    cliente_id = cadastrar_cliente(supabase)
    if not cliente_id:
        return
    
    # 6. Criar negociação
    negotiation_id = criar_negociacao(supabase, cliente_id, property_id, broker_id)
    if not negotiation_id:
        return
    
    # 7. Inserir conversas
    inserir_conversas(supabase, negotiation_id)
    
    # 8. Upload do documento
    file_path = fazer_upload_documento(supabase, negotiation_id)
    if not file_path:
        return
    
    # 9. Registrar documento na tabela
    registrar_documento(supabase, negotiation_id, file_path, document_type_id)
    
    # 10. Mostrar resumo final
    resumo_final(cliente_id, negotiation_id, corretores, propriedades, tipos_documentos)

if __name__ == "__main__":
    main()

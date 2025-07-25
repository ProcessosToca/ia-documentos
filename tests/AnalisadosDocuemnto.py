from typing import Optional
from google.api_core.client_options import ClientOptions
from google.cloud import documentai
import os
import json
import tkinter as tk
from tkinter import filedialog
import urllib.parse
import urllib.request

# Credenciais
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "projeto-de-dados-440815-d498449cf1be.json"

# Configura OpenAI API Key se não existir
if not os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = "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"

def selecionar_arquivo():
    """Seleciona arquivo PDF"""
    root = tk.Tk()
    root.withdraw()
    arquivo = filedialog.askopenfilename(
        title="Selecione PDF",
        filetypes=[("PDF", "*.pdf")]
    )
    root.destroy()
    return arquivo

def traduzir_com_gpt(texto):
    """Traduz texto para português usando GPT via API direta"""
    try:
        import json as json_module
        
        # Pega chave da variável de ambiente
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("⚠️ OPENAI_API_KEY não encontrada no ambiente")
            return texto
        
        # Configuração da API
        url = "https://api.openai.com/v1/chat/completions"
        
        # Dados da requisição
        data = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {
                    "role": "system",
                    "content": "Você é um tradutor especializado. Traduza o texto para português brasileiro mantendo a formatação original."
                },
                {
                    "role": "user",
                    "content": f"Traduza este texto para português brasileiro:\n\n{texto}"
                }
            ],
            "max_tokens": 1000,
            "temperature": 0.3
        }
        
        # Configura requisição
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        # Faz requisição
        req = urllib.request.Request(
            url,
            data=json_module.dumps(data).encode('utf-8'),
            headers=headers
        )
        
        with urllib.request.urlopen(req) as response:
            result = json_module.loads(response.read().decode())
            return result['choices'][0]['message']['content'].strip()
            
    except Exception as e:
        print(f"⚠️ Erro na tradução GPT: {e}")
        return texto  # Retorna original se falhar

def analisar_documento(
    project_id="889354502971",
    location="us", 
    processor_id="c1b018153e86135e",
    file_path=None
):
    """Analisador de IA - Versão com Tradução GPT"""
    
    if not file_path:
        print("📁 Selecione um PDF...")
        file_path = selecionar_arquivo()
        if not file_path:
            return
    
    print("🤖 ANALISANDO DOCUMENTO...")
    print(f"📄 {os.path.basename(file_path)}")
    
    try:
        # Configura cliente
        opts = ClientOptions(api_endpoint=f"{location}-documentai.googleapis.com")
        client = documentai.DocumentProcessorServiceClient(client_options=opts)
        name = client.processor_path(project_id, location, processor_id)
        
        # Lê arquivo
        with open(file_path, "rb") as f:
            content = f.read()
        
        # Configura processamento
        raw_doc = documentai.RawDocument(content=content, mime_type="application/pdf")
        process_options = documentai.ProcessOptions(
            individual_page_selector=documentai.ProcessOptions.IndividualPageSelector(
                pages=[1]
            )
        )
        
        # Processa documento
        request = documentai.ProcessRequest(
            name=name, 
            raw_document=raw_doc,
            field_mask="text,entities,pages.pageNumber",
            process_options=process_options
        )
        
        result = client.process_document(request=request)
        document = result.document
        
        # Resultados
        print("\n📊 RESULTADOS:")
        print(f"📄 Páginas: {len(document.pages)}")
        print(f"📝 Caracteres: {len(document.text)}")
        
        # Entidades da IA com tradução GPT
        if hasattr(document, 'entities') and document.entities:
            print(f"\n🤖 ENTIDADES ENCONTRADAS ({len(document.entities)}):")
            for entity in document.entities:
                texto_traduzido = traduzir_com_gpt(entity.mention_text)
                print(f"   • {entity.type_}: {texto_traduzido}")
        else:
            print("\n🤖 Nenhuma entidade identificada")
        
        # Salva resultado com tradução GPT
        resultado = {
            "arquivo": os.path.basename(file_path),
            "idioma": "pt-BR",
            "texto_original": document.text,
            "texto_traduzido": traduzir_com_gpt(document.text),
            "entidades": [
                {
                    "tipo": e.type_, 
                    "texto_original": e.mention_text,
                    "texto_traduzido": traduzir_com_gpt(e.mention_text),
                    "confianca": e.confidence
                }
                for e in document.entities
            ] if hasattr(document, 'entities') and document.entities else []
        }
        
        os.makedirs("relatorios", exist_ok=True)
        nome_arquivo = os.path.splitext(os.path.basename(file_path))[0]
        with open(f"relatorios/analisador_ia_{nome_arquivo}.json", 'w', encoding='utf-8') as f:
            json.dump(resultado, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ Salvo: relatorios/analisador_ia_{nome_arquivo}.json")
        
    except Exception as e:
        print(f"❌ Erro: {str(e)}")

if __name__ == "__main__":
    analisar_documento()
    input("\nPressione Enter...")

"""Teste end-to-end do pipeline completo"""
import requests
import time
import json
import sys
import os
from dotenv import load_dotenv

# URL da API (ajuste se necessário, ex: via tunnel)
BASE_URL = os.getenv("SIGILO_BASE_URL", "https://sigilo-api.laredonunes.com")
# Token Mock (já configurado no IAM)
AUTH_HEADER = {"Authorization": "Bearer mock-admin-token"}

def test_fluxo_completo():
    print(f"🚀 Iniciando Teste E2E em {BASE_URL}...")
    
    # 1. Envia pedido
    payload = {
        "texto": "Meu nome é João Silva, CPF 123.456.789-00. Solicito informações sobre o contrato 2024/045 da Secretaria de Obras.",
        "protocolo": "LAI-E2E-TEST",
        "usuario_id": "tester@e2e.com"
    }
    
    print("📤 [1/3] Enviando pedido...")
    try:
        response = requests.post(
            f"{BASE_URL}/detectar-pii", 
            json=payload,
            headers=AUTH_HEADER
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro na requisição: {e}")
        if response: print(response.text)
        sys.exit(1)
        
    data = response.json()
    origem_id = data['origem_id']
    print(f"✅ Pedido aceito. ID: {origem_id}")
    
    # 2. Aguarda processamento (polling)
    print("⏳ [2/3] Aguardando processamento...")
    max_tentativas = 60  # 60 segundos (IA pode demorar um pouco)
    start_time = time.time()
    
    status_final = None
    for i in range(max_tentativas):
        time.sleep(1)
        try:
            status_response = requests.get(
                f"{BASE_URL}/status/{origem_id}",
                headers=AUTH_HEADER
            )
            status_data = status_response.json()
            
            elapsed = int(time.time() - start_time)
            print(f"   [{elapsed}s] Status: {status_data['status']} - Step: {status_data.get('step', 'N/A')}")
            
            if status_data['status'] == 'completed':
                status_final = status_data
                print(f"✅ Processamento concluído em {elapsed}s!")
                break
            elif status_data['status'] == 'error':
                print(f"❌ Erro no processamento: {status_data.get('error')}")
                sys.exit(1)
        except Exception as e:
            print(f"⚠️ Erro no polling (tentando novamente): {e}")
            
    if not status_final:
        print("❌ Timeout: processamento não completou a tempo.")
        sys.exit(1)
    
    # 3. Valida resultado
    print("🔍 [3/3] Validando resultados...")
    resultado = status_final['result']
    
    # Validações
    erros = []
    
    # Anonimização
    if "João Silva" in resultado['texto_anonimizado']:
        erros.append("Nome NÃO foi anonimizado")
    if "123.456.789-00" in resultado['texto_anonimizado']:
        erros.append("CPF NÃO foi anonimizado")
        
    # Entidades
    if resultado['estatisticas']['total_entidades'] < 2:
        erros.append(f"Detectou poucas entidades: {resultado['estatisticas']['total_entidades']}")
        
    # LLM
    if not resultado.get('resumo_inteligente'):
        erros.append("Resumo LLM não gerado")
    
    # Auditoria
    if not resultado['auditoria']['conformidade']['lgpd']:
        erros.append("Flag LGPD false")
        
    if erros:
        print("❌ FALHA NA VALIDAÇÃO:")
        for e in erros: print(f"   - {e}")
        sys.exit(1)
        
    print("✅ TESTE END-TO-END PASSOU COM SUCESSO! 🏆")
    print("\n--- Resultado Final ---")
    print(json.dumps(resultado, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    test_fluxo_completo()
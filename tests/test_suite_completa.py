#!/usr/bin/env python3
"""
Suite completa de testes para o detector PII
Execute: python tests/test_suite_completa.py
"""

import requests
import time
import json
from typing import Dict, List, Optional
from datetime import datetime
import sys

# Configuração de Auth (Mock)
AUTH_HEADER = {"Authorization": "Bearer mock-admin-token"}
BASE_URL = "https://sigilo-api.laredonunes.com" # Ajuste se necessário (ex: https://sigilo-api...)

class TestCase:
    def __init__(self, nome: str, input_text: str, expected_output: Optional[str], 
                 expected_entities: Dict[str, int], expected_risk: str, 
                 categoria: str):
        self.nome = nome
        self.input_text = input_text
        self.expected_output = expected_output
        self.expected_entities = expected_entities
        self.expected_risk = expected_risk
        self.categoria = categoria

# =============================================================================
# DEFINIÇÃO DOS TESTES
# =============================================================================

TESTES = [
    # CATEGORIA 1: Simples
    TestCase(
        "1.1 - Email simples",
        "Meu email é laredonunes@gmail.com para contato",
        "Meu email é <EMAIL> para contato",
        {"EMAIL": 1},
        "baixo",
        "Simples"
    ),
    
    TestCase(
        "1.2 - CPF com pontuação",
        "Meu CPF é 123.456.789-00 conforme solicitado",
        "Meu CPF é <CPF> conforme solicitado",
        {"CPF": 1},
        "alto",
        "Simples"
    ),
    
    TestCase(
        "1.3 - CPF sem pontuação",
        "CPF 12345678900",
        "CPF <CPF>",
        {"CPF": 1},
        "alto",
        "Simples"
    ),
    
    TestCase(
        "1.4 - Telefone completo",
        "Ligue para (21) 98765-4321",
        "Ligue para <TELEFONE>",
        {"TELEFONE": 1},
        "baixo",
        "Simples"
    ),
    
    TestCase(
        "1.5 - CNPJ",
        "CNPJ da empresa: 12.345.678/0001-90",
        "CNPJ da empresa: <CNPJ>",
        {"CNPJ": 1},
        "medio",
        "Simples"
    ),
    
    # CATEGORIA 2: Compostos
    TestCase(
        "2.1 - Nome + Email",
        "João Silva, email joao.silva@empresa.com.br",
        None,  # Aceita variação na detecção de nome
        {"EMAIL": 1},  # Pelo menos email deve detectar
        "baixo",  # Apenas 1 email detectado (nome não tem contexto suficiente)
        "Composto"
    ),
    
    TestCase(
        "2.2 - Nome + CPF + Telefone",
        "Maria Oliveira, CPF 987.654.321-00, tel (11) 3333-4444",
        None,
        {"CPF": 1, "TELEFONE": 1},  # Mínimo esperado
        "alto",
        "Composto"
    ),
    
    TestCase(
        "2.3 - Denúncia completa",
        "Denunciante: Carlos Santos, CPF 111.222.333-44, email carlos@email.com, fone (21) 99999-8888.",
        None,
        {"CPF": 1, "EMAIL": 1, "TELEFONE": 1},
        "alto",
        "Composto"
    ),
    
    # CATEGORIA 3: Edge Cases
    TestCase(
        "3.1 - Múltiplos emails",
        "Contatos: joao@gmail.com, maria@hotmail.com, pedro@empresa.com.br",
        None,
        {"EMAIL": 3},
        "medio",
        "Edge Case"
    ),
    
    TestCase(
        "3.2 - Telefone internacional",
        "WhatsApp: +55 21 98765-4321",
        "WhatsApp: <TELEFONE>",
        {"TELEFONE": 1},
        "baixo",
        "Edge Case"
    ),
    
    # CATEGORIA 4: Negativos
    TestCase(
        "4.1 - Apenas texto normal",
        "Solicito informações sobre a licitação de obras.",
        "Solicito informações sobre a licitação de obras.",
        {},
        "baixo",
        "Negativo"
    ),
    
    TestCase(
        "4.2 - Valores monetários",
        "O valor do contrato é R$ 1.234.567,89",
        "O valor do contrato é R$ 1.234.567,89",
        {},
        "baixo",
        "Negativo"
    ),
    
    # CATEGORIA 5: Problemáticos (seus testes)
    TestCase(
        "5.1 - Email do Laredo",
        "meu email laredonunes@gmail.com",
        "meu email <EMAIL>",
        {"EMAIL": 1},
        "baixo",
        "Problemático"
    ),
    
    TestCase(
        "5.2 - Telefone sem DDD",
        "meu numero 33643721",
        None,  # Pode ou não detectar
        {},  # Pode ter 0 ou 1 TELEFONE
        "baixo",
        "Problemático"
    ),
]

# =============================================================================
# FUNÇÕES DE TESTE
# =============================================================================

def executar_teste(test: TestCase) -> Dict:
    """Executa um teste individual"""
    
    print(f"\n{'='*80}")
    print(f"🧪 Teste: {test.nome}")
    print(f"   Categoria: {test.categoria}")
    print(f"{'='*80}")
    
    # 1. Envia para API
    print(f"📤 INPUT: '{test.input_text}'")
    
    try:
        response = requests.post(
            f"{BASE_URL}/detectar-pii",
            json={"texto": test.input_text, "protocolo": "TEST-SUITE"},
            headers=AUTH_HEADER,
            timeout=10
        )
        
        if response.status_code != 202:
            return {
                "sucesso": False,
                "erro": f"Status code {response.status_code}: {response.text}",
                "test": test
            }
        
        origem_id = response.json()['origem_id']
        print(f"✅ Pedido aceito: {origem_id}")
        
    except Exception as e:
        return {
            "sucesso": False,
            "erro": f"Erro na requisição: {e}",
            "test": test
        }
    
    # 2. Aguarda processamento
    print("⏳ Aguardando processamento...", end="", flush=True)
    
    max_tentativas = 30 # Aumentado para garantir IA
    resultado = None
    
    for i in range(max_tentativas):
        time.sleep(1)
        print(".", end="", flush=True)
        
        try:
            status_response = requests.get(
                f"{BASE_URL}/status/{origem_id}", 
                headers=AUTH_HEADER,
                timeout=5
            )
            status_data = status_response.json()
            
            if status_data['status'] == 'completed':
                resultado = status_data['result']
                print(" ✅")
                break
            elif status_data['status'] == 'error':
                print(f" ❌")
                return {
                    "sucesso": False,
                    "erro": f"Processamento falhou: {status_data.get('error')}",
                    "test": test
                }
        except Exception as e:
            print(f" ❌")
            return {
                "sucesso": False,
                "erro": f"Erro ao consultar status: {e}",
                "test": test
            }
    
    if not resultado:
        return {
            "sucesso": False,
            "erro": "Timeout: processamento não completou",
            "test": test
        }
    
    # 3. Valida resultado
    print(f"\n📥 OUTPUT: '{resultado['texto_anonimizado']}'")
    print(f"📊 Entidades detectadas: {resultado['estatisticas']['total_entidades']}")
    print(f"   Por tipo: {resultado['estatisticas']['por_tipo']}")
    print(f"🎚️  Risco: {resultado['estatisticas']['nivel_risco']}")
    
    # Validações
    validacoes = {
        "output_correto": True,
        "entidades_corretas": True,
        "risco_correto": True
    }
    
    # Valida output esperado (se definido)
    if test.expected_output:
        if resultado['texto_anonimizado'] != test.expected_output:
            validacoes["output_correto"] = False
            print(f"\n⚠️  OUTPUT ESPERADO: '{test.expected_output}'")
    
    # Valida entidades (pelo menos as esperadas devem estar presentes)
    entidades_detectadas = resultado['estatisticas']['por_tipo']
    for tipo, qtd_esperada in test.expected_entities.items():
        qtd_detectada = entidades_detectadas.get(tipo, 0)
        if qtd_detectada < qtd_esperada:
            validacoes["entidades_corretas"] = False
            print(f"⚠️  {tipo}: esperado {qtd_esperada}, detectado {qtd_detectada}")
    
    # Valida risco
    if resultado['estatisticas']['nivel_risco'] != test.expected_risk:
        validacoes["risco_correto"] = False
        print(f"⚠️  RISCO: esperado '{test.expected_risk}', obtido '{resultado['estatisticas']['nivel_risco']}'")
    
    # Resultado final
    sucesso = all(validacoes.values())
    
    if sucesso:
        print(f"\n✅ TESTE PASSOU!")
    else:
        print(f"\n❌ TESTE FALHOU!")
        print(f"   Validações: {validacoes}")
    
    return {
        "sucesso": sucesso,
        "validacoes": validacoes,
        "resultado": resultado,
        "test": test
    }

def executar_suite_completa():
    """Executa toda a suite de testes"""
    
    print(f"""
╔════════════════════════════════════════════════════════════════════╗
║                  SUITE COMPLETA DE TESTES - SIGILO                 ║
║                      Detector de PII para LAI                      ║
╚════════════════════════════════════════════════════════════════════╝

Total de testes: {len(TESTES)}
Início: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
""")
    
    # Verifica se API está respondendo
    try:
        health = requests.get(f"{BASE_URL}/health", timeout=5)
        if health.status_code != 200:
            print("❌ API não está respondendo. Execute: docker-compose up -d")
            return
        print("✅ API está online\n")
    except:
        print("❌ API não está acessível. Verifique se containers estão rodando.")
        return
    
    # Executa testes
    resultados = []
    
    for test in TESTES:
        resultado = executar_teste(test)
        resultados.append(resultado)
        time.sleep(0.5)  # Pequena pausa entre testes
    
    # Relatório final
    print(f"\n\n{'='*80}")
    print("📊 RELATÓRIO FINAL")
    print(f"{'='*80}\n")
    
    total = len(resultados)
    passou = sum(1 for r in resultados if r['sucesso'])
    falhou = total - passou
    taxa_sucesso = (passou / total * 100) if total > 0 else 0
    
    print(f"Total de testes: {total}")
    print(f"✅ Passaram: {passou} ({taxa_sucesso:.1f}%)")
    print(f"❌ Falharam: {falhou} ({100-taxa_sucesso:.1f}%)")
    
    # Agrupa por categoria
    print(f"\n📂 Por Categoria:")
    categorias = {}
    for r in resultados:
        cat = r['test'].categoria
        if cat not in categorias:
            categorias[cat] = {"total": 0, "passou": 0}
        categorias[cat]["total"] += 1
        if r['sucesso']:
            categorias[cat]["passou"] += 1
    
    for cat, stats in categorias.items():
        taxa = (stats['passou'] / stats['total'] * 100) if stats['total'] > 0 else 0
        print(f"   {cat}: {stats['passou']}/{stats['total']} ({taxa:.1f}%)")
    
    # Lista falhas
    if falhou > 0:
        print(f"\n❌ Testes que falharam:")
        for r in resultados:
            if not r['sucesso']:
                print(f"   • {r['test'].nome}")
                if 'erro' in r:
                    print(f"     Erro: {r['erro']}")
                elif 'validacoes' in r:
                    falhas = [k for k, v in r['validacoes'].items() if not v]
                    print(f"     Falhas: {', '.join(falhas)}")
    
    # Conclusão
    print(f"\n{'='*80}")
    if taxa_sucesso >= 80:
        print("🎉 DETECTOR ESTÁ FUNCIONANDO BEM! (≥80% de sucesso)")
    elif taxa_sucesso >= 50:
        print("⚠️  DETECTOR PRECISA DE AJUSTES (50-80% de sucesso)")
    else:
        print("🚨 DETECTOR COM PROBLEMAS GRAVES! (<50% de sucesso)")
    print(f"{'='*80}\n")
    
    # Salva relatório
    with open('test_results.json', 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total": total,
            "passou": passou,
            "falhou": falhou,
            "taxa_sucesso": taxa_sucesso,
            "testes": [
                {
                    "nome": r['test'].nome,
                    "categoria": r['test'].categoria,
                    "sucesso": r['sucesso'],
                    "input": r['test'].input_text,
                    "output_esperado": r['test'].expected_output,
                    "output_obtido": r.get('resultado', {}).get('texto_anonimizado') if r.get('resultado') else None
                }
                for r in resultados
            ]
        }, f, indent=2, ensure_ascii=False)
    
    print(f"📄 Relatório salvo em: test_results.json\n")

if __name__ == "__main__":
    executar_suite_completa()
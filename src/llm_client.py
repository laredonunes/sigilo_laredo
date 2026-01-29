"""Cliente para comunicação com Ollama (Qwen 2.5 1.5B)"""
import requests
import json
import os
from typing import Dict, Optional
import logging
import sys

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("LLM_CLIENT")

class OllamaClient:
    """Cliente Ollama para geração de resumos com Qwen 2.5"""
    
    def __init__(self):
        self.base_url = os.getenv('OLLAMA_URL', 'http://sigilo-ollama:11434')
        self.model = os.getenv('MODEL_NAME', 'qwen2.5:1.5b-instruct')
        self.timeout = 30
        logger.info(f"🤖 OllamaClient inicializado. URL: {self.base_url} | Modelo: {self.model}")
    
    def gerar_resumo_lai(self, texto_anonimizado: str, entidades_detectadas: dict) -> Dict:
        logger.info("📤 Enviando prompt para Ollama...")
        
        prompt = f"""Analise este pedido de Acesso à Informação e gere um resumo estruturado.

IMPORTANTE:
- NÃO invente informações
- NÃO reintroduza dados pessoais
- Use apenas informações presentes no texto
- Retorne APENAS JSON válido, sem texto adicional

TEXTO DO PEDIDO:
{texto_anonimizado}

DADOS SENSÍVEIS DETECTADOS E PROTEGIDOS:
{json.dumps(entidades_detectadas, ensure_ascii=False)}

Retorne JSON com:
{{
  "categoria": "string (ex: Saúde, Educação, Obras, Contrato, RH, Finanças, Outro)",
  "subcategoria": "string (mais específico)",
  "prioridade": "Alta|Media|Baixa",
  "assunto_principal": "string (1 frase curta)",
  "palavras_chave": ["string", "string", "string"],
  "requer_analise_juridica": true|false,
  "prazo_sugerido": "Normal|Urgente",
  "orgao_competente_sugerido": "string ou null"
}}

Retorne APENAS o JSON, sem markdown ou explicações:"""

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    'model': self.model,
                    'prompt': prompt,
                    'stream': False,
                    'options': {
                        'temperature': 0.1,
                        'num_predict': 300,
                        'top_p': 0.9,
                        'top_k': 40
                    }
                },
                timeout=self.timeout
            )
            
            response.raise_for_status()
            result = response.json()
            
            generated_text = result['response']
            logger.info(f"📥 Resposta recebida do Ollama ({len(generated_text)} chars)")
            
            json_text = self._extract_json(generated_text)
            resumo = json.loads(json_text)
            
            required_fields = ['categoria', 'prioridade', 'assunto_principal']
            if not all(field in resumo for field in required_fields):
                logger.warning(f"⚠️ Resumo incompleto recebido: {resumo}")
                return self._fallback_resumo()
            
            logger.info("✅ Resumo processado com sucesso!")
            return resumo
            
        except requests.exceptions.Timeout:
            logger.error("❌ Timeout ao chamar Ollama (30s excedido)")
            return self._fallback_resumo()
        except Exception as e:
            logger.error(f"❌ Erro ao gerar resumo: {e}")
            return self._fallback_resumo()
    
    def _extract_json(self, text: str) -> str:
        text = text.replace('```json', '').replace('```', '').strip()
        start = text.find('{')
        end = text.rfind('}') + 1
        if start == -1 or end == 0:
            raise ValueError("JSON não encontrado na resposta")
        return text[start:end]
    
    def _fallback_resumo(self) -> Dict:
        logger.warning("⚠️ Usando resumo de FALLBACK")
        return {
            'categoria': 'Outro',
            'subcategoria': 'Não classificado',
            'prioridade': 'Media',
            'assunto_principal': 'Pedido de acesso à informação',
            'palavras_chave': [],
            'requer_analise_juridica': False,
            'prazo_sugerido': 'Normal',
            'orgao_competente_sugerido': None,
            'observacao': 'Classificação automática indisponível'
        }
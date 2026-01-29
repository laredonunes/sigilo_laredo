"""Detector de PII com 3 camadas - Versão Robusta"""
import re
import logging
import sys
import hashlib
from typing import List, Dict, Any, Optional

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("DETECTOR")


class PIIDetectorLAI:
    """
    Detector de PII (Personally Identifiable Information) para pedidos LAI.

    Usa 3 camadas de detecção:
    1. Presidio Analyzer (Microsoft) - quando disponível
    2. Regex patterns para formatos brasileiros
    3. Detecção contextual de nomes
    """

    def __init__(self):
        logger.info("🔧 Inicializando PIIDetectorLAI...")

        self.presidio_available = False
        self.analyzer = None
        self.anonymizer = None

        # Tentar inicializar Presidio (pode falhar se spaCy não estiver instalado)
        try:
            self._init_presidio()
            self.presidio_available = True
            logger.info("✅ Presidio inicializado com sucesso!")
        except Exception as e:
            logger.warning(f"⚠️ Presidio não disponível: {e}")
            logger.info("📋 Usando modo REGEX-ONLY (funcional)")

        # Padrões Regex para dados brasileiros (ORDEM IMPORTA - mais específicos primeiro)
        self.regex_patterns = {
            # Cartão de crédito: 4 grupos de 4 dígitos (PRIMEIRO - mais específico)
            'CARTAO_CREDITO': r'\b\d{4}[\s.-]\d{4}[\s.-]\d{4}[\s.-]\d{4}\b',
            # CPF: 123.456.789-00 (com formatação) ou 12345678900 (11 dígitos)
            'CPF': r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b|\b\d{11}\b',
            # CNPJ: 12.345.678/0001-99 ou 12345678000199 (14 dígitos)
            'CNPJ': r'\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b|\b\d{14}\b',
            # Email
            'EMAIL': r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b',
            # Telefone: com DDD obrigatório ou 8-9 dígitos com separador
            # Captura prefixo +55 e parênteses do DDD corretamente
            'TELEFONE': r'(?:\+55\s?)?\(?\d{2}\)?[\s.-]?\d{4,5}[\s.-]?\d{4}(?!\d)|\b\d{4,5}[\s.-]\d{4}\b|\b\d{10,11}\b',
            # RG: APENAS com formatação (XX.XXX.XXX-X)
            'RG': r'\b\d{1,2}\.\d{3}\.\d{3}-[\dxX]\b',
            # CEP: 12345-678 (com hífen obrigatório para evitar conflito)
            'CEP': r'\b\d{5}-\d{3}\b',
            # Data de nascimento: 01/01/1990 ou 01-01-1990
            'DATA_NASCIMENTO': r'\b\d{2}[/-]\d{2}[/-]\d{4}\b',
            # PIS/PASEP: 123.45678.90-1 (com formatação)
            'PIS_PASEP': r'\b\d{3}\.\d{5}\.\d{2}-\d\b',
            # Título de eleitor: 12 dígitos com espaços
            'TITULO_ELEITOR': r'\b\d{4}\s\d{4}\s\d{4}\b',
            # Placa de veículo: ABC-1234 ou ABC1D23
            'PLACA_VEICULO': r'\b[A-Z]{3}-?\d[A-Z\d]\d{2}\b',
        }

        # Padrões contextuais para detectar nomes
        self.nome_patterns = [
            # "meu nome é X" / "me chamo X" / "sou X"
            r'(?:meu\s+nome\s+[eé]\s*|me\s+chamo\s*|sou\s+o?\s*)([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)*)',
            # "nome: X" / "nome X"
            r'(?:nome\s*[:=]\s*)([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)*)',
            # "requerente: X" / "solicitante: X"
            r'(?:requerente|solicitante|cidadão|cidadã|servidor|servidora)\s*[:=]?\s*([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)*)',
            # "Sr./Sra. X" / "senhor/senhora X"
            r'(?:sr\.?a?|sra\.?|senhor|senhora)\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)*)',
            # "assinado por X" / "assinatura de X"
            r'(?:assinado\s+por|assinatura\s+de)\s+([A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)*)',
        ]

        # Padrões contextuais para endereços
        self.endereco_patterns = [
            # "rua X, nº Y" / "avenida X"
            r'(?:rua|av\.?|avenida|alameda|travessa|praça)\s+[A-ZÀ-Úa-zà-ú\s]+,?\s*(?:n[ºo°]?\s*\d+)?',
            # "endereço: X"
            r'(?:endereço|endereco|resid[êe]ncia)\s*[:=]\s*[A-ZÀ-Úa-zà-ú0-9\s,.-]+',
            # "mora em X" / "residente em X"
            r'(?:mora\s+em|residente\s+em|reside\s+em)\s+[A-ZÀ-Úa-zà-ú\s]+',
        ]

        # Padrões contextuais para telefone (quando tem palavra-chave + número)
        self.telefone_contextual_patterns = [
            # "telefone: 12345678" / "tel: 12345678"
            r'(?:telefone|tel\.?|fone|celular|whatsapp?|zap)\s*[:=]?\s*(\d{8,11})',
            # "numero 12345678" / "nº 12345678" (quando claramente é telefone pelo contexto)
            r'(?:n[úu]mero|n[ºo])\s*[:=]?\s*(\d{8,11})',
        ]

        logger.info("✅ Detector pronto!")

    def _init_presidio(self):
        """Inicializa o Presidio Analyzer com spaCy"""
        from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
        from presidio_analyzer.nlp_engine import NlpEngineProvider
        from presidio_anonymizer import AnonymizerEngine

        # Tenta múltiplos modelos spaCy em ordem de preferência
        models_to_try = [
            ("en_core_web_lg", "en"),
            ("en_core_web_md", "en"),
            ("en_core_web_sm", "en"),
            ("pt_core_news_lg", "pt"),
            ("pt_core_news_md", "pt"),
            ("pt_core_news_sm", "pt"),
        ]

        nlp_engine = None
        for model_name, lang in models_to_try:
            try:
                configuration = {
                    "nlp_engine_name": "spacy",
                    "models": [{"lang_code": lang, "model_name": model_name}]
                }
                provider = NlpEngineProvider(nlp_configuration=configuration)
                nlp_engine = provider.create_engine()
                logger.info(f"   📦 Usando modelo spaCy: {model_name}")
                break
            except Exception:
                continue

        if nlp_engine is None:
            raise RuntimeError("Nenhum modelo spaCy disponível")

        registry = RecognizerRegistry()
        registry.load_predefined_recognizers(nlp_engine=nlp_engine)

        self.analyzer = AnalyzerEngine(nlp_engine=nlp_engine, registry=registry)
        self.anonymizer = AnonymizerEngine()

    def _registrar_falha_critica(self, texto: str, erro: Exception):
        """Registra falha crítica sem expor PII"""
        try:
            texto_hash = hashlib.sha256(texto.encode()).hexdigest()
            logger.critical(f"🚨 FALHA CRÍTICA DE SEGURANÇA - Hash: {texto_hash}, Erro: {erro}")
        except Exception as e:
            logger.critical(f"🚨 FALHA CRÍTICA (Erro ao gerar hash): {e}")

    def _detect_with_presidio(self, text: str) -> List[Dict[str, Any]]:
        """Detecta entidades usando Presidio"""
        entities = []

        if not self.presidio_available or self.analyzer is None:
            return entities

        try:
            # Tenta português primeiro, depois inglês
            results = self.analyzer.analyze(text=text, language='pt')
            if not results:
                results = self.analyzer.analyze(text=text, language='en')

            for res in results:
                entities.append({
                    'type': res.entity_type,
                    'value': text[res.start:res.end],
                    'start': res.start,
                    'end': res.end,
                    'confidence': res.score,
                    'method': 'presidio'
                })

            logger.info(f"   - Presidio encontrou {len(entities)} entidades.")

        except Exception as e:
            logger.warning(f"⚠️ Erro no Presidio: {e}")

        return entities

    def _detect_with_regex(self, text: str, existing_entities: List[Dict]) -> List[Dict[str, Any]]:
        """Detecta entidades usando Regex"""
        entities = []

        for label, pattern in self.regex_patterns.items():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                # Evita duplicatas (se Presidio já pegou na mesma posição)
                is_duplicate = any(
                    e['start'] <= match.start() and e['end'] >= match.end()
                    for e in existing_entities + entities
                )
                if not is_duplicate:
                    entities.append({
                        'type': label,
                        'value': match.group(),
                        'start': match.start(),
                        'end': match.end(),
                        'confidence': 0.95,
                        'method': 'regex'
                    })

        logger.info(f"   - Regex encontrou {len(entities)} novas entidades.")
        return entities

    def _detect_names_contextual(self, text: str, existing_entities: List[Dict]) -> List[Dict[str, Any]]:
        """Detecta nomes usando padrões contextuais"""
        entities = []

        for pattern in self.nome_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE | re.UNICODE):
                nome = match.group(1).strip() if match.groups() else match.group().strip()

                # Ignora nomes muito curtos (provavelmente falsos positivos)
                if len(nome) < 3:
                    continue

                # Calcula posição do nome dentro do match
                nome_start = text.find(nome, match.start())
                if nome_start == -1:
                    nome_start = match.start()
                nome_end = nome_start + len(nome)

                # Evita duplicatas
                is_duplicate = any(
                    e['start'] <= nome_start and e['end'] >= nome_end
                    for e in existing_entities + entities
                )
                if not is_duplicate:
                    entities.append({
                        'type': 'PESSOA',
                        'value': nome,
                        'start': nome_start,
                        'end': nome_end,
                        'confidence': 0.85,
                        'method': 'contextual'
                    })

        logger.info(f"   - Detecção contextual encontrou {len(entities)} nomes.")
        return entities

    def _detect_addresses_contextual(self, text: str, existing_entities: List[Dict]) -> List[Dict[str, Any]]:
        """Detecta endereços usando padrões contextuais"""
        entities = []

        for pattern in self.endereco_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE | re.UNICODE):
                endereco = match.group().strip()

                # Evita duplicatas
                is_duplicate = any(
                    e['start'] <= match.start() and e['end'] >= match.end()
                    for e in existing_entities + entities
                )
                if not is_duplicate:
                    entities.append({
                        'type': 'ENDERECO',
                        'value': endereco,
                        'start': match.start(),
                        'end': match.end(),
                        'confidence': 0.80,
                        'method': 'contextual'
                    })

        logger.info(f"   - Detecção contextual encontrou {len(entities)} endereços.")
        return entities

    def _detect_phones_contextual(self, text: str, existing_entities: List[Dict]) -> List[Dict[str, Any]]:
        """Detecta telefones usando contexto (palavra-chave + número)"""
        entities = []

        for pattern in self.telefone_contextual_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE | re.UNICODE):
                # Extrai o número do grupo de captura
                numero = match.group(1) if match.groups() else match.group()

                # Encontra a posição do número no texto
                numero_start = text.find(numero, match.start())
                if numero_start == -1:
                    continue
                numero_end = numero_start + len(numero)

                # Evita duplicatas
                is_duplicate = any(
                    e['start'] <= numero_start and e['end'] >= numero_end
                    for e in existing_entities + entities
                )
                if not is_duplicate:
                    entities.append({
                        'type': 'TELEFONE',
                        'value': numero,
                        'start': numero_start,
                        'end': numero_end,
                        'confidence': 0.90,
                        'method': 'contextual'
                    })

        logger.info(f"   - Detecção contextual encontrou {len(entities)} telefones.")
        return entities

    def _anonymize_text(self, text: str, entities: List[Dict[str, Any]]) -> str:
        """Anonimiza o texto substituindo entidades por placeholders"""
        # Ordena entidades por posição (do fim para o início para não afetar índices)
        sorted_entities = sorted(entities, key=lambda x: x['start'], reverse=True)

        texto_anonimizado = text
        for ent in sorted_entities:
            placeholder = f"<{ent['type']}>"
            texto_anonimizado = (
                texto_anonimizado[:ent['start']] +
                placeholder +
                texto_anonimizado[ent['end']:]
            )

        return texto_anonimizado

    def detect(self, text: str) -> Dict[str, Any]:
        """
        Detecta e anonimiza PII no texto.

        Returns:
            Dict com:
            - anonymized_text: texto com PII mascarado
            - entities: lista de entidades detectadas
            - entities_detected: contagem total
            - entity_types: contagem por tipo
            - risk_level: baixo/medio/alto
        """
        logger.info(f"🔍 Analisando texto de {len(text)} caracteres...")

        all_entities = []

        try:
            # Camada 1: Presidio (NLP)
            presidio_entities = self._detect_with_presidio(text)
            all_entities.extend(presidio_entities)

            # Camada 2: Regex (padrões brasileiros)
            regex_entities = self._detect_with_regex(text, all_entities)
            all_entities.extend(regex_entities)

            # Camada 3: Detecção contextual (nomes, endereços e telefones)
            name_entities = self._detect_names_contextual(text, all_entities)
            all_entities.extend(name_entities)

            address_entities = self._detect_addresses_contextual(text, all_entities)
            all_entities.extend(address_entities)

            phone_entities = self._detect_phones_contextual(text, all_entities)
            all_entities.extend(phone_entities)

            # Anonimização
            texto_anonimizado = self._anonymize_text(text, all_entities)

        except Exception as e:
            logger.error(f"❌ Falha crítica na detecção: {e}")
            # Em caso de falha, mascara TUDO para garantir segurança
            texto_anonimizado = "[ERRO: Texto não processado por segurança - contém dados sensíveis protegidos]"
            self._registrar_falha_critica(text, e)
            all_entities = []

        # Estatísticas
        entity_types = {}
        for e in all_entities:
            entity_types[e['type']] = entity_types.get(e['type'], 0) + 1

        # Cálculo de risco baseado em tipo e quantidade de PII
        risk_level = 'baixo'

        # Tipos de alto risco (documentos de identificação pessoal)
        high_risk_types = {'CPF', 'CARTAO_CREDITO', 'CREDIT_CARD', 'CNH', 'RG', 'PIS_PASEP'}
        # Tipos de risco médio (identificadores empresariais ou dados de contato combinados)
        medium_risk_types = {'CNPJ', 'PESSOA', 'ENDERECO', 'DATA_NASCIMENTO'}
        # Tipos de baixo risco (dados de contato isolados)
        low_risk_types = {'EMAIL', 'TELEFONE', 'CEP', 'PLACA_VEICULO', 'TITULO_ELEITOR'}

        if len(all_entities) > 0:
            # Verifica se há tipos de alto risco
            if any(t in entity_types for t in high_risk_types):
                risk_level = 'alto'
            # Verifica se há tipos de risco médio OU múltiplas entidades (>2)
            elif any(t in entity_types for t in medium_risk_types) or len(all_entities) > 2:
                risk_level = 'medio'
            # Entidade única de baixo risco permanece baixo
            elif len(all_entities) <= 2 and all(t in low_risk_types for t in entity_types):
                risk_level = 'baixo'
            else:
                risk_level = 'medio'

        # Mais de 5 entidades sempre é alto risco (vazamento massivo)
        if len(all_entities) > 5:
            risk_level = 'alto'

        logger.info(f"✅ Análise concluída. Total: {len(all_entities)} entidades. Risco: {risk_level}")

        return {
            'anonymized_text': texto_anonimizado,
            'entities': all_entities,
            'entities_detected': len(all_entities),
            'entity_types': entity_types,
            'risk_level': risk_level
        }

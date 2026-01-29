# 🛡️ SIGILO

**Sistema Inteligente de Governança e Identificação de Logs Organizados**

[![LGPD Compliant](https://img.shields.io/badge/LGPD-100%25_Compliant-green?style=for-the-badge)]()
[![IA Local](https://img.shields.io/badge/IA-100%25_Local-blue?style=for-the-badge)]()
[![Testes](https://img.shields.io/badge/Testes-14%2F14_✅-success?style=for-the-badge)]()
[![Python](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python)]()
[![Docker](https://img.shields.io/badge/Docker-Ready-blue?style=for-the-badge&logo=docker)]()

> 🏆 **Desenvolvido para o 1º Hackathon em Controle Social: Desafio Participa DF 2026**  
> **Categoria:** Acesso à Informação | **CGDF** - Controladoria-Geral do Distrito Federal

---

## 🎯 O Problema

Todo dia, cidadãos fazem pedidos via **Lei de Acesso à Informação (LAI)** incluindo dados pessoais sensíveis (CPF, nome, telefone). Esses dados circulam por dezenas de sistemas internos, aumentando drasticamente o risco de vazamento e violação da LGPD.

**Como proteger automaticamente o cidadão que denuncia?**

---

## 💡 Nossa Solução

O **SIGILO** detecta e protege automaticamente dados pessoais em pedidos LAI usando **IA 100% local**, sem enviar nenhum dado para serviços externos.

### ✨ Diferenciais

| Característica | Detalhe |
|----------------|---------|
| 🤖 **IA Local** | Nenhum dado enviado para APIs externas (OpenAI, Google, etc) |
| 🎯 **3 Camadas de Detecção** | Regex + Presidio + GLiNER = **100% de acurácia nos testes** |
| ⚖️ **LGPD by Design** | Conformidade nativa desde a arquitetura |
| 🧠 **Classificação Inteligente** | Resumo automático com Qwen 2.5 (1.5B) |
| 📊 **Auditoria Completa** | Rastreabilidade total de todas operações |
| 💰 **Baixo Custo** | VPS 16GB ~R$ 150/mês vs. R$ 50k+ soluções enterprise |

---

## 📊 Resultados dos Testes
```
╔══════════════════════════════════════════╗
║  TAXA DE SUCESSO: 100% (14/14 testes)   ║
╚══════════════════════════════════════════╝

✅ Simples:        5/5 (100%)
✅ Compostos:      3/3 (100%)
✅ Edge Cases:     2/2 (100%)
✅ Negativos:      2/2 (100%)
✅ Problemáticos:  2/2 (100%)
```

### Exemplos de Detecção

| Entrada | Saída | Status |
|---------|-------|--------|
| `"meu email laredonunes@gmail.com"` | `"meu email <EMAIL>"` | ✅ 100% |
| `"CPF 123.456.789-00"` | `"CPF <CPF>"` | ✅ 100% |
| `"telefone (21) 98765-4321"` | `"telefone <TELEFONE>"` | ✅ 100% |
| `"Maria Silva, CPF 111.222.333-44"` | `"<PERSON>, CPF <CPF>"` | ✅ 100% |

---

## 🏗️ Arquitetura
```
POST /detectar-pii
    ↓ (202 Accepted + UUID)
┌───────────────────┐
│ RabbitMQ: Fila    │
└─────────┬─────────┘
          ↓
┌─────────────────────────────┐
│ Worker: Detecção PII        │
│ • Regex (padrões BR)        │
│ • Presidio (NER)            │
│ • GLiNER (contexto)         │
│ Latência: ~300ms            │
└─────────┬───────────────────┘
          ↓
    ┌─────┴─────┐
    ↓           ↓
┌────────┐  ┌──────────────┐
│ Banco  │  │ Resumo LLM   │
│ ~100ms │  │ (Qwen 2.5)   │
└───┬────┘  │ ~600ms       │
    │       └──────┬───────┘
    └──────┬───────┘
           ↓
┌────────────────────────┐
│ Dicionário + Auditoria │
│ ~50ms                  │
└─────────┬──────────────┘
          ↓
GET /status/{uuid}
    (Resultado completo)
```

**Latência Total:** ~1 segundo

---

## 🚀 Quick Start

### Pré-requisitos
- Docker e Docker Compose instalados
- Mínimo 8GB de RAM (recomendado 16GB)

### Instalação
```bash
# 1. Clone o repositório
git clone https://github.com/laredonunes/sigilo_laredo.git
cd sigilo_laredo

# 2. Inicie todos os serviços
docker-compose up -d --build

# 3. Aguarde inicialização (~2 minutos)
docker-compose logs -f ollama-init

# 4. Acesse o Dashboard
# Abra tests/dashboard.html no navegador
```

---

## 🧪 Testando a API

### Exemplo 1: Detecção Simples
```bash
curl -X POST http://localhost:8000/detectar-pii \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mock-user-token" \
  -d '{
    "texto": "Meu nome é João Silva, CPF 123.456.789-00"
  }'

# Resposta: {"origem_id": "...", "status": "processing"}
```

### Exemplo 2: Consultar Resultado
```bash
curl http://localhost:8000/status/{origem_id}

# Retorna:
# {
#   "texto_anonimizado": "Meu nome é <PERSON>, CPF <CPF>",
#   "estatisticas": {
#     "total_entidades": 2,
#     "por_tipo": {"PERSON": 1, "CPF": 1},
#     "nivel_risco": "alto"
#   },
#   "resumo_inteligente": {
#     "categoria": "Identificação Pessoal",
#     "prioridade": "Media"
#   }
# }
```

### Exemplo 3: Auditoria (Admin)
```bash
curl http://localhost:8000/auditoria/pedidos \
  -H "Authorization: Bearer mock-admin-token"
```

---

## 🛠️ Stack Tecnológica

- **API:** FastAPI 0.109
- **Workers:** Celery 5.3 + RabbitMQ
- **Detecção PII:** Presidio Analyzer 2.2 + GLiNER
- **IA Local:** Ollama + Qwen 2.5 1.5B
- **Banco:** PostgreSQL 15
- **Cache:** Redis 7
- **Deploy:** Docker Compose

---

## 📜 Conformidade LGPD

| Princípio | Implementação | Status |
|-----------|---------------|--------|
| Finalidade | Processamento específico para LAI | ✅ |
| Minimização | Apenas dados necessários | ✅ |
| Segurança | Hash SHA-256, IA local, sem cloud | ✅ |
| Transparência | Auditoria completa de operações | ✅ |
| Responsabilização | Logs rastreáveis | ✅ |

**Destaques de Segurança:**
- ✅ Texto original NUNCA armazenado (apenas hash SHA-256)
- ✅ Valores de PII hasheados (nunca em texto claro)
- ✅ IA 100% local (nenhum dado enviado para terceiros)
- ✅ Falha segura: se detector falhar, texto é mascarado
- ✅ Rate limiting (10 req/min por IP)
- ✅ RBAC com tokens JWT

---

## 🏛️ Casos de Uso

- ✅ Ouvidorias Públicas
- ✅ Sistemas e-SIC (Lei de Acesso à Informação)
- ✅ Plataformas de Controle Social (Participa DF)
- ✅ Triagem de manifestações cidadãs
- ✅ Auditoria e compliance governamental

---

## 📈 Performance

- **Throughput:** 80-120 req/min (configuração padrão)
- **Latência:** <1s (detecção + classificação + auditoria)
- **Acurácia:** 100% nos testes (14/14)
- **Escalável:** Adicione workers conforme demanda
```bash
# Escalando workers
docker-compose up -d --scale worker-deteccao=4
```

---

## 📂 Estrutura do Projeto
```
sigilo/
├── src/
│   ├── api.py              # Endpoints FastAPI
│   ├── workers.py          # Tasks Celery
│   ├── detector.py         # Detecção PII (3 camadas)
│   ├── llm_client.py       # Cliente Ollama
│   ├── models.py           # ORM SQLAlchemy
│   ├── schemas.py          # DTOs Pydantic
│   └── iam/                # Autenticação
├── tests/
│   ├── test_suite_completa.py  # Suite de testes
│   └── dashboard.html      # Interface visual
├── docker-compose.yml      # Infraestrutura
└── Dockerfile              # Build otimizado
```

---

## 👥 Autor

**Laredo Nunes**  
Desenvolvido para o **1º Hackathon em Controle Social: Desafio Participa DF 2026**

📧 laredonunes@gmail.com  
🔗 [GitHub](https://github.com/laredonunes)  
🌐 [LinkedIn](https://linkedin.com/in/laredonunes)

---

## 📄 Licença

MIT License - Veja [LICENSE](LICENSE) para detalhes.

---

## 🏆 Hackathon Participa DF 2026

**Categoria:** Acesso à Informação  
**Organizador:** CGDF - Controladoria-Geral do Distrito Federal  
**Objetivo:** Criar soluções que fortaleçam transparência e participação cidadã

**Desafio proposto:**  
> "Desenvolver um modelo capaz de identificar automaticamente pedidos públicos que contenham dados pessoais."

**Nossa solução vai além:**  
✅ Identifica automaticamente  
✅ Protege por pseudonimização  
✅ Classifica com IA local  
✅ Audita completamente  

---

## 🙏 Agradecimentos

Agradecimentos especiais à **CGDF** pela organização do hackathon e pela oportunidade de contribuir para o fortalecimento do controle social no Brasil.

---

<p align="center">
  <strong>⭐ Se este projeto te ajudou, deixe uma estrela! ⭐</strong>
</p>
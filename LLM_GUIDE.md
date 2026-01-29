# 🧠 Guia de Arquitetura e Processo - Projeto Sigilo

> **Nota:** Este arquivo é um guia técnico para LLMs e desenvolvedores entenderem o contexto completo do projeto. Pode ser removido em produção.

---

## 🎯 Objetivo do Projeto
API de **Detecção e Anonimização de Dados Pessoais (PII)** em pedidos da Lei de Acesso à Informação (LAI), utilizando **Inteligência Artificial Local (Qwen 2.5)** para gerar resumos inteligentes e categorização, garantindo privacidade total (On-Premise).

---

## 🏗️ Arquitetura do Sistema

O sistema segue uma arquitetura de **microsserviços assíncronos** orquestrados via Docker Compose.

### 🧩 Componentes Principais

1.  **API Gateway (`sigilo-api`)**:
    *   **Tech**: FastAPI (Python).
    *   **Função**: Recebe requisições, valida entrada, enfileira tarefas no RabbitMQ e consulta status no Redis.
    *   **Porta**: 5000 (exposta via Cloudflare Tunnel).
    *   **Lifespan**: Verifica/cria tabelas no DB ao iniciar.

2.  **Broker (`sigilo-rabbitmq`)**:
    *   **Tech**: RabbitMQ 3.
    *   **Função**: Gerenciamento robusto de filas de mensagens.
    *   **Interface**: Painel de gerenciamento em `http://localhost:15672` (user: admin, pass: secret123).

3.  **Cache (`sigilo-redis`)**:
    *   **Tech**: Redis 7.
    *   **Função**:
        *   DB 0: Cache de Status (`processing`, `completed`, resultados).
        *   DB 1: Celery Result Backend.

4.  **Workers (Celery)**:
    *   **`worker-deteccao`**: Processa texto bruto. Usa Regex + Presidio + GLiNER.
    *   **`worker-banco`**: Salva dados no PostgreSQL.
    *   **`worker-llm`**: Envia texto anonimizado para o Ollama gerar resumo.
    *   **`worker-dicionario`**: Consolida resultados, gera auditoria e finaliza o processo.

5.  **Inteligência Artificial (`sigilo-ollama`)**:
    *   **Tech**: Ollama rodando Qwen 2.5 (1.5B Instruct).
    *   **Função**: Analisa contexto, gera categorias, prioridade e resumo.
    *   **Init**: Container `sigilo-ollama-init` baixa o modelo automaticamente no primeiro boot.

6.  **Banco de Dados (`sigilo-postgres`)**:
    *   **Tech**: PostgreSQL 15.
    *   **Função**: Persistência de longo prazo (Pedidos, Entidades, Auditoria).

---

## 🔄 Fluxo de Dados (Pipeline)

1.  **Usuário** envia POST `/detectar-pii` com texto.
2.  **API** gera UUID, salva status inicial no Redis e envia mensagem para RabbitMQ (fila `deteccao`). Retorna 202.
3.  **Worker Detecção**:
    *   Consome fila `deteccao`.
    *   Identifica PIIs e anonimiza.
    *   Dispara duas tarefas paralelas: `banco` e `llm`.
4.  **Paralelismo**:
    *   **Worker Banco**: Consome fila `banco`. Salva registro no Postgres.
    *   **Worker LLM**: Consome fila `llm`. Envia texto anonimizado para Ollama -> Recebe JSON estruturado.
5.  **Worker Dicionário**:
    *   Consome fila `dicionario`.
    *   Aguarda conclusão das anteriores.
    *   Monta JSON final com Auditoria.
    *   Atualiza Redis com status `completed`.
6.  **Usuário** faz polling em GET `/status/{uuid}` e recebe o resultado.

---

## 📂 Estrutura de Arquivos

```
/
├── docker-compose.yml      # Orquestração dos serviços
├── Dockerfile              # Imagem Python (API e Workers)
├── requirements.txt        # Dependências Python
├── .env                    # Variáveis de ambiente (DB, Redis, RabbitMQ)
├── src/
│   ├── api.py              # Endpoints FastAPI
│   ├── celery_app.py       # Configuração do Celery com RabbitMQ
│   ├── workers.py          # Lógica das tarefas (Tasks)
│   ├── models.py           # Tabelas do Banco (SQLAlchemy)
│   ├── schemas.py          # Validação de Dados (Pydantic)
│   ├── database.py         # Conexão DB
│   ├── detector.py         # Lógica de PII (Presidio/Regex)
│   └── llm_client.py       # Cliente HTTP para Ollama
└── tests/
    ├── index.html          # Frontend de Teste (Vue.js)
    └── test_main.http      # Testes HTTP manuais
```

---

## 🚀 Comandos Essenciais

### Subir o Projeto
```bash
docker-compose up -d --build
```

### Ver Logs
```bash
# API
docker logs -f sigilo-api

# Workers
docker logs -f sigilo-worker-deteccao
docker logs -f sigilo-worker-llm

# RabbitMQ
docker logs -f sigilo-rabbitmq
```

### Acessar Painel RabbitMQ
*   **URL**: `http://localhost:15672` (ou via tunnel se configurado)
*   **User**: `admin`
*   **Pass**: `secret123`

### Teste de Conexão Redis
Acesse: `https://seu-dominio.com/debug-redis`

---

## ⚠️ Pontos de Atenção (Troubleshooting)

1.  **Erro 500 no `/status`**:
    *   Geralmente causado por inconsistência no JSON do Redis (ex: falta `updated_at`).
    *   Solução: O código atual já possui fallback. Se persistir, limpe o Redis (`docker exec sigilo-redis redis-cli FLUSHALL`).

2.  **Ollama Lento ou Timeout**:
    *   O modelo Qwen 2.5 1.5B é leve, mas se a VPS tiver < 4GB RAM, pode engasgar.
    *   O `llm_client.py` tem timeout de 30s e fallback automático (retorna resumo padrão se falhar).

3.  **RabbitMQ Connection Error**:
    *   Verifique se o container `sigilo-rabbitmq` está saudável (`docker ps`).
    *   O Celery tem retry automático na inicialização.

---

**Versão do Guia**: 2.0 (RabbitMQ Edition)
**Data**: 28/01/2026
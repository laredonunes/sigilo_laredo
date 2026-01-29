# Changelog - Projeto Sigilo

Todas as alterações notáveis neste projeto serão documentadas neste arquivo.

## [2.0.0] - 2026-01-29

### 🚀 Arquitetura e Infraestrutura
- **Migração para RabbitMQ**: Substituído o Redis como broker de mensagens pelo RabbitMQ para maior robustez e observabilidade.
- **Otimização de Memória (Multi-stage Build)**:
    - Criado `Dockerfile` com estágios `base` (leve) e `heavy` (pesado).
    - Workers leves (`banco`, `llm`, `dicionario`) agora consomem ~80MB (antes ~2GB).
    - Apenas `worker-deteccao` carrega as bibliotecas pesadas de NLP.
- **Lazy Loading**: Refatorado `src/workers.py` para carregar modelos de IA apenas quando necessário.
- **Ollama Otimizado**: Configurado `KEEP_ALIVE=-1` para manter o modelo na RAM e `NUM_PARALLEL=1` para economizar recursos.

### 🛡️ Segurança e Compliance (LGPD)
- **IAM Centralizado**: Criado módulo `src/iam/iam_man.py` suportando Mock, Keycloak e Google Auth.
- **RBAC (Role-Based Access Control)**: Implementado decorador `admin_required` para proteger rotas de auditoria.
- **Anonimização Segura**:
    - Adicionado tratamento de erro crítico no `src/detector.py`.
    - Em caso de falha no Presidio, o texto é mascarado totalmente para evitar vazamento de PII.
    - Implementado fallback de idioma (PT -> EN) para melhorar a detecção.
- **Rate Limiting**: Adicionado `slowapi` para limitar requisições por IP (10 req/min) no endpoint de detecção.

### ✨ Funcionalidades
- **Dashboard Unificado**: Criado `tests/dashboard.html` com abas de Demo, Auditoria (Admin) e Status.
- **Auditoria**: Novos endpoints `/auditoria/pedidos` para listar e detalhar processamentos (apenas Admin).
- **Health Check Detalhado**: Endpoint `/health` agora verifica conectividade com Redis, Postgres e Ollama.

### 🔧 Correções de Bugs
- **Erro 500 na API**: Corrigido bug onde o campo `updated_at` faltava no status inicial do Redis.
- **Celery Tasks**: Corrigido erro de "unregistered task" adicionando `include=['src.workers']` no `celery_app.py`.
- **OOM Kill**: Ajustados limites de memória e concorrência no `docker-compose.yml` para estabilidade em VPS de 16GB.

---

## [1.0.0] - 2026-01-28

### Inicial
- Implementação inicial com FastAPI, Celery, Redis e PostgreSQL.
- Integração com Ollama (Qwen 2.5) para resumos inteligentes.
- Pipeline de 3 camadas: Regex -> Presidio -> Anonimização.
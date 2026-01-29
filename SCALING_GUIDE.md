# 🚀 Guia de Escalabilidade e Produção - Projeto Sigilo

Este documento descreve as estratégias para escalar a API de Detecção de PII para suportar alta demanda, mantendo a segurança e a performance.

---

## 1. Estratégia de Escala Horizontal (Adicionando Poder)

A arquitetura baseada em filas (RabbitMQ) permite escalar cada componente independentemente.

### 🏭 Escalonando Workers
O gargalo geralmente é a CPU (Detecção/IA). Para processar mais pedidos por segundo:

1.  **Adicione mais réplicas no Docker Compose:**
    ```bash
    # Exemplo: Subir 4 workers de detecção e 2 de LLM
    docker-compose up -d --scale worker-deteccao=4 --scale worker-llm=2
    ```

2.  **Em Cluster (Docker Swarm / Kubernetes):**
    *   A arquitetura já é *stateless*. Basta implantar os serviços em múltiplos nós.
    *   O RabbitMQ e o Redis atuam como o "sistema nervoso" central, distribuindo as tarefas automaticamente para qualquer worker livre em qualquer máquina.

### 🧠 Escalonando a IA (Ollama)
O modelo Qwen 2.5 roda na CPU/GPU.
*   **Vertical:** Aumente a RAM e vCPUs da máquina onde o Ollama roda.
*   **Horizontal:** Suba múltiplos containers Ollama atrás de um Load Balancer (Nginx/HAProxy) e aponte a variável `OLLAMA_URL` dos workers para o LB.

---

## 2. Tuning de Performance (Ajustes Finos)

### 🐇 RabbitMQ
*   **Prefetch Count:** Atualmente configurado como `1` no Celery (`worker_prefetch_multiplier`).
    *   *Cenário:* Se as tarefas forem muito rápidas, aumente para `4` ou `10` para reduzir o overhead de rede.
    *   *Cenário:* Se forem pesadas (como IA), mantenha em `1` para evitar que um worker trave com várias tarefas pesadas na fila.

### 🐘 PostgreSQL
*   **Conexões:** O `worker-banco` usa um pool. Se escalar muito os workers, aumente o `max_connections` no Postgres.
*   **Índices:** As tabelas já têm índices em `origem_id`. Para relatórios pesados, considere criar índices em `created_at` e `tipo` (entidade).

### 🐍 Celery & Python
*   **Otimização de Memória:** Já implementamos o *Multi-stage Build* e *Lazy Loading*.
*   **Reinício Automático:** Configuramos `worker_max_tasks_per_child=10` para evitar vazamento de memória (memory leaks) em processos de longa duração.

---

## 3. Monitoramento e Observabilidade

Para produção, recomenda-se integrar uma stack de monitoramento:

1.  **Filas (RabbitMQ Management):**
    *   Acesse `http://seu-host:15672`.
    *   Vigie a métrica **"Ready" messages**. Se começar a acumular, suba mais workers.

2.  **Logs (ELK / Loki):**
    *   Configure o Docker para enviar logs para um agregador (Elasticsearch ou Loki).
    *   Os logs da aplicação já estão estruturados em JSON-friendly format (INFO/ERROR).

3.  **Métricas (Prometheus + Grafana):**
    *   Use o **Flower** (`http://seu-host:5555`) para exportar métricas do Celery para o Prometheus.
    *   Crie alertas para: "Tasks falhando", "Tempo de processamento > 30s", "Fila > 1000 itens".

---

## 4. Segurança em Escala

*   **Segredos:** Em produção, **NUNCA** use o `.env` no repositório. Use *Docker Secrets* ou *Vault*.
*   **Rede:** Mantenha o RabbitMQ e Redis em rede privada (como já feito no Docker Compose). Apenas a API deve ser exposta (via Tunnel ou Reverse Proxy com SSL).
*   **Limitação de Taxa (Rate Limiting):** Implemente no Nginx ou na própria API (via Redis) para evitar abuso de um único IP.

---

## 5. Backup e Disaster Recovery

1.  **Banco de Dados:**
    *   Configure backups diários do volume `postgres_data`.
    *   Use `pg_dump` para backup lógico periódico.

2.  **Persistência de Filas:**
    *   As filas do RabbitMQ são duráveis (`durable=True` por padrão no Celery). Se o RabbitMQ cair, as mensagens não processadas são recuperadas ao voltar.

---

**Resumo para o CTO:**
> "O sistema foi desenhado para ser elástico. Podemos dobrar a capacidade de processamento em minutos apenas adicionando mais containers de workers, sem alterar uma linha de código."

**Data:** 29/01/2026
**Versão:** 1.0
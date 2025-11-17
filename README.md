# Agentic Slot Filling - WhatsApp Lead Qualification SaaS

Sistema de triagem inteligente para WhatsApp usando IA agêntica (PydanticAI + Gemini Flash).

## 🚀 Setup Rápido

### 1. Pré-requisitos
- Docker & Docker Compose
- API Key do Google Gemini (grátis em https://makersuite.google.com/app/apikey)

### 2. Configuração

```bash
# Configure variáveis de ambiente
cp .env.example .env
# Edite .env com suas API keys

# Suba containers
docker-compose up -d

# Aguarde 40s (Evolution precisa subir)
docker-compose logs -f evolution

# Inicialize banco (após implementar scripts)
docker-compose exec backend python scripts/init_db.py
```

### 3. Conecte WhatsApp (QR Code)

```bash
# Através de script (após implementar)
docker-compose exec backend python scripts/create_session.py --session minha-empresa

# Ou via API:
curl -X POST http://localhost:8000/api/v1/sessions/qr \
  -H "Content-Type: application/json" \
  -d '{"session_name": "minha-empresa"}'
```

Escaneie o QR code com WhatsApp.

### 4. Teste

Envie mensagem de teste:
> "Oi, procuro apartamento 2 quartos em Pinheiros até 500 mil"

Verifique logs:
```bash
docker-compose logs -f backend celery-worker
```

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────┐
│  Cliente WhatsApp                       │
│  ├─ Envia mensagem                      │
│  └─ Recebe resposta humanizada          │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  Evolution API v2 (WebJS)               │
│  ├─ Gerencia conexões WhatsApp          │
│  ├─ Envia webhooks para backend         │
│  └─ Persistência: DEL_INSTANCE=false    │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  Backend FastAPI                        │
│  ├─ Recebe webhook                      │
│  ├─ Extrai slots com PydanticAI         │
│  ├─ Enfileira resposta (Celery)         │
│  └─ Aplica warmup + shadow mode         │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  Celery Worker                          │
│  ├─ Simula digitação                    │
│  ├─ Envia resposta via Evolution        │
│  └─ Atualiza estado do lead             │
└─────────────────────────────────────────┘
```

## 📊 Endpoints

- `POST /api/v1/webhook` - Recebe mensagens
- `GET /api/v1/leads` - Lista leads
- `POST /api/v1/sessions/qr` - Gera QR code
- `GET /health` - Health check

## 🛡️ Segurança

- Dados sensíveis criptografados (Fernet)
- Rate limiting (warmup 10 dias)
- Typing simulation humanizado
- Shadow Mode (pausa se humano intervir)

## 🔧 Troubleshooting

**Evolution retorna erro 500:**
```bash
docker-compose restart evolution
docker-compose logs evolution
```

**Celery não processa:**
```bash
docker-compose logs celery-worker
```

**Testar extração standalone:**
```bash
docker-compose exec backend python scripts/test_extraction.py
```

## 📝 Próximos Passos

Este é o setup da **FASE 1**. As próximas fases incluem:

- **FASE 2**: Core Services (config.py, models.py, evolution_client.py, slot_extractor.py)
- **FASE 3**: API Endpoints (webhook.py, sessions.py, leads.py, health.py)
- **FASE 4**: Utils e Tasks (typing_simulator.py, warmup_controller.py, celery_app.py)
- **FASE 5**: Scripts de Teste
- **FASE 6**: Testes Unitários

## 🎯 Decisões Arquiteturais

Este projeto implementa decisões validadas por múltiplas fontes de IA:

1. **Evolution API v2 (WebJS)**: Menor risco de ban que WAHA GOWS
2. **PydanticAI**: Simplicidade vs LangGraph (overkill para slot filling)
3. **Gemini Flash**: 50% mais barato que GPT-4o-mini
4. **Cluster de 10**: Mitiga banimento em cascata

Veja `SPEC.md` para detalhes completos.

## 📄 Licença

MIT License - Use livremente para projetos comerciais.

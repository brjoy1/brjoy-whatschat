# 🧪 Guia Completo de Testes - Agentic Slot Filling

Este guia cobre **todos os testes** que você deve fazer antes de usar em produção.

---

## 📋 Pré-requisitos

```bash
# Verificar versões
docker --version          # >= 20.10
docker compose version    # >= 2.0
python3 --version         # >= 3.11
```

---

## 🚀 FASE 1: Testes de Setup (Sem Docker)

### 1.1. Configurar Variáveis de Ambiente

```bash
# Copiar .env.example
cp .env.example .env

# Gerar chave de criptografia
python3 scripts/generate_encryption_key.py

# Copiar saída e adicionar ao .env
nano .env
```

**Variáveis obrigatórias:**
```bash
GEMINI_API_KEY=AIza...                    # ← Sua chave do Google AI Studio
EVOLUTION_API_KEY=minha-chave-secreta     # ← Qualquer string aleatória
POSTGRES_PASSWORD=senha-super-segura      # ← Senha do PostgreSQL
ENCRYPTION_KEY=gAAAAABl...                # ← Gerada pelo script acima
```

### 1.2. Validar Imports Python (Sem Import Circular)

```bash
# Teste 1: Importar webhook sem erro
python3 -c "from app.api import webhook; print('✅ webhook OK')"

# Teste 2: Importar message_tasks sem erro
python3 -c "from app.tasks import message_tasks; print('✅ message_tasks OK')"

# Teste 3: Importar evolution_client
python3 -c "from app.services import evolution_client; print('✅ evolution_client OK')"

# Teste 4: Importar slot_extractor
python3 -c "from app.services import slot_extractor; print('✅ slot_extractor OK')"
```

**Esperado:** Todos devem printar ✅ sem erros.

### 1.3. Testar Validação Pydantic

```bash
python3 scripts/test_extraction.py
```

**Esperado:**
```
🚀 Inicializando SlotExtractor...
✅ SlotExtractor inicializado

============================================================
📝 Teste: Caso completo
============================================================

📥 Mensagens:
  1. Oi, quero comprar um apartamento de 2 quartos em Pinheiros
  2. Meu orçamento é até 500 mil
  3. Meu nome é João Silva
  4. Telefone é 11 98765-4321

🧠 Extraindo slots...

✅ Slots extraídos:
  Total: 7/11 slots
  ✓ nome: João Silva
  ✓ telefone: 11987654321
  ✓ tipo_imovel: apartamento
  ✓ finalidade: comprar
  ✓ localizacao_desejada: Pinheiros
  ✓ num_quartos: 2
  ✓ orcamento_max: 500000.0

✅ Todos campos críticos preenchidos!

❓ Próxima pergunta: Em qual região ou bairro você prefere? 📍

✅ PASSOU: 7 >= 7 slots esperados

📊 Slots: 7/11 | Qualificação: 71%
```

### 1.4. Teste Interativo de Extração

```bash
python3 scripts/test_extraction.py --interactive
```

**Teste conversando:**
```
Cliente: quero apto 2 quartos
🧠 Analisando...

📊 Slots: 2/11
Informações coletadas:
  ✓ tipo_imovel: apartamento
  ✓ num_quartos: 2

Assistente: Você quer comprar ou alugar? 🤝

Cliente: comprar em pinheiros 500k
🧠 Analisando...

📊 Slots: 5/11
Informações coletadas:
  ✓ tipo_imovel: apartamento
  ✓ finalidade: comprar
  ✓ localizacao_desejada: Pinheiros
  ✓ num_quartos: 2
  ✓ orcamento_max: 500000.0

Assistente: Antes de continuarmos, qual é o seu nome? 😊
```

### 1.5. Executar Suite de Testes Automatizada

```bash
chmod +x scripts/run_tests.sh
./scripts/run_tests.sh
```

**Esperado:**
```
🚀 Iniciando testes do Agentic Slot Filling...

▶ 1. Verificando arquivo .env
✅ .env configurado
▶ 2. Verificando ENCRYPTION_KEY
✅ ENCRYPTION_KEY configurada
▶ 3. Testando imports Python
✅ webhook.py OK
✅ message_tasks.py OK
✅ evolution_client.py OK
✅ slot_extractor.py OK
▶ 4. Validando docker-compose.yml
✅ docker-compose.yml válido
▶ 5. Verificando dependências Python
✅ Todas dependências críticas presentes
▶ 6. Testando validação Pydantic
✅ Validação de telefone OK
✅ Rejeição de telefone inválido OK
▶ 7. Verificando scripts
✅ Scripts prontos
▶ 8. Verificando estrutura de diretórios
✅ Estrutura de diretórios OK

════════════════════════════════════════════════
✅ TODOS OS TESTES PASSARAM!
════════════════════════════════════════════════
```

---

## 🐳 FASE 2: Testes com Docker

### 2.1. Subir Containers

```bash
# Subir em modo detached
docker-compose up -d

# Verificar logs
docker-compose logs -f
```

**Aguardar mensagens:**
```
evolution-api    | ✅ Evolution API v2.1.3 started
postgres-db      | database system is ready to accept connections
redis-cache      | Ready to accept connections
backend-api      | Application startup complete
celery-worker    | celery@... ready
```

**IMPORTANTE:** Evolution API demora ~40 segundos para subir!

### 2.2. Verificar Health Checks

```bash
# Health check básico
curl http://localhost:8000/health
```

**Esperado:**
```json
{
  "status": "healthy",
  "service": "agentic-slot-filling-api",
  "timestamp": "2025-11-17T..."
}
```

```bash
# Health check detalhado
curl http://localhost:8000/health/detailed
```

**Esperado:**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-17T...",
  "services": {
    "database": {
      "status": "healthy",
      "message": "PostgreSQL conectado"
    },
    "redis": {
      "status": "healthy",
      "message": "Redis conectado"
    },
    "evolution_api": {
      "status": "healthy",
      "message": "Evolution API disponível"
    }
  }
}
```

### 2.3. Inicializar Banco de Dados

```bash
docker-compose exec backend python scripts/init_db.py
```

**Esperado:**
```
🚀 Inicializando banco de dados...
Database URL: postgres:5432/agentic_slots

📝 Criando tabelas...
✅ Tabelas criadas: whatsapp_sessions, leads, conversation_messages

🎉 Banco de dados inicializado com sucesso!
```

### 2.4. Verificar Tabelas Criadas

```bash
docker-compose exec postgres psql -U postgres -d agentic_slots -c "\dt"
```

**Esperado:**
```
                    List of relations
 Schema |          Name           | Type  |  Owner
--------+-------------------------+-------+----------
 public | conversation_messages   | table | postgres
 public | leads                   | table | postgres
 public | whatsapp_sessions       | table | postgres
(3 rows)
```

---

## 📱 FASE 3: Testes com WhatsApp (QR Code)

### 3.1. Criar Sessão e Gerar QR Code

```bash
docker-compose exec backend python scripts/create_session.py --session teste-mvp
```

**Esperado:**
```
📡 Conectando à Evolution API...
✅ Evolution API está disponível

🔨 Criando instância 'teste-mvp'...
✅ Instância criada

📱 Gerando QR code...
✅ Sessão criada no banco

============================================================
📱 QR CODE GERADO COM SUCESSO!
============================================================

Para escanear o QR code:
1. Abra WhatsApp no celular
2. Vá em Configurações > Aparelhos conectados
3. Toque em 'Conectar um aparelho'
4. Escaneie o QR code exibido

Ou acesse via API:
GET http://localhost:8000/api/v1/sessions/teste-mvp

============================================================

⏳ Aguardando conexão... (pressione Ctrl+C para cancelar)
```

### 3.2. Escanear QR Code

1. Abra WhatsApp no celular
2. Configurações → Aparelhos conectados
3. Conectar um aparelho
4. Escaneie o QR

**Esperado no terminal:**
```
✅ WhatsApp conectado com sucesso!
🎉 Sessão 'teste-mvp' está pronta para uso!
```

### 3.3. Verificar Status da Sessão

```bash
curl http://localhost:8000/api/v1/sessions/teste-mvp | jq
```

**Esperado:**
```json
{
  "id": 1,
  "session_name": "teste-mvp",
  "status": "connected",
  "qr_code": null,
  "phone_number": "5511999999999",
  "created_at": "2025-11-17T..."
}
```

---

## 💬 FASE 4: Teste End-to-End (Mensagem Real)

### 4.1. Enviar Mensagem de Teste no WhatsApp

**Do seu celular, envie para o número conectado:**

```
Mensagem 1: Oi, quero um apartamento
```

### 4.2. Verificar Logs do Backend

```bash
docker-compose logs -f backend
```

**Esperado:**
```
📥 Processando mensagem de 5511987654321
✨ Novo lead: 5511987654321
🧠 Extraindo slots para lead 1
✅ Lead 1 atualizado: 1/11 slots, score 9.09
❓ Próxima pergunta: Você quer comprar ou alugar? 🤝
```

### 4.3. Verificar Logs do Celery

```bash
docker-compose logs -f celery-worker
```

**Esperado:**
```
📤 Task iniciada: enviar mensagem para 5511987654321
🤖 Iniciando envio humanizado para 5511987654321
✓ Mensagem marcada como lida
⏱️ Aguardando 3.2s (leitura)
✓ Digitação iniciada
⏱️ Digitando por 8.5s (32 caracteres)
✓ Digitação parada
⏱️ Aguardando 1.1s (antes de enviar)
✅ Mensagem humanizada enviada para 5511987654321
```

### 4.4. Verificar Resposta no WhatsApp

**Você deve receber no celular (com delays humanizados):**
```
✓✓ (visto)
   digitando...
Você quer comprar ou alugar? 🤝
```

### 4.5. Continuar Conversa

**Envie:**
```
Mensagem 2: comprar em pinheiros
Mensagem 3: até 500 mil
Mensagem 4: meu nome é João
```

**Verifique se recebe perguntas progressivas:**
```
Em qual região ou bairro você prefere? 📍
Qual é o seu orçamento máximo? 💰
Antes de continuarmos, qual é o seu nome? 😊
Qual o melhor telefone para contato (com DDD)? 📱
```

### 4.6. Verificar Lead no Banco

```bash
curl http://localhost:8000/api/v1/leads | jq
```

**Esperado:**
```json
[
  {
    "id": 1,
    "session_id": 1,
    "phone": "5511987654321",
    "status": "active",
    "nome": "João",
    "tipo_imovel": "apartamento",
    "finalidade": "comprar",
    "localizacao_desejada": "Pinheiros",
    "orcamento_max": 500000.0,
    "slots_filled": 5,
    "total_messages": 4,
    "qualification_score": 54.55,
    "shadow_mode": false
  }
]
```

### 4.7. Verificar Histórico de Mensagens

```bash
curl http://localhost:8000/api/v1/leads/1/messages | jq
```

**Esperado:**
```json
{
  "lead_id": 1,
  "total_messages": 8,
  "messages": [
    {
      "id": 1,
      "role": "user",
      "content": "Oi, quero um apartamento",
      "created_at": "2025-11-17T..."
    },
    {
      "id": 2,
      "role": "assistant",
      "content": "Você quer comprar ou alugar? 🤝",
      "created_at": "2025-11-17T..."
    },
    ...
  ]
}
```

---

## 🧪 FASE 5: Testes de Segurança e Limites

### 5.1. Testar Warmup Controller

```bash
# Simular 21 novos contatos (deve bloquear no 21º)
docker-compose exec backend python << 'EOF'
from app.utils.warmup_controller import WarmupController
from app.api.deps import get_redis
import redis

redis_client = redis.from_url("redis://redis:6379/0", decode_responses=True)
warmup = WarmupController(redis_client)

# Registrar sessão
warmup.register_session_activation("teste-mvp")

# Tentar 21 contatos
for i in range(21):
    phone = f"5511{i:09d}"
    try:
        can_contact, msg = warmup.can_contact_new_number("teste-mvp", phone, enforce=True)
        print(f"{i+1}. {phone}: {msg}")
    except Exception as e:
        print(f"{i+1}. {phone}: ❌ BLOQUEADO - {e}")
EOF
```

**Esperado:**
```
1. 5511000000000: Contato permitido (1/20 hoje, dia 0/10)
2. 5511000000001: Contato permitido (2/20 hoje, dia 0/10)
...
20. 5511000000019: Contato permitido (20/20 hoje, dia 0/10)
21. 5511000000020: ❌ BLOQUEADO - Limite diário de 20 novos contatos atingido
```

### 5.2. Testar Rate Limiting de Mensagens

```bash
docker-compose exec backend python << 'EOF'
from app.utils.warmup_controller import WarmupController
from app.api.deps import get_redis
import redis

redis_client = redis.from_url("redis://redis:6379/0", decode_responses=True)
warmup = WarmupController(redis_client)

phone = "5511999999999"

# Tentar 5 mensagens (deve bloquear na 5ª)
for i in range(5):
    try:
        can_send, msg = warmup.can_send_message("teste-mvp", phone, enforce=True)
        print(f"Mensagem {i+1}: {msg}")
    except Exception as e:
        print(f"Mensagem {i+1}: ❌ BLOQUEADO - {e}")
EOF
```

**Esperado:**
```
Mensagem 1: Mensagem permitida (1/4 na última hora)
Mensagem 2: Mensagem permitida (2/4 na última hora)
Mensagem 3: Mensagem permitida (3/4 na última hora)
Mensagem 4: Mensagem permitida (4/4 na última hora)
Mensagem 5: ❌ BLOQUEADO - Limite de 4 mensagens/hora atingido
```

### 5.3. Testar Shadow Mode

```bash
# Simular humano assumindo controle
docker-compose exec backend python << 'EOF'
from app.services.conversation_mgr import ConversationManager
from app.database import SessionLocal

db = SessionLocal()
conv_mgr = ConversationManager(db)

# Ativar shadow mode
conv_mgr.enable_shadow_mode(lead_id=1, reason="Teste manual")

# Verificar
from app.models import Lead
lead = db.query(Lead).filter(Lead.id == 1).first()
print(f"Shadow Mode: {lead.shadow_mode}")
print(f"Desde: {lead.shadow_mode_since}")

db.close()
EOF
```

**Esperado:**
```
Shadow Mode: True
Desde: 2025-11-17 15:30:00+00:00
```

**Agora envie mensagem no WhatsApp - IA NÃO deve responder!**

---

## 📊 FASE 6: Testes de Performance

### 6.1. Testar Latência de Extração

```bash
time docker-compose exec backend python scripts/test_extraction.py
```

**Esperado:** < 5 segundos para 4 casos de teste

### 6.2. Monitorar Pool de Conexões PostgreSQL

```bash
# Terminal 1: Monitorar conexões
watch -n 2 'docker-compose exec postgres psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"'

# Terminal 2: Enviar 50 mensagens simultâneas
for i in {1..50}; do
  curl -X POST http://localhost:8000/api/v1/webhook \
    -H "Content-Type: application/json" \
    -d "{\"instance\": \"teste\", \"data\": {}}" &
done
wait
```

**Esperado:** Conexões devem estabilizar (pool_size=10, max_overflow=20)

### 6.3. Testar Celery Queue

```bash
# Verificar tasks na fila
docker-compose exec redis redis-cli LLEN celery

# Verificar workers ativos
docker-compose exec celery-worker celery -A app.tasks.celery_app inspect active
```

---

## ✅ Checklist de Testes Completos

### Setup Inicial
- [ ] `.env` configurado com todas as chaves
- [ ] `ENCRYPTION_KEY` gerada
- [ ] Imports Python sem erros
- [ ] Validação Pydantic funcionando
- [ ] Suite de testes automatizada passou

### Docker
- [ ] Containers sobem sem erros
- [ ] Health checks retornam `healthy`
- [ ] Banco de dados inicializado
- [ ] 3 tabelas criadas

### WhatsApp
- [ ] QR code gerado
- [ ] WhatsApp conectado
- [ ] Status = `connected`

### End-to-End
- [ ] Mensagem recebida no backend
- [ ] Slots extraídos corretamente
- [ ] Resposta enviada com delays humanizados
- [ ] Lead salvo no banco
- [ ] Histórico de mensagens registrado

### Segurança
- [ ] Warmup bloqueia após 20 contatos/dia
- [ ] Rate limit bloqueia após 4 msgs/hora
- [ ] Shadow mode pausa IA
- [ ] Telefones criptografados no banco

### Performance
- [ ] Extração de slots < 5s
- [ ] Pool de conexões estável
- [ ] Celery processa tasks

---

## 🐛 Troubleshooting

### Evolution API não sobe

```bash
# Verificar logs
docker-compose logs evolution

# Se travado em "Starting Chrome..."
docker-compose restart evolution

# Aguardar 40s completos antes de testar
```

### Celery não processa tasks

```bash
# Verificar worker
docker-compose logs celery-worker

# Reiniciar
docker-compose restart celery-worker

# Verificar Redis
docker-compose exec redis redis-cli ping
# Esperado: PONG
```

### Extração de slots falha

```bash
# Verificar API key do Gemini
docker-compose exec backend python << 'EOF'
import google.generativeai as genai
from app.config import settings

genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')
response = model.generate_content("Olá")
print(response.text)
EOF
```

**Esperado:** Resposta do Gemini

---

## 🎉 Testes Concluídos!

Se todos os testes passaram, seu sistema está **100% funcional e production-ready!**

**Próximos passos:**
1. Deploy em staging
2. Testes com usuários reais
3. Monitoramento com Sentry/Prometheus
4. Configurar backups automáticos

---

**Dúvidas?** Consulte `IMPLEMENTATION_SUMMARY.md` e `FIXES_APPLIED.md`

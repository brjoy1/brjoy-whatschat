#!/bin/bash
# Script de teste automatizado para validar o setup completo

set -e  # Para em caso de erro

echo "🚀 Iniciando testes do Agentic Slot Filling..."
echo ""

# Cores para output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Função para testar
test_step() {
    echo -e "${YELLOW}▶ $1${NC}"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
    exit 1
}

# 1. Verificar .env
test_step "1. Verificando arquivo .env"
if [ ! -f ".env" ]; then
    error ".env não encontrado! Execute: cp .env.example .env"
fi

if ! grep -q "GEMINI_API_KEY=your_gemini_key_here" .env; then
    success ".env configurado"
else
    error ".env ainda com valores padrão! Configure GEMINI_API_KEY"
fi

# 2. Verificar chave de criptografia
test_step "2. Verificando ENCRYPTION_KEY"
if grep -q "^ENCRYPTION_KEY=" .env && ! grep -q "ENCRYPTION_KEY=$" .env; then
    success "ENCRYPTION_KEY configurada"
else
    echo "⚠️  ENCRYPTION_KEY não configurada. Gerando..."
    python scripts/generate_encryption_key.py | grep "ENCRYPTION_KEY=" >> .env
    success "ENCRYPTION_KEY gerada e adicionada ao .env"
fi

# 3. Testar imports Python (sem imports circulares)
test_step "3. Testando imports Python"
python3 -c "from app.api import webhook" 2>/dev/null && success "webhook.py OK" || error "Erro em webhook.py"
python3 -c "from app.tasks import message_tasks" 2>/dev/null && success "message_tasks.py OK" || error "Erro em message_tasks.py"
python3 -c "from app.services import evolution_client" 2>/dev/null && success "evolution_client.py OK" || error "Erro em evolution_client.py"
python3 -c "from app.services import slot_extractor" 2>/dev/null && success "slot_extractor.py OK" || error "Erro em slot_extractor.py"

# 4. Validar docker-compose.yml
test_step "4. Validando docker-compose.yml"
if command -v docker &> /dev/null; then
    docker compose config > /dev/null 2>&1 && success "docker-compose.yml válido" || error "docker-compose.yml inválido"
else
    echo "⚠️  Docker não instalado - pulando validação"
fi

# 5. Verificar requirements.txt
test_step "5. Verificando dependências Python"
if grep -q "pydantic-ai" requirements.txt && \
   grep -q "google-generativeai" requirements.txt && \
   grep -q "tenacity" requirements.txt; then
    success "Todas dependências críticas presentes"
else
    error "Faltam dependências em requirements.txt"
fi

# 6. Testar validação Pydantic
test_step "6. Testando validação Pydantic"
python3 << 'EOF'
from app.schemas import LeadImobiliaria

# Teste 1: Telefone válido
try:
    lead = LeadImobiliaria(telefone="11987654321")
    print("✅ Validação de telefone OK")
except Exception as e:
    print(f"❌ Erro: {e}")
    exit(1)

# Teste 2: Telefone inválido
try:
    lead = LeadImobiliaria(telefone="123")
    print("❌ Validação não funcionou - aceitou telefone inválido")
    exit(1)
except ValueError:
    print("✅ Rejeição de telefone inválido OK")
EOF

# 7. Verificar scripts
test_step "7. Verificando scripts"
for script in scripts/*.py; do
    if [ -x "$script" ]; then
        echo "  ✓ $(basename $script) executável"
    else
        chmod +x "$script"
        echo "  ✓ $(basename $script) tornado executável"
    fi
done
success "Scripts prontos"

# 8. Verificar estrutura de diretórios
test_step "8. Verificando estrutura de diretórios"
required_dirs=("app/api" "app/core" "app/services" "app/tasks" "app/utils" "scripts" "tests")
for dir in "${required_dirs[@]}"; do
    if [ -d "$dir" ]; then
        echo "  ✓ $dir"
    else
        error "Diretório $dir não encontrado"
    fi
done
success "Estrutura de diretórios OK"

echo ""
echo "════════════════════════════════════════════════"
echo -e "${GREEN}✅ TODOS OS TESTES PASSARAM!${NC}"
echo "════════════════════════════════════════════════"
echo ""
echo "Próximos passos:"
echo "1. docker-compose up -d"
echo "2. docker-compose exec backend python scripts/init_db.py"
echo "3. docker-compose exec backend python scripts/create_session.py --session teste"
echo "4. docker-compose exec backend python scripts/test_extraction.py"
echo ""

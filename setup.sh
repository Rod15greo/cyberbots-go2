#!/bin/bash
# ============================================================
# setup.sh — Primeira configuração no Jetson do Go2 EDU
# Execute UMA VEZ quando chegar ao laboratório
# ============================================================

set -e

echo ""
echo "=== CyberBots Go2 — Setup inicial ==="
echo ""

# 1. Verificar Docker e nvidia-container-runtime
echo "[1/5] Verificando Docker + CUDA runtime..."
if ! command -v docker &>/dev/null; then
    echo "ERRO: Docker nao encontrado. Instale com:"
    echo "  curl -fsSL https://get.docker.com | sh"
    exit 1
fi

if ! docker info 2>/dev/null | grep -q "Runtimes.*nvidia"; then
    echo "AVISO: nvidia-container-runtime nao detectado."
    echo "Instale com: sudo apt install nvidia-container-runtime"
    echo "Depois reinicie o Docker: sudo systemctl restart docker"
fi

# 2. Criar .env se nao existir
echo "[2/5] Configurando .env..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "ACAO NECESSARIA: edite o arquivo .env com as configuracoes do servidor:"
    echo "  nano .env"
    echo ""
    echo "Preencha pelo menos:"
    echo "  SERVER_URL=http://IP_DO_SEU_EC2:8000"
    echo "  WS_PUBLISHER_URL=ws://IP_DO_SEU_EC2:8000/ws/publisher"
    echo "  TURN_URL=turn:IP_DO_SEU_EC2:3478"
    echo ""
    read -p "Pressione Enter após editar o .env para continuar..."
else
    echo "  .env ja existe — pulando."
fi

# 3. Buscar chave AES (firmware >= 1.1.15)
echo "[3/5] Chave AES do Go2..."
if grep -q "^GO2_AES_KEY=$" .env 2>/dev/null || grep -q "^GO2_AES_KEY=\"\"" .env 2>/dev/null; then
    echo ""
    echo "  Se o seu Go2 usa firmware >= 1.1.15, voce precisa da chave AES."
    echo "  Para obter:"
    echo "    pip3 install unitree-fetch-aes-key"
    echo "    unitree-fetch-aes-key --email SEU@EMAIL.com --password 'SENHA'"
    echo "  Cole a chave no .env em GO2_AES_KEY=..."
    echo "  Se nao souber a versao do firmware, tente sem a chave primeiro."
    echo ""
else
    echo "  Chave AES configurada."
fi

# 4. Verificar pasta de faces
echo "[4/5] Verificando pasta de faces..."
if [ -z "$(ls -A faces/ 2>/dev/null)" ]; then
    echo ""
    echo "  ACAO NECESSARIA: adicione as fotos das pessoas na pasta faces/"
    echo "  Exemplo:"
    echo "    cp /caminho/para/fotos/*.jpg faces/"
    echo "  Nome do arquivo = nome da pessoa (ex: joao_silva.jpg)"
    echo ""
else
    echo "  Faces encontradas: $(ls faces/ | wc -l) arquivo(s)"
fi

# 5. Build da imagem Docker
echo "[5/5] Construindo imagem Docker (pode levar 10-20 minutos na primeira vez)..."
docker compose build

echo ""
echo "=== Setup concluido! ==="
echo ""
echo "Para iniciar o sistema:"
echo "  docker compose up"
echo ""
echo "Para rodar em background:"
echo "  docker compose up -d"
echo "  docker compose logs -f"
echo ""

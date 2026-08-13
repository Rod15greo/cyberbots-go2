# CyberBots — Go2 EDU Publisher

Publisher WebRTC para o **Unitree Go2 EDU** (Jetson Orin Nano/NX).  
Substitui a Raspberry Pi: usa a câmera integrada do Go2 e processa reconhecimento facial com CUDA diretamente no Jetson.

---

## Quando você chegar ao laboratório — 5 passos

```bash
# 1. Conectar ao Go2 por WiFi ou Ethernet
#    Ethernet: cabo entre seu notebook e o Go2 → Go2 estará em 192.168.123.18
#    WiFi AP:  conectar no hotspot GO2-XXXXXX

# 2. SSH no Jetson Orin
ssh unitree@192.168.123.18
# senha: 123

# 3. Clonar o repositório
git clone https://github.com/Rod15greo/cyberbots-go2
cd cyberbots-go2

# 4. Setup inicial (uma vez só)
chmod +x setup.sh && ./setup.sh

# 5. Rodar
docker compose up
```

Pronto. O Go2 estará publicando o stream para o servidor EC2.

---

## Arquitetura

```
[Câmera Go2 720p/15fps]
       │ H.264 RTP (rede interna)
       ▼
[unitree_webrtc_connect] ← assina stream interno do Go2
       │ frames numpy BGR
       ▼
[InsightFace — Jetson CUDA]
  SCRFD (~8ms) + ArcFace (~2ms)
       │ frame + detecções
       ▼
[WebRTC Publisher — aiortc]
       │ WebRTC + WebSocket
       ▼ (via modem 4G)
[Servidor EC2 — Sinalização]
       │
[Celular → Quest Pro]
```

---

## Configuração do .env

```bash
cp .env.example .env
nano .env
```

| Variável | Descrição | Padrão |
|---|---|---|
| `SERVER_URL` | URL do servidor EC2 | obrigatório |
| `WS_PUBLISHER_URL` | WebSocket do publisher | obrigatório |
| `TURN_URL` | Servidor TURN | obrigatório |
| `TURN_USER` | Usuário TURN | `robot` |
| `TURN_PASS` | Senha TURN | obrigatório |
| `GO2_IP` | IP do Go2 (modo STA) | vazio = modo AP |
| `GO2_AES_KEY` | Chave AES firmware ≥1.1.15 | vazio = sem chave |
| `INSIGHTFACE_MODEL` | `buffalo_l` ou `buffalo_s` | `buffalo_l` |
| `CONFIDENCE_THRESHOLD` | Limiar de reconhecimento | `0.45` |

---

## Adicionar faces

Coloque fotos na pasta `faces/` antes de rodar.  
O nome do arquivo = nome da pessoa.

```
faces/
├── joao_silva.jpg
├── maria_santos.png
└── pedro_oliveira.jpg
```

```bash
# Exemplo: copiar fotos do seu notebook para o Jetson
scp fotos/*.jpg unitree@192.168.123.18:~/cyberbots-go2/faces/
```

---

## Modos de conexão Go2

### Modo AP (Go2 cria hotspot — padrão)
```bash
# Conectar no hotspot: GO2-XXXXXX
# Deixar GO2_IP= vazio no .env
docker compose up
```

### Modo STA (Go2 conectado ao roteador)
```bash
# Descobrir IP do Go2 na sua rede
# Preencher GO2_IP=192.168.x.x no .env
docker compose up
```

### Modo Ethernet (mais estável para desenvolvimento)
```bash
# Cabo entre Go2 e notebook
# Go2 estará em 192.168.123.161, Jetson em 192.168.123.18
ssh unitree@192.168.123.18
```

---

## Firmware ≥ 1.1.15 — Chave AES

Se o Go2 usar firmware novo, precisa de chave AES para WebRTC:

```bash
pip3 install unitree-fetch-aes-key
unitree-fetch-aes-key --email seu@email.com --password 'senha_unitree'
# Cole a chave no .env em GO2_AES_KEY=...
```

---

## Comandos úteis

```bash
# Iniciar
docker compose up -d

# Ver logs em tempo real
docker compose logs -f

# Parar
docker compose down

# Rebuild após mudança no código
docker compose build && docker compose up -d

# Ver uso de GPU no Jetson
sudo tegrastats
# ou
watch -n 1 nvidia-smi
```

---

## Performance esperada (Jetson Orin Nano, JetPack 6)

| Operação | Tempo |
|---|---|
| Detecção SCRFD (CUDA) | ~8ms |
| Reconhecimento ArcFace (CUDA) | ~2ms por face |
| FPS (limitado pela câmera Go2) | **15 fps** |
| Latência total câmera → Quest | ~160–260ms |

---

## Estrutura do projeto

```
cyberbots-go2/
├── Dockerfile              # Imagem para Jetson Orin (aarch64 + CUDA)
├── docker-compose.yml      # Configuração do serviço
├── .env.example            # Template de variáveis de ambiente
├── setup.sh                # Script de primeira configuração
├── faces/                  # Fotos de referência (não versionadas)
│   └── .gitkeep
└── src/
    ├── main.py             # Ponto de entrada — orquestra tudo
    ├── config.py           # Lê variáveis de ambiente
    ├── camera.py           # Câmera Go2 via unitree_webrtc_connect
    ├── face_engine.py      # InsightFace com CUDA
    └── webrtc_publisher.py # aiortc publisher + sinalização EC2
```

---

## Troubleshooting

**Docker não acessa GPU:**
```bash
sudo apt install nvidia-container-runtime
sudo systemctl restart docker
```

**Erro de conexão com câmera Go2:**
- Verificar se o app oficial Unitree está fechado no celular (conflito WebRTC)
- Checar se GO2_AES_KEY é necessária (firmware ≥ 1.1.15)

**InsightFace usando CPU em vez de CUDA:**
```bash
# Dentro do container, verificar providers disponíveis
docker compose run --rm cyberbots-go2 python3 -c \
  "import onnxruntime; print(onnxruntime.get_available_providers())"
# Deve incluir 'CUDAExecutionProvider'
```

**Porta 9991 recusada (WebRTC Go2):**
- Go2 precisa estar ligado e com WiFi ativo
- Verificar modo de conexão (AP vs STA)

# ============================================================
# CyberBots Go2 — Docker para Jetson Orin (JetPack 6 / Ubuntu 22.04)
# Base: NVIDIA L4T CUDA runtime (aarch64)
#
# Para JetPack 5 (Ubuntu 20.04): trocar a linha FROM por:
#   FROM nvcr.io/nvidia/l4t-cuda:11.4.19-runtime
# ============================================================

FROM nvcr.io/nvidia/l4t-cuda:12.2.12-runtime

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH

# ── Dependências de sistema ───────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    python3-dev \
    build-essential \
    cmake \
    git \
    curl \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    ffmpeg \
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libswscale-dev \
    libopus-dev \
    libvpx-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf python3.10 /usr/bin/python3 && \
    ln -sf python3.10 /usr/bin/python

# ── pip atualizado ────────────────────────────────────────────
RUN pip3 install --upgrade pip setuptools wheel

# ── onnxruntime-gpu para Jetson aarch64 ──────────────────────
# NVIDIA disponibiliza wheels específicos para JetPack 6 (CUDA 12.x)
# Se der erro aqui, consulte: https://elinux.org/Jetson_Zoo#ONNX_Runtime
RUN pip3 install --no-cache-dir \
    "onnxruntime-gpu>=1.18.0" \
    || pip3 install --no-cache-dir \
        https://nvidia.box.com/shared/static/iizg3ggrtdkqawkmebbfixo7sce6j365.whl

# ── Dependências Python principais ───────────────────────────
RUN pip3 install --no-cache-dir \
    insightface==0.7.3 \
    opencv-python-headless \
    numpy \
    Pillow

# ── cryptography + pyOpenSSL pinados — versões compatíveis com DTLS ──────────
# Pi (que funcionava) usava cryptography==38.0.4 + pyOpenSSL==23.0.0.
# cryptography>=43 quebra DTLS silenciosamente em Python 3.8/3.10 via pyOpenSSL.
RUN pip3 install --no-cache-dir \
    "cryptography==38.0.4" \
    "pyOpenSSL==23.0.0"

# ── aiortc e dependências WebRTC ─────────────────────────────
RUN pip3 install --no-cache-dir \
    aiortc \
    aioice \
    aiohttp \
    websockets

# ── SDK da Unitree Go2 ────────────────────────────────────────
RUN pip3 install --no-cache-dir \
    unitree_webrtc_connect \
    unitree_sdk2py

# ── Aplicação ─────────────────────────────────────────────────
WORKDIR /app

COPY src/ ./src/

# Pasta de faces (montada como volume em runtime)
RUN mkdir -p /app/faces

# Cache de modelos InsightFace (montado como volume para não baixar sempre)
RUN mkdir -p /root/.insightface/models

CMD ["python3", "src/main.py"]

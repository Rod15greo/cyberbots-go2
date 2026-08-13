import os

SERVER_URL           = os.getenv("SERVER_URL",           "http://100.56.213.149:8000")
WS_PUBLISHER_URL     = os.getenv("WS_PUBLISHER_URL",     "ws://100.56.213.149:8000/ws/publisher")
TURN_URL             = os.getenv("TURN_URL",             "turn:100.56.213.149:3478")
TURN_USER            = os.getenv("TURN_USER",            "robot")
TURN_PASS            = os.getenv("TURN_PASS",            "robot123")

# Go2 network — deixar vazio para modo AP (Go2 cria hotspot proprio)
# preencher com IP do Go2 caso esteja em modo STA (conectado ao seu roteador)
GO2_IP               = os.getenv("GO2_IP",               "")
GO2_AES_KEY          = os.getenv("GO2_AES_KEY",          "")  # necessario em firmware >= 1.1.15

FACES_DIR            = os.getenv("FACES_DIR",            "./faces")
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.45"))
INSIGHTFACE_MODEL    = os.getenv("INSIGHTFACE_MODEL",    "buffalo_l")   # buffalo_s = mais rapido
DET_SIZE             = int(os.getenv("DET_SIZE",         "640"))

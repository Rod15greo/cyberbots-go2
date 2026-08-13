"""
Captura de frames da câmera frontal do Go2 via WebRTC interno.
Substitui o cv2.VideoCapture(0) da Raspberry Pi.
"""

import asyncio
import logging
import numpy as np
import cv2
from config import GO2_IP, GO2_AES_KEY

logger = logging.getLogger("camera")


class Go2Camera:
    def __init__(self, on_frame_callback):
        """
        on_frame_callback: func(frame_bgr: np.ndarray) chamada a cada frame recebido.
        """
        self._on_frame = on_frame_callback
        self._running = False

    async def start(self):
        from unitree_webrtc_connect import UnitreeWebRTCConnection, WebRTCConnectionMethod

        if GO2_IP:
            logger.info(f"Conectando ao Go2 em modo STA — IP: {GO2_IP}")
            conn = UnitreeWebRTCConnection(WebRTCConnectionMethod.LocalSTA, ip=GO2_IP)
        else:
            logger.info("Conectando ao Go2 em modo AP (hotspot do robo)")
            conn = UnitreeWebRTCConnection(WebRTCConnectionMethod.LocalAP)

        if GO2_AES_KEY:
            logger.info("Aplicando chave AES (firmware >= 1.1.15)")
            conn.setAESKey(GO2_AES_KEY)

        conn.setOnVideoFrameReceivedCallback(self._handle_frame)

        self._running = True
        logger.info("Camera Go2 iniciada — aguardando frames...")
        await conn.connect()

    def _handle_frame(self, frame):
        """
        Callback chamado pelo unitree_webrtc_connect a cada frame.
        O frame pode chegar como av.VideoFrame ou como bytes H.264 dependendo da versão.
        """
        try:
            # Tenta tratar como av.VideoFrame (versões mais recentes)
            if hasattr(frame, 'to_ndarray'):
                img = frame.to_ndarray(format='bgr24')
            else:
                # Fallback: frame como bytes JPEG/raw — decodifica com OpenCV
                data = getattr(frame, 'data', frame)
                arr = np.frombuffer(data, dtype=np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

            if img is not None:
                self._on_frame(img)
        except Exception as e:
            logger.error(f"Erro ao processar frame da camera: {e}")

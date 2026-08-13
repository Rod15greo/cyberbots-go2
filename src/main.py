"""
CyberBots — Go2 EDU Publisher
Substitui a Raspberry Pi: câmera Go2 + InsightFace CUDA + WebRTC publisher.
"""

import asyncio
import logging
import sys
import time

import cv2
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")


async def main():
    from face_engine import FaceEngine
    from webrtc_publisher import WebRTCPublisher
    from camera import Go2Camera

    logger.info("=== CyberBots Go2 Publisher iniciando ===")

    # Inicializa InsightFace (carrega modelos ONNX na GPU)
    face_engine  = FaceEngine()
    publisher    = WebRTCPublisher(face_engine)
    loop         = asyncio.get_event_loop()

    last_face_ts = 0.0
    FACE_INTERVAL = 0.3  # processa faces a no máximo ~3x por segundo

    def on_frame(frame_bgr: np.ndarray):
        """
        Callback chamado a cada frame da câmera Go2 (até 15fps).
        Roda na thread do unitree_webrtc_connect — NÃO é async.
        """
        nonlocal last_face_ts

        # Envia o frame ao WebRTC (thread-safe via queue)
        publisher.track.push(frame_bgr)
        publisher.update_fps()

        now = time.time()
        if now - last_face_ts < FACE_INTERVAL:
            return
        last_face_ts = now

        # Processa faces em executor (evita bloquear event loop)
        async def process():
            result = await loop.run_in_executor(None, face_engine.process, frame_bgr)
            for det in result["detections"]:
                if det["confidence"] >= face_engine.threshold:
                    logger.info(
                        f"Face: {det['name']} ({det['confidence']*100:.0f}%) "
                        f"| det={result['detection_ms']}ms "
                        f"| rec={result['recognition_ms']}ms"
                    )
                    await publisher.send_face_match(
                        det["name"],
                        det["confidence"],
                        result["detection_ms"],
                        result["recognition_ms"],
                    )

        asyncio.run_coroutine_threadsafe(process(), loop)

    camera = Go2Camera(on_frame_callback=on_frame)

    logger.info("Iniciando publisher WebRTC e câmera...")
    await asyncio.gather(
        publisher.run(),
        camera.start(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Encerrado pelo usuário.")
        sys.exit(0)

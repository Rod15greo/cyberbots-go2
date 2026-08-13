"""
Pipeline de reconhecimento facial com InsightFace + CUDA (Jetson Orin).
Mesma lógica da Pi, mas usando CUDAExecutionProvider.
"""

import logging
import time
import numpy as np
import cv2
from pathlib import Path
from config import FACES_DIR, CONFIDENCE_THRESHOLD, INSIGHTFACE_MODEL, DET_SIZE

logger = logging.getLogger("face_engine")


class FaceEngine:
    def __init__(self):
        import insightface
        logger.info(f"Carregando InsightFace modelo '{INSIGHTFACE_MODEL}' com CUDA...")
        self.app = insightface.app.FaceAnalysis(
            name=INSIGHTFACE_MODEL,
            providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
        )
        self.app.prepare(ctx_id=0, det_size=(DET_SIZE, DET_SIZE))
        self.threshold = CONFIDENCE_THRESHOLD
        self.known_faces: dict[str, np.ndarray] = {}
        self._load_faces()

    def _load_faces(self):
        faces_path = Path(FACES_DIR)
        if not faces_path.exists():
            logger.warning(f"Pasta de faces não encontrada: {FACES_DIR}")
            return

        count = 0
        for img_file in sorted(faces_path.glob("*")):
            if img_file.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}:
                continue
            name = img_file.stem
            img = cv2.imread(str(img_file))
            if img is None:
                logger.warning(f"Nao foi possivel ler: {img_file}")
                continue
            faces = self.app.get(img)
            if not faces:
                logger.warning(f"Nenhuma face detectada em: {img_file.name}")
                continue
            self.known_faces[name] = faces[0].normed_embedding
            count += 1

        logger.info(f"{count} faces carregadas: {list(self.known_faces.keys())}")

    def process(self, frame_bgr: np.ndarray) -> dict:
        """
        Processa um frame e retorna dict com:
        - detections: lista de faces detectadas com nome e confiança
        - detection_ms: tempo de detecção SCRFD
        - recognition_ms: tempo total de reconhecimento ArcFace
        """
        t_det = time.monotonic()
        faces = self.app.get(frame_bgr)
        detection_ms = (time.monotonic() - t_det) * 1000

        results = []
        t_rec = time.monotonic()
        for face in faces:
            name, confidence = self._identify(face.normed_embedding)
            results.append({
                "name":       name,
                "confidence": confidence,
                "bbox":       face.bbox.tolist(),
            })
        recognition_ms = (time.monotonic() - t_rec) * 1000

        return {
            "detections":     results,
            "detection_ms":   round(detection_ms, 1),
            "recognition_ms": round(recognition_ms, 1),
        }

    def _identify(self, embedding: np.ndarray) -> tuple[str, float]:
        if not self.known_faces:
            return "Desconhecido", 0.0

        scores = {
            name: float(np.dot(embedding, ref))
            for name, ref in self.known_faces.items()
        }
        best_name = max(scores, key=scores.get)
        best_score = scores[best_name]

        if best_score >= self.threshold:
            return best_name, best_score
        return "Desconhecido", best_score

    def register_face(self, name: str, img_bgr: np.ndarray) -> bool:
        """Registra uma nova face em tempo de execução (via request do servidor)."""
        faces = self.app.get(img_bgr)
        if not faces:
            return False
        self.known_faces[name] = faces[0].normed_embedding
        logger.info(f"Face registrada: {name}")
        return True

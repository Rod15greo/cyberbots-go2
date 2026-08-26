"""
Publisher WebRTC para o servidor de sinalização EC2.
Adaptado do código da Raspberry Pi para o Go2 EDU.
"""

import asyncio
import fractions
import json
import logging
import time
import base64
import uuid

import aiohttp
import cv2
import numpy as np
from av import VideoFrame
from aioice.candidate import Candidate
from aiortc import (
    MediaPlayer,
    RTCConfiguration,
    RTCIceCandidate,
    RTCIceServer,
    RTCPeerConnection,
    RTCSessionDescription,
    VideoStreamTrack,
)
from config import SERVER_URL, WS_PUBLISHER_URL, TURN_URL, TURN_USER, TURN_PASS

logger = logging.getLogger("webrtc")

VIDEO_CLOCK_RATE = 90000
VIDEO_TIME_BASE  = fractions.Fraction(1, VIDEO_CLOCK_RATE)
VIDEO_FPS        = 15  # camera do Go2 é 15 fps


class FrameTrack(VideoStreamTrack):
    """VideoTrack que entrega frames enviados via push()."""

    def __init__(self):
        super().__init__()
        self._queue: asyncio.Queue[np.ndarray] = asyncio.Queue(maxsize=2)
        self._pts   = 0
        self._start = None

    def push(self, frame_bgr: np.ndarray):
        """Chamado pela thread da câmera — thread-safe via put_nowait."""
        try:
            self._queue.put_nowait(frame_bgr)
        except asyncio.QueueFull:
            pass  # descarta frame se fila cheia (câmera mais rápida que encoder)

    async def recv(self) -> VideoFrame:
        if self._start is None:
            self._start = time.time()

        frame_bgr = await self._queue.get()

        # BGR → YUV420p (formato nativo WebRTC)
        av_frame = VideoFrame.from_ndarray(frame_bgr, format="bgr24")
        av_frame = av_frame.reformat(format="yuv420p")

        pts  = int((time.time() - self._start) * VIDEO_CLOCK_RATE)
        av_frame.pts       = pts
        av_frame.time_base = VIDEO_TIME_BASE
        self._pts = pts
        return av_frame


class WebRTCPublisher:
    def __init__(self, face_engine):
        self._face_engine = face_engine
        self._track = FrameTrack()
        self._pc: RTCPeerConnection | None = None
        self._ws = None
        self._session: aiohttp.ClientSession | None = None
        self._fps_counter = 0
        self._fps_start   = time.time()
        self._current_fps = 0.0

    @property
    def track(self) -> FrameTrack:
        return self._track  # sempre aponta para a track atual da PC vigente

    async def run(self):
        """Loop principal — conecta ao servidor e mantém conexão WebSocket."""
        self._session = aiohttp.ClientSession()
        while True:
            try:
                logger.info(f"Conectando ao servidor: {WS_PUBLISHER_URL}")
                async with self._session.ws_connect(WS_PUBLISHER_URL) as ws:
                    self._ws = ws
                    logger.info("WebSocket publisher conectado")
                    await self._ws_loop(ws)
            except Exception as e:
                logger.error(f"Erro WebSocket: {e} — reconectando em 5s...")
                await asyncio.sleep(5)

    async def _ws_loop(self, ws):
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                await self._handle_message(json.loads(msg.data))
            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                break

    async def _handle_message(self, data: dict):
        msg_type = data.get("type")
        logger.info(f"Mensagem recebida: {msg_type}")

        if msg_type == "subscriber_connected":
            await self._create_peer_connection()

        elif msg_type == "answer":
            if self._pc:
                sdp = data.get("sdp") or data.get("data", {}).get("sdp", "")
                await self._pc.setRemoteDescription(
                    RTCSessionDescription(sdp=sdp, type="answer")
                )
                logger.info("Remote description (answer) configurada")

        elif msg_type == "ice":
            if self._pc:
                cand_str = data.get("candidate", "")
                if not cand_str:
                    return
                # Remove prefixo "candidate:" se presente
                if cand_str.startswith("candidate:"):
                    cand_str = cand_str[len("candidate:"):]
                try:
                    parsed   = Candidate.from_sdp(cand_str)
                    sdp_mid  = data.get("sdpMid", "0") or "0"
                    sdp_idx  = int(data.get("sdpMLineIndex", 0) or 0)
                    ice_cand = RTCIceCandidate(
                        component     = parsed.component,
                        foundation    = parsed.foundation,
                        ip            = parsed.host,
                        port          = parsed.port,
                        priority      = parsed.priority,
                        protocol      = parsed.transport,
                        type          = parsed.type,
                        relatedAddress= getattr(parsed, "related_address", None),
                        relatedPort   = getattr(parsed, "related_port", None),
                        sdpMid        = sdp_mid,
                        sdpMLineIndex = sdp_idx,
                    )
                    await self._pc.addIceCandidate(ice_cand)
                except Exception as e:
                    logger.warning(f"Erro ao adicionar ICE candidate: {e}")

        elif msg_type == "register_face":
            await self._handle_register_face(data)

    async def _create_peer_connection(self):
        if self._pc:
            await self._pc.close()
            self._pc = None
            logger.info("PeerConnection anterior fechada")

        # Cria nova track a cada PC — track fechada pelo PC anterior não pode ser reutilizada
        self._track = FrameTrack()

        ice_servers = [
            RTCIceServer(urls="stun:stun.l.google.com:19302"),
            RTCIceServer(urls=TURN_URL, username=TURN_USER, credential=TURN_PASS),
        ]
        self._pc = RTCPeerConnection(RTCConfiguration(iceServers=ice_servers))
        self._pc.addTrack(self._track)

        @self._pc.on("icecandidate")
        async def on_ice_candidate(candidate):
            if candidate is None:
                return
            logger.debug(f"ICE local: {candidate.candidate[:50]}")
            await self._send_ice(candidate)

        @self._pc.on("iceconnectionstatechange")
        async def on_ice_state():
            state = self._pc.iceConnectionState
            logger.info(f"ICE state: {state}")

        logger.info("Aguardando gathering de ICE candidates...")
        offer = await self._pc.createOffer()
        await self._pc.setLocalDescription(offer)

        # Aguarda gathering completo (todos os candidates incluindo TURN relay)
        while self._pc.iceGatheringState != "complete":
            await asyncio.sleep(0.1)

        try:
            async with self._session.post(
                f"{SERVER_URL}/offer",
                json={"sdp": self._pc.localDescription.sdp, "type": "offer"},
            ) as resp:
                logger.info(f"Offer enviado — status {resp.status}")
        except Exception as e:
            logger.error(f"Erro ao enviar offer: {e}")

    async def _send_ice(self, candidate):
        try:
            async with self._session.post(
                f"{SERVER_URL}/ice",
                json={
                    "candidate":     candidate.candidate,
                    "sdpMid":        candidate.sdpMid,
                    "sdpMLineIndex": candidate.sdpMLineIndex,
                    "from":          "publisher",
                },
            ) as resp:
                pass
        except Exception:
            pass

    async def send_face_match(self, name: str, confidence: float,
                               detection_ms: float, recognition_ms: float):
        """Envia resultado de reconhecimento via WebSocket ao servidor."""
        if self._ws is None or self._ws.closed:
            return
        payload = {
            "type":           "face_match",
            "name":           name,
            "confidence":     round(confidence, 3),
            "detection_ms":   detection_ms,
            "recognition_ms": recognition_ms,
            "fps":            round(self._current_fps, 1),
        }
        try:
            await self._ws.send_str(json.dumps(payload))
        except Exception as e:
            logger.warning(f"Erro ao enviar face_match: {e}")

    async def _handle_register_face(self, data: dict):
        """Processa pedido de cadastro de face vindo do servidor."""
        name     = data.get("name", "")
        req_id   = data.get("req_id", "")
        photo_b64= data.get("photo_b64", "")
        if not (name and req_id and photo_b64):
            return
        try:
            img_bytes = base64.b64decode(photo_b64)
            arr       = np.frombuffer(img_bytes, dtype=np.uint8)
            img_bgr   = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            ok = self._face_engine.register_face(name, img_bgr)
            result = {"type": "register_face_result", "req_id": req_id,
                      "status": "ok" if ok else "error",
                      "name": name}
        except Exception as e:
            result = {"type": "register_face_result", "req_id": req_id,
                      "status": "error", "detail": str(e)}
        if self._ws and not self._ws.closed:
            await self._ws.send_str(json.dumps(result))

    def update_fps(self):
        self._fps_counter += 1
        elapsed = time.time() - self._fps_start
        if elapsed >= 2.0:
            self._current_fps = self._fps_counter / elapsed
            self._fps_counter = 0
            self._fps_start   = time.time()

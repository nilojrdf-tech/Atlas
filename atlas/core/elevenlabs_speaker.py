"""Sintese de voz via API da ElevenLabs (opcional), com lip sync por visemas.

Equivalente a ElevenLabsSpeaker.swift: usa o endpoint ``with-timestamps``
(alinhamento por caractere) para montar uma timeline de visemas; sem
alinhamento, cai para medicao de amplitude; se a API falhar, cai para a
voz local (``Speaker``). Pede o audio em PCM (nao mp3) para tocar direto
com ``sounddevice``, sem depender de um decoder externo.
"""
from __future__ import annotations

import base64
import logging
import threading
import time
import unicodedata
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np
import requests
import sounddevice as sd

from .speaker import Speaker

log = logging.getLogger("atlas.elevenlabs")

OUTPUT_SAMPLE_RATE = 44100
OUTPUT_FORMAT = f"pcm_{OUTPUT_SAMPLE_RATE}"


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _viseme_for_char(ch: str) -> Optional[int]:
    c = _strip_accents(ch).lower()
    if len(c) != 1 or not c.isalpha():
        return None
    if c == "a":
        return 2
    if c in "eiy":
        return 1
    if c in "ouw":
        return 3
    if c in "mbp":
        return 0
    if c in "fv":
        return 4
    return 1


@dataclass
class _MouthEvent:
    time: float
    level: int


def _build_mouth_events(characters: list[str], starts: list[float], ends: list[float]) -> list[_MouthEvent]:
    events: list[_MouthEvent] = []
    last_level = -1
    last_end = 0.0
    for i, ch in enumerate(characters):
        if i >= len(starts) or i >= len(ends):
            break
        level = _viseme_for_char(ch)
        if level is None:
            continue
        if events and starts[i] - last_end > 0.12 and last_level != 0:
            events.append(_MouthEvent(last_end, 0))
            last_level = 0
        if level != last_level:
            events.append(_MouthEvent(starts[i], level))
            last_level = level
        last_end = ends[i]
    events.append(_MouthEvent(last_end, 0))
    return events


class ElevenLabsSpeaker:
    def __init__(self, api_key: str, voice_id: str, model: str, output_device: Optional[int] = None) -> None:
        self.on_mouth_level: Optional[Callable[[int], None]] = None
        self._api_key = api_key
        self._voice_id = voice_id
        self._model = model
        self._output_device = output_device
        self._fallback = Speaker()
        log.info("Voz: ElevenLabs (modelo %s, voice_id %s)", model, voice_id)

    def speak(self, text: str, on_done: Callable[[], None]) -> None:
        threading.Thread(target=self._speak_blocking, args=(text, on_done), daemon=True).start()

    def _speak_blocking(self, text: str, on_done: Callable[[], None]) -> None:
        url = (
            f"https://api.elevenlabs.io/v1/text-to-speech/{self._voice_id}/with-timestamps"
            f"?output_format={OUTPUT_FORMAT}"
        )
        try:
            resp = requests.post(
                url,
                headers={"xi-api-key": self._api_key, "content-type": "application/json"},
                json={"text": text, "model_id": self._model},
                timeout=60,
            )
        except requests.RequestException as exc:
            log.warning("ElevenLabs: %s", exc)
            self._fallback_speak(text, on_done)
            return

        if resp.status_code != 200:
            log.warning("ElevenLabs (HTTP %s): %s", resp.status_code, resp.text[:200])
            self._fallback_speak(text, on_done)
            return

        try:
            payload = resp.json()
            audio_bytes = base64.b64decode(payload["audio_base64"])
        except Exception:
            log.warning("ElevenLabs: resposta sem audio valido.")
            self._fallback_speak(text, on_done)
            return

        alignment = payload.get("normalized_alignment") or payload.get("alignment")
        mouth_events: list[_MouthEvent] = []
        if alignment:
            mouth_events = _build_mouth_events(
                alignment.get("characters", []),
                alignment.get("character_start_times_seconds", []),
                alignment.get("character_end_times_seconds", []),
            )

        pcm = np.frombuffer(audio_bytes, dtype="<i2").astype(np.float32) / 32768.0
        duration = len(pcm) / OUTPUT_SAMPLE_RATE

        stop_event = threading.Event()

        def visemes_worker() -> None:
            idx = 0
            t0 = time.monotonic()
            while not stop_event.is_set():
                now = time.monotonic() - t0
                if now >= duration:
                    break
                while idx < len(mouth_events) and mouth_events[idx].time <= now:
                    if self.on_mouth_level:
                        self.on_mouth_level(mouth_events[idx].level)
                    idx += 1
                time.sleep(1 / 60)

        def amplitude_worker() -> None:
            window = int(OUTPUT_SAMPLE_RATE * 0.03)
            t0 = time.monotonic()
            while not stop_event.is_set():
                now = time.monotonic() - t0
                if now >= duration:
                    break
                pos = int(now * OUTPUT_SAMPLE_RATE)
                chunk = pcm[pos:pos + window]
                level = 0
                if chunk.size:
                    rms = float(np.sqrt(np.mean(chunk ** 2)) + 1e-9)
                    db = 20 * np.log10(rms)
                    if db > -18:
                        level = 2
                    elif db > -32:
                        level = 1
                if self.on_mouth_level:
                    self.on_mouth_level(level)
                time.sleep(1 / 30)

        mouth_thread = threading.Thread(
            target=visemes_worker if mouth_events else amplitude_worker, daemon=True
        )

        def finish() -> None:
            stop_event.set()
            if self.on_mouth_level:
                self.on_mouth_level(0)
            on_done()

        try:
            mouth_thread.start()
            sd.play(pcm, samplerate=OUTPUT_SAMPLE_RATE, device=self._output_device, blocking=True)
        except Exception:
            log.exception("falha ao tocar o audio da ElevenLabs")
            stop_event.set()
            self._fallback_speak(text, on_done)
            return
        finish()

    def _fallback_speak(self, text: str, on_done: Callable[[], None]) -> None:
        log.info("Usando a voz do sistema como fallback.")
        self._fallback.on_mouth_level = self.on_mouth_level
        self._fallback.speak(text, on_done)

    def stop(self) -> None:
        try:
            sd.stop()
        except Exception:
            pass
        self._fallback.stop()

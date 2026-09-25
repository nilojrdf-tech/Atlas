"""Captura do microfone e transcricao continua, 100% local, com Vosk.

Equivalente a SpeechRecognizer.swift (AVAudioEngine + SFSpeechRecognizer
on-device), mas sem o limite de sessao de ~1 minuto do reconhecedor da
Apple — nao e necessario reiniciar a escuta periodicamente.
"""
from __future__ import annotations

import json
import logging
import queue
import threading
from pathlib import Path
from typing import Callable, Optional

import sounddevice as sd
import vosk

vosk.SetLogLevel(-1)  # silencia os logs internos do Kaldi/Vosk

log = logging.getLogger("atlas.speech")

SAMPLE_RATE = 16000
BLOCK_SIZE = 4000  # ~0.25s por bloco


def default_model_dir() -> Path:
    here = Path(__file__).resolve().parent.parent.parent
    candidates = [
        here / "models" / "vosk-model-small-pt-0.3",
        Path(__file__).resolve().parent.parent / "models" / "vosk-model-small-pt-0.3",
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(
        "Modelo Vosk pt-BR nao encontrado. Baixe vosk-model-small-pt-0.3 em "
        "https://alphacephei.com/vosk/models e extraia em models/ na raiz do projeto."
    )


class SpeechRecognizer:
    """Escuta continua do microfone; emite transcricoes parciais via callback."""

    def __init__(self, model_dir: Optional[Path] = None, device: Optional[int] = None) -> None:
        self._model = vosk.Model(str(model_dir or default_model_dir()))
        self.device = device
        self.on_partial: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[Exception], None]] = None
        self.contextual_words: list[str] = []

        self._recognizer: Optional[vosk.KaldiRecognizer] = None
        self._stream: Optional[sd.RawInputStream] = None
        self._audio_q: "queue.Queue[bytes]" = queue.Queue()
        self._worker: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()

    def _make_recognizer(self) -> vosk.KaldiRecognizer:
        if self.contextual_words:
            grammar = json.dumps(self.contextual_words + ["[unk]"], ensure_ascii=False)
            rec = vosk.KaldiRecognizer(self._model, SAMPLE_RATE, grammar)
        else:
            rec = vosk.KaldiRecognizer(self._model, SAMPLE_RATE)
        rec.SetWords(False)
        return rec

    def _audio_callback(self, indata, frames, time_info, status) -> None:
        if status:
            log.debug("status do stream de audio: %s", status)
        self._audio_q.put(bytes(indata))

    def _worker_loop(self) -> None:
        while self._running:
            try:
                data = self._audio_q.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                recognizer = self._recognizer
                if recognizer is None:
                    continue
                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "")
                else:
                    result = json.loads(recognizer.PartialResult())
                    text = result.get("partial", "")
                if text and self.on_partial:
                    self.on_partial(text)
            except Exception as exc:  # nao deixa a thread morrer por um frame ruim
                log.exception("erro processando audio")
                if self.on_error:
                    self.on_error(exc)

    def start_listening(self) -> None:
        self.stop_listening()
        with self._lock:
            self._recognizer = self._make_recognizer()
            self._running = True
            self._audio_q = queue.Queue()
            try:
                self._stream = sd.RawInputStream(
                    samplerate=SAMPLE_RATE,
                    blocksize=BLOCK_SIZE,
                    device=self.device,
                    dtype="int16",
                    channels=1,
                    callback=self._audio_callback,
                )
                self._stream.start()
            except Exception as exc:
                self._running = False
                raise
            self._worker = threading.Thread(target=self._worker_loop, daemon=True)
            self._worker.start()

    def stop_listening(self) -> None:
        with self._lock:
            self._running = False
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
            if self._worker is not None:
                self._worker.join(timeout=1.0)
                self._worker = None
            self._recognizer = None

"""Sintese de voz local com o SAPI5 do Windows (via pyttsx3).

Equivalente a Speaker.swift (AVSpeechSynthesizer): usa o evento de "vai
falar esta palavra" para abrir/fechar a boca do avatar, ja que o SAPI nao
expõe medicao de volume diretamente aqui.
"""
from __future__ import annotations

import logging
import random
import threading
import time
from typing import Callable, Optional, Protocol

import pyttsx3

log = logging.getLogger("atlas.speaker")


class Speaking(Protocol):
    on_mouth_level: Optional[Callable[[int], None]]

    def speak(self, text: str, on_done: Callable[[], None]) -> None: ...

    def stop(self) -> None: ...


def list_system_voices() -> list[tuple[str, str]]:
    """Retorna [(id, nome)] das vozes SAPI instaladas."""
    engine = pyttsx3.init()
    try:
        return [(v.id, v.name) for v in engine.getProperty("voices")]
    finally:
        engine.stop()


def _best_ptbr_voice_id() -> Optional[str]:
    for vid, name in list_system_voices():
        if "pt-br" in vid.lower() or "pt_br" in vid.lower() or "portuguese" in name.lower():
            return vid
    return None


class Speaker:
    def __init__(self, voice_id: Optional[str] = None) -> None:
        self.on_mouth_level: Optional[Callable[[int], None]] = None
        self._voice_id = voice_id or _best_ptbr_voice_id()
        self._stop_flag = threading.Event()
        self._mouth_close_timer: Optional[threading.Timer] = None
        if self._voice_id:
            log.info("Voz do sistema: %s", self._voice_id)
        else:
            log.warning("Nenhuma voz pt-BR instalada no Windows; usando a voz padrao.")

    def _on_started_word(self, name, location, length) -> None:
        if self.on_mouth_level:
            self.on_mouth_level(random.randint(1, 2))
        if self._mouth_close_timer:
            self._mouth_close_timer.cancel()
        self._mouth_close_timer = threading.Timer(0.2, lambda: self.on_mouth_level and self.on_mouth_level(0))
        self._mouth_close_timer.daemon = True
        self._mouth_close_timer.start()

    def speak(self, text: str, on_done: Callable[[], None]) -> None:
        self._stop_flag.clear()

        def run() -> None:
            engine = pyttsx3.init()
            try:
                if self._voice_id:
                    engine.setProperty("voice", self._voice_id)
                engine.connect("started-word", self._on_started_word)
                engine.say(text)
                engine.runAndWait()
            except Exception:
                log.exception("falha na sintese de voz local")
            finally:
                engine.stop()
                if self._mouth_close_timer:
                    self._mouth_close_timer.cancel()
                if self.on_mouth_level:
                    self.on_mouth_level(0)
                on_done()

        threading.Thread(target=run, daemon=True).start()

    def stop(self) -> None:
        # pyttsx3/SAPI nao oferece uma interrupcao limpa entre threads;
        # o efeito pratico de "parar" fica a cargo de quem chama nao usar
        # mais o callback apos isso (o VoiceAssistant ignora respostas
        # tardias de uma fala cancelada).
        self._stop_flag.set()

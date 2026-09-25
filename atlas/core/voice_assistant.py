"""Maquina de estados do Atlas: aguardando wake word -> capturando pergunta
-> pensando -> falando -> volta ao inicio.

Porte direto da logica de VoiceAssistant.swift (Pynkaro), adaptado para
Vosk/local (sem o watchdog de 45s, desnecessario aqui) e para chamar os
callbacks de UI (avatar, bandeja) atraves de funcoes simples — a camada
Qt (main.py) e quem faz a ponte thread-safe para a interface grafica.
"""
from __future__ import annotations

import enum
import logging
import re
import threading
import unicodedata
from typing import Callable, Optional

from . import config
from .gemini_client import AskResult, GeminiClient, GeminiError
from .elevenlabs_speaker import ElevenLabsSpeaker
from .speaker import Speaker
from .speech_recognizer import SpeechRecognizer

log = logging.getLogger("atlas.assistant")

CANCEL_PHRASES = ["esquece", "esqueca", "deixa pra la", "deixa para la", "cancela"]


class Status(enum.Enum):
    STARTING = "starting"
    WAITING = "waiting"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    PAUSED = "paused"

    @property
    def label(self) -> str:
        return {
            Status.STARTING: "Aguardando configuracao...",
            Status.WAITING: "Aguardando a palavra de ativacao",
            Status.LISTENING: "Ouvindo...",
            Status.THINKING: "Pensando...",
            Status.SPEAKING: "Falando...",
            Status.PAUSED: "Escuta pausada",
        }[self]


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.lower().strip()


class _State(enum.Enum):
    WAITING_WAKE_WORD = "waiting_wake_word"
    CAPTURING_QUESTION = "capturing_question"
    THINKING = "thinking"
    SPEAKING = "speaking"


class VoiceAssistant:
    def __init__(self) -> None:
        self.settings = config.load_settings()
        self.wake_word = _normalize(self.settings.wake_word or "atlas")

        self.on_status_change: Optional[Callable[[Status], None]] = None
        self.on_show_avatar: Optional[Callable[[], None]] = None
        self.on_hide_avatar: Optional[Callable[[], None]] = None
        self.on_caption: Optional[Callable[[Optional[str]], None]] = None
        self.on_mouth_level: Optional[Callable[[int], None]] = None
        self.on_sources: Optional[Callable[[list[str]], None]] = None
        self.on_fatal_error: Optional[Callable[[str], None]] = None

        self.recognizer = SpeechRecognizer(device=self.settings.input_device)
        self.gemini = GeminiClient()
        self.speaker = self._make_speaker()
        self.speaker.on_mouth_level = self._emit_mouth

        self._state = _State.WAITING_WAKE_WORD
        self._paused = False
        self._question = ""
        self._last_transcript = ""
        self._silence_timer: Optional[threading.Timer] = None
        self._lock = threading.RLock()

    def _make_speaker(self):
        key = config.get_elevenlabs_key()
        if key:
            return ElevenLabsSpeaker(
                api_key=key,
                voice_id=self.settings.elevenlabs_voice_id,
                model=self.settings.elevenlabs_model,
                output_device=self.settings.output_device,
            )
        return Speaker(voice_id=self.settings.system_voice_id or None)

    def _emit_mouth(self, level: int) -> None:
        if self.on_mouth_level:
            self.on_mouth_level(level)

    def _emit_status(self) -> None:
        if not self.on_status_change:
            return
        if self._paused:
            self.on_status_change(Status.PAUSED)
            return
        mapping = {
            _State.WAITING_WAKE_WORD: Status.WAITING,
            _State.CAPTURING_QUESTION: Status.LISTENING,
            _State.THINKING: Status.THINKING,
            _State.SPEAKING: Status.SPEAKING,
        }
        self.on_status_change(mapping[self._state])

    def _set_state(self, state: _State) -> None:
        self._state = state
        self._emit_status()

    # ---------------------------------------------------------------- ciclo

    def start(self) -> None:
        self.recognizer.on_partial = self._handle_partial
        self.recognizer.on_error = self._on_recognizer_error
        self.recognizer.contextual_words = [self.wake_word]
        self._emit_status()
        self._restart_listening()
        log.info('Aguardando "%s"...', self.wake_word)

    def pause(self) -> None:
        with self._lock:
            if self._paused:
                return
            self._cancel_silence_timer()
            self.recognizer.stop_listening()
            if self.on_hide_avatar:
                self.on_hide_avatar()
            self._question = ""
            self._last_transcript = ""
            self._state = _State.WAITING_WAKE_WORD
            self._paused = True
            self._emit_status()
            log.info("Escuta pausada.")

    def resume(self) -> None:
        with self._lock:
            if not self._paused:
                return
            self._paused = False
            log.info("Escuta retomada.")
            self._restart_listening()
            self._emit_status()

    def ask_now(self) -> None:
        """Equivalente ao botao/atalho: pula direto para 'capturando pergunta'."""
        with self._lock:
            if self._paused or self._state != _State.WAITING_WAKE_WORD:
                return
            self._set_state(_State.CAPTURING_QUESTION)
            self._last_transcript = ""
            self._question = ""
            if self.on_show_avatar:
                self.on_show_avatar()
            self._arm_silence_timer()

    def shutdown(self) -> None:
        self._cancel_silence_timer()
        self.recognizer.stop_listening()
        self.speaker.stop()

    # ---------------------------------------------------------------- escuta

    def _restart_listening(self) -> None:
        if self._paused:
            return
        self._last_transcript = ""
        try:
            self.recognizer.start_listening()
        except Exception as exc:
            log.warning("Falha ao iniciar o audio: %s. Tentando de novo em 2s...", exc)
            threading.Timer(2.0, self._restart_listening).start()

    def _on_recognizer_error(self, exc: Exception) -> None:
        log.warning("Erro no reconhecedor: %s", exc)
        if self.on_fatal_error:
            self.on_fatal_error(str(exc))

    # ------------------------------------------------------------ transcricao

    def _handle_partial(self, raw_text: str) -> None:
        with self._lock:
            if self._paused:
                return
            text = _normalize(raw_text)
            if self._state == _State.WAITING_WAKE_WORD:
                if self.wake_word in text:
                    self._set_state(_State.CAPTURING_QUESTION)
                    log.info("Pode falar...")
                    if self.on_show_avatar:
                        self.on_show_avatar()
                    self._update_question(text)
            elif self._state == _State.CAPTURING_QUESTION:
                self._update_question(text)

    def _update_question(self, transcript: str) -> None:
        if transcript == self._last_transcript:
            return
        self._last_transcript = transcript
        log.info("Ouvido: %s", transcript)

        idx = transcript.rfind(self.wake_word)
        if idx >= 0:
            question = transcript[idx + len(self.wake_word):]
        else:
            question = transcript
        question = question.strip(" ,.!?")
        self._question = question

        if self._is_cancel_request(question):
            self._cancel_capture()
            return

        if self.on_caption:
            self.on_caption(f"Voce: {question}" if question else None)
        self._arm_silence_timer()

    @staticmethod
    def _is_cancel_request(text: str) -> bool:
        normalized = re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()
        return any(normalized == p or normalized.endswith(" " + p) for p in CANCEL_PHRASES)

    def _cancel_capture(self) -> None:
        if self._state != _State.CAPTURING_QUESTION:
            return
        log.info('Cancelado ("esquece"). Voltando a aguardar.')
        self._cancel_silence_timer()
        self.recognizer.stop_listening()
        if self.on_hide_avatar:
            self.on_hide_avatar()
        self._question = ""
        self._last_transcript = ""
        self._set_state(_State.WAITING_WAKE_WORD)
        self._restart_listening()

    def _arm_silence_timer(self) -> None:
        self._cancel_silence_timer()
        interval = (
            self.settings.silence_no_question_s
            if not self._question
            else self.settings.silence_after_question_s
        )
        self._silence_timer = threading.Timer(interval, self._finish_capture)
        self._silence_timer.daemon = True
        self._silence_timer.start()

    def _cancel_silence_timer(self) -> None:
        if self._silence_timer:
            self._silence_timer.cancel()
            self._silence_timer = None

    # --------------------------------------------------------- pergunta/resposta

    def _finish_capture(self) -> None:
        with self._lock:
            if self._state != _State.CAPTURING_QUESTION:
                return
            self.recognizer.stop_listening()
            question = self._question
            self._question = ""
            self._last_transcript = ""

            if not question:
                log.info("Nenhuma pergunta detectada. Voltando a aguardar.")
                if self.on_hide_avatar:
                    self.on_hide_avatar()
                self._set_state(_State.WAITING_WAKE_WORD)
                self._restart_listening()
                return

            self._set_state(_State.THINKING)
            log.info("Pergunta: %s", question)

        threading.Thread(target=self._ask_gemini, args=(question,), daemon=True).start()

    def _ask_gemini(self, question: str) -> None:
        try:
            result = self.gemini.ask(question)
            self._handle_answer(result, None)
        except GeminiError as exc:
            self._handle_answer(None, str(exc))
        except Exception as exc:  # rede, timeout etc.
            log.exception("erro inesperado consultando o Gemini")
            self._handle_answer(None, str(exc))

    def _handle_answer(self, result: Optional[AskResult], error: Optional[str]) -> None:
        if error is not None:
            log.warning("Erro na API: %s", error)
            reply = "Desculpe, nao consegui falar com a inteligencia artificial agora."
            sources: list[str] = []
        else:
            assert result is not None
            reply = result.text
            sources = result.sources

        log.info("Resposta: %s", reply)
        with self._lock:
            self._set_state(_State.SPEAKING)
        if self.on_caption:
            self.on_caption(reply)
        if self.on_sources:
            self.on_sources(sources)

        def done() -> None:
            if self.on_hide_avatar:
                self.on_hide_avatar()
            with self._lock:
                self._set_state(_State.WAITING_WAKE_WORD)
            log.info('Aguardando "%s"...', self.wake_word)
            self._restart_listening()

        self.speaker.speak(reply, done)

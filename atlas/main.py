"""Ponto de entrada do Atlas: assistente de voz com personagem animado.

Fluxo: fica na bandeja do sistema; ao ouvir a palavra de ativacao (ou pelo
menu "Perguntar agora"), o avatar aparece, ouve a pergunta, consulta o
Gemini (com busca no Google quando necessario) e responde em voz alta.
"""
from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from .core import config
from .core.voice_assistant import Status, VoiceAssistant
from .ui.avatar_window import AvatarWindow
from .ui.settings_window import SettingsWindow
from .ui.tray import TrayApp

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("atlas.main")


class AtlasApp:
    def __init__(self) -> None:
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        settings = config.load_settings()
        self.avatar = AvatarWindow(screen_index=settings.avatar_screen_index, scale=settings.avatar_scale)
        self.tray = TrayApp()
        self.assistant: VoiceAssistant | None = None
        self._paused = False

        self.tray.ask_now_requested.connect(self._on_ask_now)
        self.tray.pause_toggle_requested.connect(self._on_pause_toggle)
        self.tray.settings_requested.connect(self._on_settings)
        self.tray.quit_requested.connect(self._on_quit)

    def run(self) -> int:
        if not config.get_gemini_key():
            self._run_onboarding()
        else:
            self._start_assistant()
        return self.app.exec()

    def _run_onboarding(self) -> None:
        dialog = SettingsWindow(is_onboarding=True)
        if dialog.exec() and config.get_gemini_key():
            self._start_assistant()
        else:
            log.warning("Configuracao inicial cancelada; encerrando.")
            sys.exit(0)

    def _start_assistant(self) -> None:
        if self.assistant is not None:
            return
        try:
            self.assistant = VoiceAssistant()
        except FileNotFoundError as exc:
            QMessageBox.critical(None, "Atlas", str(exc))
            sys.exit(1)

        self.assistant.on_status_change = self._on_status_change
        self.assistant.on_show_avatar = self.avatar.show_avatar
        self.assistant.on_hide_avatar = self.avatar.hide_avatar
        self.assistant.on_caption = self.avatar.set_caption
        self.assistant.on_mouth_level = self.avatar.set_mouth
        self.assistant.on_sources = self._on_sources
        self.assistant.on_fatal_error = self._on_fatal_error

        if not self.avatar.has_avatar():
            log.warning("Nenhum avatar.png encontrado; o assistente funciona, mas sem personagem na tela.")

        self.assistant.start()

    def _on_status_change(self, status: Status) -> None:
        self._paused = status == Status.PAUSED
        self.tray.status_signal.emit(status)

    def _on_sources(self, sources: list[str]) -> None:
        if sources:
            log.info("Fontes consultadas: %s", ", ".join(sources))

    def _on_fatal_error(self, message: str) -> None:
        log.error("Erro do reconhecedor de fala: %s", message)

    def _on_ask_now(self) -> None:
        if self.assistant:
            self.assistant.ask_now()

    def _on_pause_toggle(self) -> None:
        if not self.assistant:
            return
        if self._paused:
            self.assistant.resume()
        else:
            self.assistant.pause()

    def _on_settings(self) -> None:
        dialog = SettingsWindow(is_onboarding=False)
        dialog.exec()

    def _on_quit(self) -> None:
        if self.assistant:
            self.assistant.shutdown()
        self.app.quit()


def main() -> int:
    return AtlasApp().run()


if __name__ == "__main__":
    sys.exit(main())

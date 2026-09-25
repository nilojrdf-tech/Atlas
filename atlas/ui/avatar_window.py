"""Janela flutuante do avatar do Atlas: sem borda, transparente, sempre no
topo, ignora cliques (atravessam para a janela de baixo), no canto inferior
direito da tela escolhida. Entrada: sobe com fade; saida: fade.

Equivalente a AvatarWindow.swift (modo sprites do Pynkaro).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import (
    QEasingCurve, QPoint, QPropertyAnimation, QRect, Qt, QTimer, Signal, Slot,
)
from PySide6.QtGui import QFont, QGuiApplication, QPixmap
from PySide6.QtWidgets import QLabel, QWidget

log = logging.getLogger("atlas.avatar")

SCREEN_MARGIN = 24
MAX_SIDE = 260

MOUTH_FILES = {
    0: "avatar.png",
    1: "avatar_mid.png",
    2: "avatar_open.png",
    3: "avatar_round.png",
    4: "avatar_fv.png",
}
# Cadeia de fallback quando um sprite especifico nao existe.
FALLBACK_CHAINS = {
    0: [0],
    1: [1, 2, 0],
    2: [2, 1, 0],
    3: [3, 1, 2, 0],
    4: [4, 1, 2, 0],
}


def _default_assets_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "assets"


class AvatarWindow(QWidget):
    # Sinais permitem chamar a janela com seguranca a partir de outras threads
    # (o VoiceAssistant roda fora da thread da interface).
    show_requested = Signal()
    hide_requested = Signal()
    mouth_requested = Signal(int)
    caption_requested = Signal(str)

    def __init__(self, assets_dir: Optional[Path] = None, screen_index: int = 0, scale: float = 1.0) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self.screen_index = screen_index
        self.scale = scale
        self._sprites: dict[int, QPixmap] = {}
        self._current_level = 0

        assets = assets_dir or _default_assets_dir()
        self._load_sprites(assets)

        self._image_label = QLabel(self)
        self._image_label.setScaledContents(True)

        self._caption = QLabel(self)
        self._caption.setWordWrap(True)
        self._caption.setAlignment(Qt.AlignCenter)
        self._caption.setStyleSheet(
            "background-color: rgba(0,0,0,158); color: white; border-radius: 12px; padding: 8px 14px;"
        )
        font = QFont()
        font.setPointSize(11)
        font.setWeight(QFont.Medium)
        self._caption.setFont(font)
        self._caption.hide()

        self._fade = QPropertyAnimation(self, b"windowOpacity")
        self._fade.setDuration(400)

        self.show_requested.connect(self._do_show)
        self.hide_requested.connect(self._do_hide)
        self.mouth_requested.connect(self._do_set_mouth)
        self.caption_requested.connect(self._do_set_caption)

        self._layout_geometry()
        self.setWindowOpacity(0.0)

    # ------------------------------------------------------------- sprites

    def _load_sprites(self, assets_dir: Path) -> None:
        for level, filename in MOUTH_FILES.items():
            path = assets_dir / filename
            if path.exists():
                pix = QPixmap(str(path))
                if not pix.isNull():
                    self._sprites[level] = pix
        if 0 not in self._sprites:
            log.warning("avatar.png nao encontrado em %s; avatar nao sera exibido.", assets_dir)

    def has_avatar(self) -> bool:
        return 0 in self._sprites

    # ------------------------------------------------------------ geometria

    def _target_screen(self):
        screens = QGuiApplication.screens()
        if 0 <= self.screen_index < len(screens):
            return screens[self.screen_index]
        return QGuiApplication.primaryScreen()

    def _layout_geometry(self) -> None:
        if not self._sprites:
            return
        base = self._sprites.get(0) or next(iter(self._sprites.values()))
        side = MAX_SIDE * self.scale
        w = side
        h = side * base.height() / base.width()

        screen = self._target_screen()
        geo: QRect = screen.geometry()
        x = geo.right() - int(w) - SCREEN_MARGIN
        y = geo.bottom() - int(h) - SCREEN_MARGIN
        self.setGeometry(x, y, int(w), int(h) + 40)

        self._image_label.setGeometry(0, 40, int(w), int(h))
        self._render_current_sprite()

        cap_width = int(w) - 20
        self._caption.setGeometry(10, 0, cap_width, 34)

    def _render_current_sprite(self) -> None:
        chain = FALLBACK_CHAINS.get(self._current_level, [0])
        for level in chain:
            pix = self._sprites.get(level)
            if pix is not None:
                self._image_label.setPixmap(pix)
                return

    # ---------------------------------------------------------- API publica
    # (chamaveis de qualquer thread; internamente emitem sinais Qt, que sao
    # entregues de forma thread-safe na thread da interface.)

    def show_avatar(self) -> None:
        self.show_requested.emit()

    def hide_avatar(self) -> None:
        self.hide_requested.emit()

    def set_mouth(self, level: int) -> None:
        self.mouth_requested.emit(max(0, min(4, level)))

    def set_caption(self, text: Optional[str]) -> None:
        self.caption_requested.emit(text or "")

    # ------------------------------------------------------------- slots Qt

    @Slot()
    def _do_show(self) -> None:
        if not self.has_avatar():
            return
        self._layout_geometry()
        self.show()
        self.raise_()
        self._fade.stop()
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(1.0)
        self._fade.setEasingCurve(QEasingCurve.OutCubic)
        self._fade.setDuration(300)
        self._fade.start()

    @Slot()
    def _do_hide(self) -> None:
        self._fade.stop()
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(0.0)
        self._fade.setDuration(350)

        def on_finished() -> None:
            self.hide()
            self._current_level = 0
            self._render_current_sprite()
            self._caption.hide()
            try:
                self._fade.finished.disconnect(on_finished)
            except Exception:
                pass

        self._fade.finished.connect(on_finished)
        self._fade.start()

    @Slot(int)
    def _do_set_mouth(self, level: int) -> None:
        if level == self._current_level:
            return
        self._current_level = level
        self._render_current_sprite()

    @Slot(str)
    def _do_set_caption(self, text: str) -> None:
        if not text.strip():
            self._caption.hide()
            return
        self._caption.setText(text)
        self._caption.adjustSize()
        w = self.width() - 20
        self._caption.setFixedWidth(w)
        self._caption.setGeometry(10, 4, w, self._caption.heightForWidth(w) + 16)
        self._caption.show()
        self._caption.raise_()

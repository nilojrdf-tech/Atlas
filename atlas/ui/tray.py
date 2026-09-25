"""Icone na bandeja do sistema: reflete o estado do assistente e da acesso
ao menu (perguntar agora, pausar/retomar, configuracoes, sair).

Equivalente ao NSStatusItem do PynkaroApp.swift.
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QObject, QRect, Qt, Signal, Slot
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from ..core.voice_assistant import Status

STATUS_GLYPH = {
    Status.STARTING: "…",
    Status.WAITING: "◎",
    Status.LISTENING: "🎙",
    Status.THINKING: "…",
    Status.SPEAKING: "🔊",
    Status.PAUSED: "⏸",
}

STATUS_COLOR = {
    Status.STARTING: "#8a8a8a",
    Status.WAITING: "#3b82f6",
    Status.LISTENING: "#22c55e",
    Status.THINKING: "#f59e0b",
    Status.SPEAKING: "#06b6d4",
    Status.PAUSED: "#94a3b8",
}


def _make_icon(status: Status) -> QIcon:
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    color = QColor(STATUS_COLOR.get(status, "#3b82f6"))
    painter.setBrush(QBrush(color))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(4, 4, 56, 56)
    painter.setPen(QColor("white"))
    font = QFont()
    font.setPointSize(28)
    painter.setFont(font)
    painter.drawText(QRect(0, 0, 64, 64), Qt.AlignCenter, "A")
    painter.end()
    return QIcon(pix)


class TrayApp(QObject):
    ask_now_requested = Signal()
    pause_toggle_requested = Signal()
    settings_requested = Signal()
    quit_requested = Signal()
    # Emitido de qualquer thread (o VoiceAssistant roda fora da UI); a conexao
    # Qt entrega em fila para a thread da bandeja automaticamente.
    status_signal = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.tray = QSystemTrayIcon(_make_icon(Status.STARTING))
        self.tray.setToolTip("Atlas — " + Status.STARTING.label)
        self.status_signal.connect(self.set_status)

        self.menu = QMenu()
        self.status_action = self.menu.addAction(Status.STARTING.label)
        self.status_action.setEnabled(False)
        self.menu.addSeparator()

        self.ask_action = self.menu.addAction("Perguntar agora")
        self.ask_action.triggered.connect(self.ask_now_requested.emit)

        self.pause_action = self.menu.addAction("Pausar escuta")
        self.pause_action.triggered.connect(self.pause_toggle_requested.emit)

        self.menu.addSeparator()
        settings_action = self.menu.addAction("Configuracoes...")
        settings_action.triggered.connect(self.settings_requested.emit)

        self.menu.addSeparator()
        quit_action = self.menu.addAction("Sair do Atlas")
        quit_action.triggered.connect(self.quit_requested.emit)

        self.tray.setContextMenu(self.menu)
        self.tray.show()

    @Slot(object)
    def set_status(self, status: Status) -> None:
        self.tray.setIcon(_make_icon(status))
        self.tray.setToolTip("Atlas — " + status.label)
        self.status_action.setText(status.label)
        self.pause_action.setText("Retomar escuta" if status == Status.PAUSED else "Pausar escuta")

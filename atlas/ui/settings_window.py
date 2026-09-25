"""Janela de Configuracoes / onboarding do Atlas.

Equivalente a SettingsView (SwiftUI) do Pynkaro: chaves de API (gravadas
no Gerenciador de Credenciais do Windows via core.config), wake word,
dispositivos de microfone/saida, tela do avatar e inicializacao com o
Windows.
"""
from __future__ import annotations

from typing import Callable, Optional

import sounddevice as sd
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout,
)

from ..core import config
from ..core.speaker import list_system_voices
from ..platform_ import autostart


class SettingsWindow(QDialog):
    def __init__(self, is_onboarding: bool = False, on_saved: Optional[Callable[[], None]] = None) -> None:
        super().__init__()
        self.is_onboarding = is_onboarding
        self.on_saved = on_saved
        self.settings = config.load_settings()

        self.setWindowTitle("Bem-vindo ao Atlas" if is_onboarding else "Configuracoes do Atlas")
        self.setMinimumWidth(460)

        root = QVBoxLayout(self)

        if is_onboarding:
            intro = QLabel(
                "Bem-vindo ao Atlas! Para comecar, informe sua chave da API do Gemini.\n"
                "Ela fica guardada com seguranca no Gerenciador de Credenciais do Windows "
                "e nunca sai do seu computador (so o texto das perguntas vai para a API)."
            )
            intro.setWordWrap(True)
            root.addWidget(intro)

        # --- Chaves de API -------------------------------------------------
        keys_box = QGroupBox("Chaves de API")
        keys_form = QFormLayout(keys_box)

        self.gemini_key_edit = QLineEdit(config.get_gemini_key() or "")
        self.gemini_key_edit.setPlaceholderText("AIza...")
        self.gemini_key_edit.setEchoMode(QLineEdit.Password)
        keys_form.addRow("Gemini (obrigatoria):", self.gemini_key_edit)
        gemini_link = QLabel('<a href="https://aistudio.google.com/apikey">Criar chave em aistudio.google.com</a>')
        gemini_link.setOpenExternalLinks(True)
        keys_form.addRow("", gemini_link)

        self.elevenlabs_key_edit = QLineEdit(config.get_elevenlabs_key() or "")
        self.elevenlabs_key_edit.setPlaceholderText("Opcional — sem ela, usa a voz do Windows")
        self.elevenlabs_key_edit.setEchoMode(QLineEdit.Password)
        keys_form.addRow("ElevenLabs (opcional):", self.elevenlabs_key_edit)
        eleven_link = QLabel('<a href="https://elevenlabs.io/app/settings/api-keys">Criar chave em elevenlabs.io</a>')
        eleven_link.setOpenExternalLinks(True)
        keys_form.addRow("", eleven_link)

        root.addWidget(keys_box)

        # --- Assistente ------------------------------------------------
        if not is_onboarding:
            asst_box = QGroupBox("Assistente")
            asst_form = QFormLayout(asst_box)

            self.wake_word_edit = QLineEdit(self.settings.wake_word)
            asst_form.addRow("Palavra de ativacao:", self.wake_word_edit)

            self.model_edit = QLineEdit(self.settings.gemini_model)
            asst_form.addRow("Modelo Gemini:", self.model_edit)

            self.web_search_check = QCheckBox("Buscar na web quando necessario")
            self.web_search_check.setChecked(self.settings.web_search_enabled)
            asst_form.addRow("", self.web_search_check)

            root.addWidget(asst_box)

            # --- Audio ---------------------------------------------------
            audio_box = QGroupBox("Audio")
            audio_form = QFormLayout(audio_box)

            self.input_combo = QComboBox()
            self.input_combo.addItem("Padrao do sistema", None)
            self.output_combo = QComboBox()
            self.output_combo.addItem("Padrao do sistema", None)
            try:
                for idx, dev in enumerate(sd.query_devices()):
                    if dev["max_input_channels"] > 0:
                        self.input_combo.addItem(dev["name"], idx)
                    if dev["max_output_channels"] > 0:
                        self.output_combo.addItem(dev["name"], idx)
            except Exception:
                pass
            self._select_combo_data(self.input_combo, self.settings.input_device)
            self._select_combo_data(self.output_combo, self.settings.output_device)
            audio_form.addRow("Microfone:", self.input_combo)
            audio_form.addRow("Saida de audio:", self.output_combo)

            self.voice_combo = QComboBox()
            self.voice_combo.addItem("Automatica (melhor voz pt-BR)", "")
            try:
                for vid, name in list_system_voices():
                    self.voice_combo.addItem(name, vid)
            except Exception:
                pass
            self._select_combo_data(self.voice_combo, self.settings.system_voice_id or "")
            audio_form.addRow("Voz do Windows:", self.voice_combo)

            root.addWidget(audio_box)

            # --- Avatar ----------------------------------------------------
            avatar_box = QGroupBox("Avatar")
            avatar_form = QFormLayout(avatar_box)

            self.screen_combo = QComboBox()
            for idx, screen in enumerate(QGuiApplication.screens()):
                self.screen_combo.addItem(f"{idx}: {screen.name()}", idx)
            self._select_combo_data(self.screen_combo, self.settings.avatar_screen_index)
            avatar_form.addRow("Tela do avatar:", self.screen_combo)

            self.scale_spin = QDoubleSpinBox()
            self.scale_spin.setRange(0.5, 2.0)
            self.scale_spin.setSingleStep(0.1)
            self.scale_spin.setValue(self.settings.avatar_scale)
            avatar_form.addRow("Tamanho:", self.scale_spin)

            root.addWidget(avatar_box)

            # --- Sistema -----------------------------------------------
            sys_box = QGroupBox("Sistema")
            sys_form = QFormLayout(sys_box)
            self.autostart_check = QCheckBox("Iniciar o Atlas com o Windows")
            self.autostart_check.setChecked(autostart.is_enabled())
            sys_form.addRow("", self.autostart_check)
            root.addWidget(sys_box)

        # --- Botoes ----------------------------------------------------
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        save_btn = QPushButton("Salvar e comecar" if is_onboarding else "Salvar")
        save_btn.clicked.connect(self._save)
        save_btn.setDefault(True)
        buttons.addWidget(save_btn)
        if not is_onboarding:
            cancel_btn = QPushButton("Cancelar")
            cancel_btn.clicked.connect(self.reject)
            buttons.addWidget(cancel_btn)
        root.addLayout(buttons)

    @staticmethod
    def _select_combo_data(combo: QComboBox, data) -> None:
        idx = combo.findData(data)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _save(self) -> None:
        gemini_key = self.gemini_key_edit.text().strip()
        if not gemini_key:
            QMessageBox.warning(self, "Chave obrigatoria", "Informe a chave da API do Gemini para continuar.")
            return
        config.set_gemini_key(gemini_key)
        config.set_elevenlabs_key(self.elevenlabs_key_edit.text().strip())

        if not self.is_onboarding:
            self.settings.wake_word = self.wake_word_edit.text().strip() or "atlas"
            self.settings.gemini_model = self.model_edit.text().strip() or "gemini-3.8-flash"
            self.settings.web_search_enabled = self.web_search_check.isChecked()
            self.settings.input_device = self.input_combo.currentData()
            self.settings.output_device = self.output_combo.currentData()
            self.settings.system_voice_id = self.voice_combo.currentData() or ""
            self.settings.avatar_screen_index = self.screen_combo.currentData() or 0
            self.settings.avatar_scale = self.scale_spin.value()
            config.save_settings(self.settings)
            autostart.set_enabled(self.autostart_check.isChecked())

        self.accept()
        if self.on_saved:
            self.on_saved()

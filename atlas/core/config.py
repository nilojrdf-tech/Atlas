"""Configuracao do Atlas.

Duas categorias de dado, com armazenamento diferente:

- Segredos (chaves de API): Gerenciador de Credenciais do Windows, via
  `keyring`. Nunca gravados em config.json, nunca em log, nunca pedidos
  pelo chat do Claude Code.
- Ajustes (wake word, dispositivos, aparencia, modelo etc.): arquivo JSON
  em ``%APPDATA%\\Atlas\\config.json``.

Ordem de resolucao de uma chave de API (a primeira encontrada vence):
  1. Credential Manager do Windows (onde a janela de Configuracoes grava)
  2. Variavel de ambiente (GEMINI_API_KEY/GOOGLE_API_KEY ou ELEVENLABS_API_KEY)
     — util para desenvolvimento/CI, sem depender da UI.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

try:
    import keyring
except ImportError:  # ambiente sem keyring instalado ainda
    keyring = None  # type: ignore

SERVICE_NAME = "Atlas"
APP_DIR = Path(os.environ.get("APPDATA", Path.home())) / "Atlas"
SETTINGS_PATH = APP_DIR / "config.json"


def _keyring_get(account: str) -> Optional[str]:
    if keyring is None:
        return None
    try:
        return keyring.get_password(SERVICE_NAME, account)
    except Exception:
        return None


def _keyring_set(account: str, value: str) -> bool:
    if keyring is None:
        return False
    try:
        if value:
            keyring.set_password(SERVICE_NAME, account, value)
        else:
            try:
                keyring.delete_password(SERVICE_NAME, account)
            except Exception:
                pass
        return True
    except Exception:
        return False


def get_gemini_key() -> Optional[str]:
    return (
        _keyring_get("gemini_api_key")
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or None
    )


def set_gemini_key(value: str) -> None:
    _keyring_set("gemini_api_key", value.strip())


def get_elevenlabs_key() -> Optional[str]:
    return _keyring_get("elevenlabs_api_key") or os.environ.get("ELEVENLABS_API_KEY") or None


def set_elevenlabs_key(value: str) -> None:
    _keyring_set("elevenlabs_api_key", value.strip())


@dataclass
class Settings:
    wake_word: str = "atlas"
    gemini_model: str = "gemini-3.8-flash"
    web_search_enabled: bool = True
    system_voice_id: str = ""          # id da voz SAPI (vazio = escolha automatica)
    elevenlabs_voice_id: str = "f016iUUEKqhX0trYHH6Q"
    elevenlabs_model: str = "eleven_multilingual_v2"
    input_device: Optional[int] = None   # indice do sounddevice; None = padrao do sistema
    output_device: Optional[int] = None
    avatar_screen_index: int = 0
    avatar_scale: float = 1.0
    avatar_image_dir: str = ""          # vazio = usa atlas/assets embutido
    start_with_windows: bool = False
    silence_after_question_s: float = 1.8
    silence_no_question_s: float = 6.0

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, ensure_ascii=False)


def load_settings() -> Settings:
    if SETTINGS_PATH.exists():
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            base = asdict(Settings())
            base.update({k: v for k, v in data.items() if k in base})
            return Settings(**base)
        except Exception:
            pass
    return Settings()


def save_settings(settings: Settings) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(settings.to_json(), encoding="utf-8")

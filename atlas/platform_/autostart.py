"""Inicializacao com o Windows (opcional, controlada nas configuracoes).

Usa a chave de registro Run do usuario atual — nao precisa de admin, nao
mexe em nada fora do perfil do usuario.
"""
from __future__ import annotations

import sys
import winreg

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "Atlas"


def _executable_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    # Em desenvolvimento (python main.py): reaponta para o pythonw + script.
    import os
    script = os.path.abspath(sys.argv[0])
    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    return f'"{pythonw}" "{script}"'


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
            return True
    except FileNotFoundError:
        return False


def set_enabled(enabled: bool) -> None:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, _executable_command())
        else:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass

"""Ponto de entrada de nivel superior (script, nao modulo de pacote).

Existe separado de atlas/main.py porque o pacote usa imports relativos
(from . import ...), que exigem ser executado como parte do pacote — este
arquivo garante isso tanto em `python run_atlas.py` quanto quando
empacotado pelo PyInstaller (build.ps1).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from atlas.main import main

if __name__ == "__main__":
    sys.exit(main())

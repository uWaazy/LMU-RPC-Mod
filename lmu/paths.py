"""Pasta raiz do projeto (onde ficam assets/, icon.*, preview.png, pyLMUSharedMemory/). Funciona no .exe (PyInstaller) tambem."""
import os
import sys

ROOT = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(relative_path):
    return os.path.join(ROOT, relative_path)

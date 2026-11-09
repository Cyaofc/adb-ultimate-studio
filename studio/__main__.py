"""Entrada de la aplicación."""
import argparse
import logging
from logging.handlers import RotatingFileHandler
import sys

from .store import Store, data_dir


def main():
    parser = argparse.ArgumentParser(description="ADB Ultimate Studio")
    parser.add_argument("--check", action="store_true", help="mostrar las herramientas detectadas")
    args = parser.parse_args()
    if args.check:
        from .commands import Tools
        for name in Tools.names:
            try:
                print(name, Tools().locate(name))
            except ValueError:
                print(name, "no disponible en PATH")
        return 0
    from PySide6.QtWidgets import QApplication
    from .window import Window
    folder = data_dir()
    store = Store(folder / "studio.sqlite3")
    logging.basicConfig(level=logging.INFO, handlers=[
        RotatingFileHandler(folder / "diagnostico.log", maxBytes=1024 * 1024,
                            backupCount=2, encoding="utf-8")])
    app = QApplication([sys.argv[0]])
    app.setApplicationName("ADB Ultimate Studio")
    app.setDesktopFileName("adb-ultimate-studio")
    window = Window(store)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

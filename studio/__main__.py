"""Entrada de la aplicación."""
import argparse
import logging
from logging.handlers import RotatingFileHandler
import sys

from .store import Store, data_dir


def main():
    parser = argparse.ArgumentParser(description="ADB Ultimate Studio")
    parser.add_argument("--check", action="store_true", help="mostrar las herramientas detectadas")
    parser.add_argument("--probe", nargs=3, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.probe:
        import socket

        action, host, raw_port = args.probe
        try:
            port = int(raw_port)
            if action == "dns":
                rows = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
                print("\n".join(sorted({row[4][0] for row in rows})))
            elif action == "tcp":
                with socket.create_connection((host, port), timeout=4) as connection:
                    print("TCP abierto", connection.getpeername())
            else:
                raise ValueError("Tipo de diagnóstico no válido")
            return 0
        except (OSError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
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

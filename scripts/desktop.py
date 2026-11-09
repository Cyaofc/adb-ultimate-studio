"""Instala el lanzador y el icono para el usuario actual."""
import os
from pathlib import Path
import shutil
import sys


def desktop_arg(value):
    if any(ord(char) < 32 for char in value):
        raise ValueError("La ruta contiene caracteres de control")
    escaped = "".join("\\" + char if char in '\\"$`' else char for char in value)
    return '"' + escaped.replace("\\", "\\\\").replace("%", "%%") + '"'


def main():
    project = Path(sys.argv[1])
    data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    icons = data / "icons/hicolor/scalable/apps"
    entries = data / "applications"
    for directory in (icons, entries):
        directory.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(project / "assets/adb-ultimate-studio.svg", icons / "adb-ultimate-studio.svg")
    template = (project / "assets/adb-ultimate-studio.desktop").read_text(encoding="utf-8")
    (entries / "adb-ultimate-studio.desktop").write_text(
        template.replace("@EXEC@", desktop_arg(str(project / "scripts/start.sh"))), encoding="utf-8")


if __name__ == "__main__":
    main()

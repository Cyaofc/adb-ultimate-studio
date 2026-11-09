"""Validadores y flujos reutilizables, independientes de la interfaz."""
from pathlib import Path, PurePosixPath
import hashlib
import ipaddress
import json
import re
import stat
import shutil
import tempfile

import yaml


def token(value):
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.:-]*", value):
        raise ValueError("Identificador no válido")
    return value


def remote(value):
    if not value.startswith("/") or ".." in value.split("/") or any(ord(c) < 32 for c in value):
        raise ValueError("Indica una ruta Android absoluta, sin .. ni caracteres de control")
    return "/" + str(PurePosixPath(value)).lstrip("/")


def endpoint(value):
    host, sep, port = value.rpartition(":")
    if not sep or not port.isascii() or not port.isdecimal() or not 1 <= int(port) <= 65535:
        raise ValueError("Especifica host:puerto o [IPv6]:puerto")
    if host.startswith("[") and host.endswith("]"):
        ipaddress.IPv6Address(host[1:-1])
    elif not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*", host):
        raise ValueError("Host no válido")
    return value


def properties(raw):
    return dict(re.findall(r"^\[([^\]]+)\]: \[(.*)\]$", raw, re.M))


def packages(raw):
    return sorted({line[8:].strip() for line in raw.splitlines() if line.startswith("package:")})


def apk_files(paths):
    files = [Path(path).resolve(strict=True) for path in paths]
    if not files or any(not f.is_file() or f.suffix.lower() != ".apk" or not f.stat().st_size for f in files):
        raise ValueError("Selecciona archivos APK regulares y no vacíos")
    return tuple(map(str, files))


def digest(path, cancel):
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            if cancel.is_set():
                raise InterruptedError("Cancelado")
            sha.update(chunk)
    return sha.hexdigest()


def manifest(folder, cancel):
    data = {}
    for path in sorted(folder.rglob("*")):
        mode = path.lstat().st_mode
        if stat.S_ISREG(mode):
            data[path.relative_to(folder).as_posix()] = digest(path, cancel)
        elif not stat.S_ISDIR(mode):
            raise ValueError(f"Archivo especial o enlace: {path}")
    return data


def verified_backup(folder, cancel):
    metadata = folder / "manifest.json"
    data = folder / "data"
    if not metadata.is_file() or metadata.is_symlink() or data.is_symlink() or not data.is_dir():
        raise ValueError("Estructura de respaldo no válida")
    if metadata.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("Manifiesto demasiado grande")
    saved = json.loads(metadata.read_text(encoding="utf-8"))
    if saved["files"] != manifest(data, cancel):
        raise ValueError("Los archivos no coinciden con el manifiesto")
    return saved


def backup(parent, source, execute, cancel):
    folder = Path(tempfile.mkdtemp(prefix="adb-backup-", dir=parent))
    data = folder / "data"
    data.mkdir()
    complete = False
    try:
        result = execute(data)
        if not result.ok or result.status == "simulated":
            return result
        contents = manifest(data, cancel)
        if cancel.is_set():
            raise InterruptedError("Cancelado")
        (folder / "manifest.json").write_text(
            json.dumps({"source": source, "files": contents}, indent=2), encoding="utf-8")
        complete = True
        return folder
    finally:
        if not complete:
            shutil.rmtree(folder)



def load_macro(path):
    if path.stat().st_size > 64 * 1024:
        raise ValueError("Macro demasiado grande")
    raw = path.read_text(encoding="utf-8")
    steps = yaml.safe_load(raw) if path.suffix.lower() in (".yaml", ".yml") else json.loads(raw)
    return validate_macro(steps)


def validate_macro(steps):
    if not isinstance(steps, list) or not 1 <= len(steps) <= 100:
        raise ValueError("La macro debe contener entre 1 y 100 pasos")
    for step in steps:
        if not isinstance(step, dict) or set(step) - {"action", "args", "pause", "retries", "property", "equals"}:
            raise ValueError("Paso de macro no válido")
        args = step.get("args", [])
        action = step.get("action")
        if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
            raise ValueError("args debe ser una lista de cadenas")
        input_args(action, args)
        if type(step.get("pause", 0)) not in (int, float) or not 0 <= step.get("pause", 0) <= 60:
            raise ValueError("Pausa fuera de rango")
        if type(step.get("retries", 0)) is not int or not 0 <= step.get("retries", 0) <= 3:
            raise ValueError("Reintentos fuera de rango")
        if "property" in step or "equals" in step:
            if not isinstance(step.get("property"), str) or not isinstance(step.get("equals"), str):
                raise ValueError("Una condición requiere property y equals")
            token(step["property"])
    return steps


def input_args(action, args):
    lengths = {"tap": (2,), "swipe": (4, 5), "keyevent": (1,), "text": (1,)}
    if not isinstance(action, str) or action not in lengths or len(args) not in lengths[action]:
        raise ValueError("Acción o cantidad de argumentos no válida")
    if action == "text":
        if not re.fullmatch(r"[A-Za-z0-9 .,_@-]{1,250}", args[0]):
            raise ValueError("input text admite aquí solo texto ASCII básico")
        args = [args[0].replace(" ", "%s")]
    elif any(not re.fullmatch(r"[0-9]{1,6}", a) for a in args):
        raise ValueError("Introduce coordenadas, duración o código de tecla numéricos")
    return ("input", action, *args)


INFO = {
    "Propiedades": ("getprop",),
    "Kernel": ("uname", "-a"),
    "CPU": ("cat", "/proc/cpuinfo"),
    "Carga CPU": ("dumpsys", "cpuinfo"),
    "RAM": ("cat", "/proc/meminfo"),
    "Batería y temperatura": ("dumpsys", "battery"),
    "Estadísticas de batería": ("dumpsys", "batterystats"),
    "Térmico": ("dumpsys", "thermalservice"),
    "Almacenamiento": ("df", "-h"),
    "Procesos": ("ps", "-A"),
    "Servicios": ("service", "list"),
    "Aplicaciones activas": ("dumpsys", "activity", "activities"),
    "Sensores": ("dumpsys", "sensorservice"),
    "Conectividad": ("dumpsys", "connectivity"),
    "Interfaces IP": ("ip", "addr"),
    "Wi-Fi": ("dumpsys", "wifi"),
    "Políticas": ("dumpsys", "device_policy"),
    "Resolución": ("wm", "size"),
    "Densidad": ("wm", "density"),
    "Tiempo de actividad": ("cat", "/proc/uptime"),
    "Identidad shell": ("id",),
    "SELinux": ("getenforce",),
    "Presencia de su": ("command", "-v", "su"),
    "Presencia de Magisk": ("command", "-v", "magisk"),
}

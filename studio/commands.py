"""Construcción de comandos y detección de objetivos."""
from dataclasses import dataclass
from pathlib import Path
import re
import shlex
import shutil


@dataclass(frozen=True)
class Device:
    mode: str
    serial: str
    state: str
    details: str = ""

    @property
    def label(self):
        return f"{self.mode} · {self.serial} · {self.state} {self.details}".strip()


def devices(mode: str, output: str) -> list[Device]:
    result = []
    for line in output.splitlines():
        if not line.strip() or line.startswith(("List of devices", "*", "adb:", "fastboot:")):
            continue
        fields = line.split(None, 2)
        if len(fields) >= 2:
            serial, state = fields[:2]
            details = fields[2] if len(fields) == 3 else ""
            if state == "no" and details.startswith("permissions"):
                state = "no permissions"
            if re.fullmatch(r"[A-Za-z0-9_.:%\[\]-]+", serial):
                result.append(Device(mode, serial, state, details))
    return result


class Tools:
    names = ("adb", "fastboot", "scrcpy", "apkanalyzer", "aapt", "jadx")

    def __init__(self, overrides=None):
        self.overrides = overrides or {}

    def locate(self, name):
        if name not in self.names:
            raise ValueError("Herramienta desconocida")
        path = shutil.which(self.overrides.get(name) or name)
        if not path:
            raise ValueError(f"No se encontró {name}. Configura su ruta en Preferencias.")
        return str(Path(path).resolve())

    def host(self, name, *args):
        return (self.locate(name), *args)

    def target(self, device, *args, states=None):
        if device is None:
            raise ValueError("Selecciona un dispositivo")
        allowed = states or (("device",) if device.mode == "adb" else ("fastboot",))
        if device.state not in allowed:
            raise ValueError(f"Estado incompatible: {device.state}")
        return self.host(device.mode, "-s", device.serial, *args)

    def adb(self, device, *args):
        if device is None or device.mode != "adb":
            raise ValueError("Selecciona un dispositivo ADB")
        return self.target(device, *args)

    def shell(self, device, *args):
        return self.adb(device, "shell", shlex.join(args))

    def fastboot(self, device, *args):
        if device is None or device.mode != "fastboot":
            raise ValueError("Selecciona un dispositivo Fastboot")
        return self.target(device, *args)

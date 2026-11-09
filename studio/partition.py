"""Operaciones Fastboot separadas y con autorización por operación."""
from pathlib import Path
import hashlib
import re
import shlex
import struct
import shutil
import tempfile

from PySide6.QtWidgets import QCheckBox

from .services import digest, token


FORMATS = (
    (b"ANDROID!", "Android boot"),
    (b"VNDRBOOT", "Android vendor boot"),
    (b"\x3a\xff\x26\xed", "Android sparse"),
    (b"AVB0", "Android verified boot metadata"),
)


def image_format(path):
    with path.open("rb") as stream:
        header = stream.read(64)
    return next((name for magic, name in FORMATS if header.startswith(magic)), "desconocido")


def expanded_size(path, kind):
    size = path.stat().st_size
    if kind != "Android sparse":
        return size
    with path.open("rb") as stream:
        header = stream.read(28)
    if len(header) != 28:
        raise ValueError("Cabecera sparse incompleta")
    _, major, _, file_header, chunk_header, block, blocks, chunks, _ = struct.unpack("<IHHHHIIII", header)
    if (major != 1 or file_header < 28 or chunk_header < 12 or not block or block % 4 or
            not blocks or not chunks or file_header + chunks * chunk_header > size):
        raise ValueError("Cabecera sparse no válida")
    return block * blocks


class Partition:
    def partition_page(self):
        layout = self.page("Particiones Fastboot", "Flashear o borrar puede causar pérdida de datos o impedir el arranque. "
                           "Verifica la compatibilidad con la documentación del fabricante.")
        self.partition_enabled = QCheckBox("Habilitar operaciones de partición durante esta sesión")
        layout.addWidget(self.partition_enabled)
        self.buttons(layout, ("Preparar imagen", self.prepare_flash),
                     ("Flashear imagen preparada", self.flash_partition),
                     ("Borrar partición", self.erase_partition))
        self.flash_data = None
        layout.addStretch()

    def partition_target(self):
        if not self.partition_enabled.isChecked():
            raise ValueError("Habilita primero las operaciones de partición")
        device = self.target()
        self.tools.fastboot(device, "getvar", "product")
        return device

    def prepare_flash(self):
        device = self.partition_target()
        partition = self.ask("Partición exacta (incluye el sufijo de slot si corresponde)")
        if not partition:
            return
        token(partition)
        if ":" in partition:
            raise ValueError("El nombre de partición no admite dos puntos")
        path = self.file("Seleccionar imagen")
        if not path:
            return
        path = path.resolve(strict=True)
        def work(task):
            if not path.is_file():
                raise ValueError("La imagen debe ser un archivo regular")
            size = path.stat().st_size
            kind = image_format(path)
            if size < 64 or kind == "desconocido":
                raise ValueError("La imagen es demasiado corta o no tiene una cabecera reconocida")
            return device.serial, partition, path, kind, size, expanded_size(path, kind), digest(path, task.cancel)

        def done(value):
            if isinstance(value, tuple):
                self.flash_data = value
                serial, dest, image, kind, size, expanded, sha = value
                self.append("event", f"Imagen preparada · {serial} · {dest}\n{image}\n"
                                     f"{kind} · {size} bytes locales · {expanded} bytes expandidos · SHA-256 {sha}\n")
        self.flash_data = None
        self.start(work, device, done)

    def partition_confirm(self, serial, operation, partition, detail):
        phrase = f"{operation} {serial} {partition}"
        answer = self.ask(f"{detail}\n\nPuede borrar datos o impedir el arranque.\nEscribe exactamente: {phrase}")
        return answer == phrase

    def flash_partition(self):
        device = self.partition_target()
        if not self.flash_data:
            raise ValueError("Prepara una imagen primero")
        serial, partition, path, kind, size, expanded, sha = self.flash_data
        if serial != device.serial:
            raise ValueError("El serial difiere del usado al preparar la imagen")
        detail = f"{path}\n{kind} · {size} bytes locales · {expanded} bytes expandidos · SHA-256 {sha}"
        if not self.partition_confirm(serial, "FLASH", partition, detail):
            return
        command = self.tools.fastboot(device, "flash", partition)
        query = self.tools.fastboot(device, "getvar", f"partition-size:{partition}")
        def work(task):
            check = task.command(query, timeout=10)
            if check.status in ("timeout", "cancelled"):
                return check
            pattern = rf"partition-size:{re.escape(partition)}:\s*(0x[0-9a-fA-F]+|[0-9]+)"
            found = re.search(pattern, check.stdout + "\n" + check.stderr) if check.ok else None
            if found:
                raw = found[1]
                capacity = int(raw, 16 if raw.startswith("0x") else 10)
                if capacity and expanded > capacity:
                    raise ValueError("El tamaño expandido supera la capacidad informada por Fastboot")
            with tempfile.TemporaryDirectory(prefix="adb-studio-flash-") as folder:
                temp = Path(folder) / "verified.img"
                if shutil.disk_usage(folder).free < size:
                    raise ValueError("Espacio insuficiente para preparar una copia local verificada")
                checksum = hashlib.sha256()
                remaining = size
                with path.open("rb") as source, temp.open("xb") as destination:
                    while remaining:
                        if task.cancel.is_set():
                            raise InterruptedError
                        chunk = source.read(min(1024 * 1024, remaining))
                        if not chunk:
                            raise ValueError("La imagen cambió desde la preparación")
                        checksum.update(chunk)
                        destination.write(chunk)
                        remaining -= len(chunk)
                    if source.read(1) or checksum.hexdigest() != sha:
                        raise ValueError("La imagen cambió desde la preparación")
                return task.command((*command, str(temp)), display=f"{shlex.join((*command, str(path)))} · SHA-256 {sha}",
                                    timeout=900)
        self.start(work, device)

    def erase_partition(self):
        device = self.partition_target()
        partition = self.ask("Partición exacta que se borrará")
        if not partition:
            return
        token(partition)
        if ":" in partition:
            raise ValueError("El nombre de partición no admite dos puntos")
        if self.partition_confirm(device.serial, "ERASE", partition, "Borrado de partición sin archivo de entrada"):
            self.execute(self.tools.fastboot(device, "erase", partition), device, timeout=600)

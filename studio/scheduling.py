"""Programación local de respaldos puntuales durante la sesión de escritorio."""
from datetime import datetime
import time

from PySide6.QtCore import QTimer

from .services import remote


class Scheduling:
    def schedule_backup(self):
        device = self.target()
        source = remote(self.backup_source.text())
        self.tools.adb(device, "get-state")
        parent = self.directory("Destino del respaldo programado")
        if not parent:
            return
        value = self.ask("Fecha y hora local (AAAA-MM-DD HH:MM)", datetime.now().strftime("%Y-%m-%d %H:%M"))
        if not value:
            return
        delay = datetime.strptime(value, "%Y-%m-%d %H:%M").timestamp() - time.time()
        if not 0 < delay <= 7 * 86400:
            raise ValueError("Elige una hora futura dentro de siete días")
        if not self.confirm(f"Respaldar {source} en {parent} a las {value}. "
                            "La aplicación debe seguir abierta y el dispositivo disponible.", device):
            return
        timer = QTimer(self)
        timer.setSingleShot(True)
        job = (timer, device.serial, source, parent, value)
        self.scheduled.append(job)
        timer.timeout.connect(lambda: self.run_scheduled(job))
        timer.start(round(delay * 1000))
        self.append("event", f"Respaldo programado {value} · {device.serial} · {source}\n")

    def run_scheduled(self, job):
        timer, serial, source, parent, value = job
        self.scheduled.remove(job)
        timer.deleteLater()
        device = next((item for index in range(self.selector.count())
                       if (item := self.selector.itemData(index)) and item.mode == "adb"
                       and item.serial == serial and item.state == "device"), None)
        if self.task or not device:
            self.append("event", f"Respaldo programado omitido · {value} · {serial}. "
                                 "Comprueba las tareas activas y la conexión.\n")
            return
        self.guard(lambda: self.start_backup(device, source, parent))

    def pending_backups(self):
        if not self.scheduled:
            raise ValueError("No hay respaldos programados")
        pending = {f"{i}. {job[4]} · {job[1]} · {job[2]}": job
                   for i, job in enumerate(self.scheduled, 1)}
        name = self.choose("Selecciona un respaldo para cancelarlo", pending)
        if name and self.confirm(f"Cancelar {name}"):
            job = pending[name]
            job[0].stop()
            job[0].deleteLater()
            self.scheduled.remove(job)

"""Muestreo periódico y gráfico de memoria disponible y batería."""
import re
import time

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget


def measurement(meminfo, battery):
    fields = dict(re.findall(r"^(MemTotal|MemAvailable):\s+(\d+)\s+kB", meminfo, re.M))
    total = int(fields.get("MemTotal", 0))
    available = fields.get("MemAvailable")
    level = re.search(r"^\s*level:\s*(\d+)\s*$", battery, re.M)
    scale = re.search(r"^\s*scale:\s*(\d+)\s*$", battery, re.M)
    ram = 100 * int(available) / total if available is not None and total else None
    charge = 100 * int(level[1]) / int(scale[1]) if level and scale and int(scale[1]) else None
    return tuple(value if value is not None and 0 <= value <= 100 else None for value in (ram, charge))


class Trend(QWidget):
    def __init__(self):
        super().__init__()
        self.samples = []
        self.setMinimumHeight(180)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = self.rect().adjusted(48, 25, -20, -30)
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.drawText(8, 16, "RAM disponible (azul) · Batería (verde)")
        for tick in (0, 25, 50, 75, 100):
            y = round(area.bottom() - tick * area.height() / 100)
            painter.drawText(6, y + 4, f"{tick}%")
            painter.drawLine(area.left(), y, area.right(), y)
        if not self.samples:
            painter.drawText(area, Qt.AlignmentFlag.AlignCenter, "Sin muestras")
            return
        start, end = self.samples[0][0], self.samples[-1][0]
        painter.drawText(area.left(), area.bottom() + 20, f"{end-start:.0f} s de muestreo")
        for index, color in ((1, "#369afa"), (2, "#38b478")):
            painter.setPen(QPen(QColor(color), 2))
            points = QPolygonF()
            for sample in self.samples:
                value = sample[index]
                if value is None:
                    painter.drawPolyline(points)
                    points.clear()
                    continue
                x = area.left() + (sample[0] - start) * area.width() / max(1, end-start)
                y = area.bottom() - value * area.height() / 100
                point = QPointF(x, y)
                points.append(point)
                painter.drawEllipse(point, 2.5, 2.5)
            painter.drawPolyline(points)


class Monitor:
    def monitor_page(self):
        layout = self.page("Monitor", "Muestreo cada cinco segundos. Los huecos indican métricas no disponibles.")
        self.trend = Trend()
        layout.addWidget(self.trend, 1)
        self.buttons(layout, ("Iniciar muestreo", self.start_monitor),
                     ("Exportar muestras", self.export_samples))

    def export_samples(self):
        if not self.trend.samples:
            raise ValueError("Inicia un muestreo primero")
        start = self.trend.samples[0][0]
        self.report({"serial": self.monitor_serial,
                     "muestras": [{"segundos": seconds-start, "ram_disponible_pct": ram,
                                   "bateria_pct": battery} for seconds, ram, battery in self.trend.samples]})

    def start_monitor(self):
        import json
        device = self.target()
        memory = self.tools.shell(device, "cat", "/proc/meminfo")
        battery = self.tools.shell(device, "dumpsys", "battery")

        def work(task):
            if task.dry:
                return task.command(memory)
            for _ in range(120):
                results = [task.command(cmd, visible=False, audit=False, timeout=4) for cmd in (memory, battery)]
                if task.cancel.is_set():
                    from .runner import Result
                    return Result(-1, status="cancelled")
                if all(not result.ok for result in results):
                    return results[0]
                ram, charge = measurement(*(result.stdout if result.ok else "" for result in results))
                task.output.emit("metric", json.dumps([time.monotonic(), ram, charge]))
                if task.cancel.wait(5):
                    from .runner import Result
                    return Result(-1, status="cancelled")
            return results[0]

        self.start(work, device)
        self.monitor_serial = device.serial
        self.trend.samples.clear()
        self.trend.update()

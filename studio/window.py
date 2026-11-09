"""Navegación, selección de dispositivos y ciclo de vida de tareas."""
from pathlib import Path
import html
import json
import shlex

from PySide6.QtCore import QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QListWidget, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QScrollArea, QSplitter, QStackedWidget, QTabWidget, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt

from .commands import Tools, devices
from .pages import Pages
from .runner import Result
from .tasks import Task
from .theme import apply


class Window(QMainWindow, Pages):
    def __init__(self, store):
        super().__init__()
        self.store = store
        self.tools = Tools(store.get("config", "tools", {}))
        self.task = self.discovery = None
        self.adb_stopped = False
        self.closing = False
        self.sink_filter = None
        self.setWindowTitle("ADB Ultimate Studio")
        self.resize(1130, 780)
        root = QWidget(objectName="workspace")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(14, 14, 14, 10)
        layout.setSpacing(10)
        banner = QFrame(objectName="header")
        header = QHBoxLayout(banner)
        header.setContentsMargins(14, 10, 14, 10)
        layout.addWidget(banner)
        mark = QLabel(">_", objectName="brandMark")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(46, 46)
        header.addWidget(mark)
        branding = QVBoxLayout()
        branding.setSpacing(1)
        branding.addWidget(QLabel("ADB Ultimate Studio", objectName="brand"))
        branding.addWidget(QLabel("Administración y diagnóstico de Android", objectName="muted"))
        header.addLayout(branding)
        header.addStretch(1)
        target = QVBoxLayout()
        target.setSpacing(2)
        target.addWidget(QLabel("DISPOSITIVO OBJETIVO", objectName="eyebrow"))
        self.selector = QComboBox()
        self.selector.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.selector.setMinimumContentsLength(30)
        self.selector.addItem("Selecciona un dispositivo")
        target.addWidget(self.selector)
        header.addLayout(target)
        self.refresh_button = self.button(header, "Actualizar", self.refresh, primary=True)
        split = QSplitter(Qt.Orientation.Vertical)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(7)
        layout.addWidget(split, 1)
        body = QWidget()
        row = QHBoxLayout(body)
        row.setContentsMargins(0, 0, 0, 0)
        rail_card = QFrame(objectName="rail")
        rail_card.setFixedWidth(204)
        rail = QVBoxLayout(rail_card)
        rail.setContentsMargins(10, 12, 10, 8)
        row.addWidget(rail_card)
        rail.addWidget(QLabel("HERRAMIENTAS", objectName="eyebrow"))
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.setPlaceholderText("Buscar funciones")
        rail.addWidget(self.search)
        self.nav = QListWidget(objectName="navigation")
        rail.addWidget(self.nav)
        self.stack = QStackedWidget()
        row.addWidget(self.stack, 1)
        split.addWidget(body)
        tabs = QTabWidget()
        self.tabs = tabs
        self.views = {}
        for key, title in (("stdout", "Salida"), ("stderr", "Errores"), ("event", "Eventos")):
            view = QPlainTextEdit()
            view.setReadOnly(True)
            view.setPlaceholderText({"stdout": "Aquí aparecerá la salida de las herramientas.",
                                     "stderr": "Aquí se mostrarán los mensajes de error.",
                                     "event": "Aquí aparecerá el registro de esta sesión."}[key])
            view.setProperty("console", True)
            view.setMaximumBlockCount(5000)
            tabs.addTab(view, title)
            self.views[key] = view
        split.addWidget(tabs)
        split.setSizes([555, 170])
        bar = QHBoxLayout()
        layout.addLayout(bar)
        self.state = QLabel("Buscando dispositivos…", objectName="status")
        bar.addWidget(self.state, 1)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        bar.addWidget(self.progress)
        self.cancel_button = self.button(bar, "Cancelar tarea", self.cancel_active)
        self.cancel_button.setEnabled(False)
        self.button(bar, "Limpiar consola", lambda: [view.clear() for view in self.views.values()])
        self.button(bar, "Exportar consola", self.export_console)
        self.sections = []
        self.build_pages()
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        self.selector.currentIndexChanged.connect(self.show_target)
        self.search.textChanged.connect(self.search_pages)
        self.apply_theme(store.get("config", "dark", True))
        self.timer = QTimer(self)
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        QTimer.singleShot(0, self.refresh)

    def search_pages(self, query):
        for index, terms in enumerate(self.sections):
            self.nav.item(index).setHidden(query.casefold() not in terms)
        visible = next((i for i in range(len(self.sections)) if not self.nav.item(i).isHidden()), None)
        if visible is not None and self.nav.currentItem().isHidden():
            self.nav.setCurrentRow(visible)

    def page(self, title, description):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget(objectName="panel")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(18, 14, 18, 18)
        layout.setSpacing(9)
        layout.addWidget(QLabel(title, objectName="panelTitle"))
        label = QLabel(description, objectName="muted")
        label.setWordWrap(True)
        layout.addWidget(label)
        scroll.setWidget(content)
        self.stack.addWidget(scroll)
        self.nav.addItem(title)
        self.sections.append((title + " " + description).casefold())
        return layout

    def button(self, layout, label, callback, *, primary=False):
        button = QPushButton(label)
        button.setProperty("primary", primary)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(button)
        button.clicked.connect(lambda: self.guard(callback))
        return button

    def guard(self, callback):
        try:
            callback()
        except (OSError, ValueError, KeyError) as exc:
            QMessageBox.warning(self, "Operación", str(exc))

    def choose(self, title, options):
        choice, accepted = QInputDialog.getItem(self, title, title, list(options), editable=False)
        return choice if accepted else None

    def ask(self, label, default=""):
        value, ok = QInputDialog.getText(self, "ADB Ultimate Studio", label, text=default)
        return value if ok else None

    def directory(self, title):
        name = QFileDialog.getExistingDirectory(self, title)
        return Path(name) if name else None

    def file(self, title, patterns="Todos (*)"):
        name, _ = QFileDialog.getOpenFileName(self, title, filter=patterns)
        return Path(name) if name else None

    def save(self, title, suffix):
        name, _ = QFileDialog.getSaveFileName(self, title, f"informe.{suffix}")
        return Path(name) if name else None

    def report(self, payload):
        kind = self.choose("Formato de informe", ("TXT", "JSON", "HTML"))
        if not kind:
            return
        path = self.save("Exportar informe", kind.lower())
        if path:
            raw = json.dumps(payload, indent=2, ensure_ascii=False)
            if kind == "HTML":
                raw = '<!doctype html><meta charset="utf-8"><title>Informe ADB</title><pre>' + html.escape(raw) + "</pre>"
            path.write_text(raw + "\n", encoding="utf-8")

    def export_console(self):
        self.report({key: view.toPlainText() for key, view in self.views.items()})

    def append(self, channel, data):
        if channel == "metric":
            self.trend.samples.append(json.loads(data))
            self.trend.update()
            return
        if channel == "stdout" and self.sink_filter:
            data = self.sink_filter(data)
        if data:
            view = self.views[channel]
            cursor = view.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(data)
            view.setTextCursor(cursor)
            if view.document().characterCount() > 2_000_000:
                cursor.setPosition(0)
                cursor.setPosition(500_000, QTextCursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()

    def apply_theme(self, dark):
        apply(self, dark)
        self.store.put("config", "dark", dark)

    def refresh(self):
        if self.closing or self.discovery or self.task:
            return
        tools = self.tools
        adb_stopped = self.adb_stopped
        def scan(task):
            found, errors = [], []
            for name in ("adb", "fastboot"):
                if name == "adb" and adb_stopped:
                    continue
                try:
                    result = task.command(tools.host(name, "devices", *(("-l",) if name == "adb" else ())),
                                          timeout=4, visible=False, audit=False)
                    found.extend(devices(name, result.stdout))
                    if not result.ok:
                        errors.append(f"{name}: {result.stderr or result.status}")
                except ValueError as exc:
                    errors.append(str(exc))
            return found, errors

        self.discovery = Task(scan, self.store, "host", self)
        self.discovery.done.connect(self.update_devices)
        self.discovery.finished.connect(self.clear_discovery)
        self.discovery.start()

    def clear_discovery(self):
        self.discovery.deleteLater()
        self.discovery = None

    def update_devices(self, result):
        if isinstance(result, Result):
            self.state.setText(result.stderr or result.status)
            return
        found, errors = result
        self.device_metrics["adb"].setText(str(sum(d.mode == "adb" for d in found)))
        self.device_metrics["fastboot"].setText(str(sum(d.mode == "fastboot" for d in found)))
        current = self.selector.currentData()
        self.selector.blockSignals(True)
        self.selector.clear()
        self.selector.addItem("Selecciona un dispositivo" if found else "Sin dispositivos detectados")
        for index, device in enumerate(found, 1):
            title = f"{device.model or device.mode.upper()} · {device.serial}"
            self.selector.addItem(title, device)
            self.selector.setItemData(index, device.label, Qt.ItemDataRole.ToolTipRole)
            if current and (current.mode, current.serial) == (device.mode, device.serial):
                self.selector.setCurrentIndex(index)
        self.selector.blockSignals(False)
        self.show_target()
        if not self.task:
            count = len(found)
            self.state.setText("1 dispositivo detectado" if count == 1 else f"{count} dispositivos detectados")
            self.state.setToolTip("\n".join(errors))
            if errors and errors != getattr(self, "last_scan_errors", None):
                self.append("event", "\n".join(errors) + "\n")
            self.last_scan_errors = errors

    def confirm(self, description, device=None):
        target = device.label if device else "Equipo local o servidor ADB"
        return QMessageBox.question(self, "Confirmar operación", f"{target}\n\n{description}",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                    QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def execute(self, argv, device=None, *, risk=None, callback=None, timeout=60, display=None, history=None):
        if risk and not self.confirm(risk + "\n\n" + (display or shlex.join(argv)), device):
            return False
        return self.start(lambda task: task.command(argv, timeout=timeout, display=display, history=history),
                          device, callback)

    def start(self, work, device=None, callback=None):
        if self.task:
            raise ValueError("Ya hay una tarea activa. Finalízala o cancélala.")
        self.callback = callback
        self.task = Task(work, self.store, device.serial if device else "host", self)
        self.task.output.connect(self.append)
        self.task.done.connect(self.complete)
        self.task.finished.connect(self.clear_task)
        self.cancel_button.setEnabled(True)
        self.progress.show()
        self.state.setText(f"En ejecución · {self.task.target}")
        self.task.start()
        return True

    def complete(self, result):
        if isinstance(result, Result):
            label = {"finished": "Finalizada" if result.ok else "Error",
                     "cancelled": "Cancelada", "timeout": "Tiempo agotado",
                     "error": "Error"}[result.status]
            if not result.ok and result.status not in ("cancelled",):
                self.tabs.setCurrentWidget(self.views["stderr"] if result.stderr else self.views["event"])
            if not result.ok and result.stderr:
                self.append("event", result.stderr[-3000:] + "\n")
            self.append("event", f"{label} · código {result.code} · {result.duration:.2f} s\n")
        else:
            label = "Finalizada"
        self.state.setText(label)
        self.statusBar().showMessage(label, 5000)
        if self.callback:
            self.guard(lambda: self.callback(result))
        self.sink_filter = None

    def clear_task(self):
        self.task.deleteLater()
        self.task = None
        self.cancel_button.setEnabled(False)
        self.progress.hide()

    def cancel_active(self):
        if self.task:
            self.task.cancel.set()

    def closeEvent(self, event):
        for task in (self.task, self.discovery):
            if task:
                task.cancel.set()
                if not task.wait(2000):
                    event.ignore()
                    return
        self.closing = True
        self.timer.stop()
        event.accept()

    def target(self):
        return self.selector.currentData()

    def shell(self, *args, **options):
        device = self.target()
        return self.execute(self.tools.shell(device, *args), device, **options)

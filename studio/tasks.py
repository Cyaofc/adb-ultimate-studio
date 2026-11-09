"""Puente entre trabajos de fondo y señales de Qt."""
from threading import Event
import logging
import shlex

from PySide6.QtCore import QThread, Signal

from .runner import Result, run


class Task(QThread):
    output = Signal(str, str)
    done = Signal(object)

    def __init__(self, work, store, target, dry, parent=None):
        super().__init__(parent)
        self.work = work
        self.store = store
        self.target = target
        self.dry = dry
        self.cancel = Event()

    def command(self, argv, *, visible=True, audit=True, display=None, **kwargs):
        label = display or shlex.join(argv)
        if audit:
            self.output.emit("event", f"$ {label}\n")
        emit = self.output.emit if visible else lambda *_: None
        result = run(argv, self.cancel, emit, dry=self.dry, **kwargs)
        if audit:
            self.store.record(self.target, label, result)
        return result

    def run(self):
        try:
            self.done.emit(self.work(self))
        except InterruptedError:
            self.done.emit(Result(-1, status="cancelled"))
        except Exception as exc:
            logging.exception("Fallo de tarea")
            self.done.emit(Result(-1, stderr=str(exc), status="error"))

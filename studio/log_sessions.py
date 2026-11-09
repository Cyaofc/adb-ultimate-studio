"""Sesiones Logcat guardadas como texto local."""
from difflib import unified_diff

from .runner import Result


def compare_logs(left, right):
    for path in (left, right):
        if not path.is_file() or path.stat().st_size > 2_000_000:
            raise ValueError("Selecciona archivos de texto regulares de hasta 2 MB")
    before = left.read_text(encoding="utf-8").splitlines(keepends=True)
    after = right.read_text(encoding="utf-8").splitlines(keepends=True)
    return unified_diff(before, after, fromfile=left.name, tofile=right.name)


class LogSessions:
    def save_log(self):
        data = getattr(self, "log_session", [])
        if not data:
            raise ValueError("Todavía no hay líneas Logcat capturadas")
        path = self.save("Guardar sesión Logcat filtrada", "txt")
        if path:
            path.write_text("".join(data), encoding="utf-8")

    def compare_log_sessions(self):
        left = self.file("Registro de referencia", "Texto (*.txt *.log);;Todos (*)")
        right = self.file("Registro actual", "Texto (*.txt *.log);;Todos (*)") if left else None
        if not right:
            return
        def work(task):
            lines = []
            for index, line in enumerate(compare_logs(left, right)):
                if task.cancel.is_set():
                    return Result(-1, status="cancelled")
                if index == 4500:
                    lines.append("\n[Comparación truncada a 4500 líneas]\n")
                    break
                lines.append(line)
            task.output.emit("stdout", "".join(lines) if lines else "Los archivos son iguales.\n")
            return Result(0)
        self.start(work)

"""Pantalla, macros, respaldos, Fastboot y configuración."""
from pathlib import Path
import json
import os
import shlex
import tempfile
import uuid

from .services import (
    backup, digest, input_args, load_macro, remote, token, verified_backup,
)
from .runner import Result
from .partition import image_format
from .profiles import Profiles
from .scheduling import Scheduling


class Advanced(Scheduling, Profiles):
    def screen_page(self):
        layout = self.page("Pantalla y macros", "Capturas, grabación, scrcpy, toques, gestos, teclas y secuencias JSON/YAML.")
        self.buttons(layout, ("Captura PNG", self.screenshot), ("Grabar pantalla", self.record_screen),
                     ("Abrir scrcpy", self.scrcpy))
        self.buttons(layout, ("Enviar entrada", self.send_input), ("Importar macro", self.import_macro),
                     ("Macros guardadas", self.macro_profile), ("Exportar ejemplo", self.macro_example))
        layout.addStretch()

    def binary_capture(self, path, argv, device, *, timeout, prefix):
        def work(task):
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
                temp = Path(stream.name)
                try:
                    result = task.command(argv, sink=stream, timeout=timeout)
                    stream.flush()
                    with temp.open("rb") as source:
                        header = source.read(16)
                    if result.ok:
                        if not prefix(header):
                            raise ValueError("La salida no contiene el formato esperado")
                        os.replace(temp, path)
                    return result
                finally:
                    temp.unlink(missing_ok=True)
        self.start(work, device)

    def screenshot(self):
        device = self.target()
        argv = self.tools.adb(device, "exec-out", "screencap", "-p")
        path = self.save("Guardar captura", "png")
        if path:
            self.binary_capture(path, argv, device, timeout=30,
                                prefix=lambda header: header.startswith(b"\x89PNG\r\n\x1a\n"))

    def record_screen(self):
        device = self.target()
        self.tools.adb(device, "get-state")
        path = self.save("Guardar vídeo H.264", "h264")
        if not path:
            return
        seconds = self.ask("Duración en segundos (1 a 180)", "15")
        if seconds is None:
            return
        if not seconds.isascii() or not seconds.isdecimal() or not 1 <= int(seconds) <= 180:
            raise ValueError("Duración fuera de rango")
        argv = self.tools.adb(device, "exec-out", "screenrecord", "--output-format=h264",
                              "--time-limit", seconds, "-")
        self.binary_capture(path, argv, device, timeout=int(seconds)+30,
                            prefix=lambda header: header.startswith((b"\x00\x00\x01", b"\x00\x00\x00\x01")))

    def scrcpy(self):
        device = self.target()
        self.tools.adb(device, "get-state")
        size = self.ask("Tamaño máximo de vídeo opcional, en píxeles")
        if size is None:
            return
        if size and (not size.isascii() or not size.isdecimal() or not 128 <= int(size) <= 8192):
            raise ValueError("Tamaño fuera de rango")
        cmd = self.tools.host("scrcpy", "-s", device.serial, *(("-m", size) if size else ()))
        self.execute(cmd, device, timeout=None)

    def send_input(self):
        action = self.choose("Tipo de entrada", ("tap", "swipe", "keyevent", "text"))
        if not action:
            return
        examples = {"tap": "120 350", "swipe": "120 350 120 700 500", "keyevent": "4", "text": "Hola"}
        value = self.ask("Argumentos", examples[action])
        if value is not None:
            args = [value] if action == "text" else value.split()
            self.shell(*input_args(action, args), risk="Enviar entrada a la pantalla activa.",
                       history="adb shell input text [texto privado]" if action == "text" else None)

    def macro_example(self):
        path = self.save("Guardar ejemplo JSON", "json")
        if path:
            path.write_text(json.dumps([{"action": "keyevent", "args": ["4"], "pause": 1,
                                         "retries": 0}], indent=2), encoding="utf-8")

    def import_macro(self):
        path = self.file("Importar macro", "Macros (*.json *.yaml *.yml)")
        if path:
            steps = load_macro(path)
            name = self.ask("Guardar macro con el nombre", path.stem)
            if name:
                self.store.put("macro", name, steps)

    def macro_profile(self):
        macros = self.store.list("macro")
        if not macros:
            raise ValueError("Importa una macro primero")
        name = self.choose("Seleccionar macro", macros)
        if not name:
            return
        action = self.choose("Acción", ("Ejecutar", "Ejecutar un paso", "Exportar JSON", "Eliminar perfil"))
        if action == "Exportar JSON":
            path = self.save("Guardar macro", "json")
            if path:
                path.write_text(json.dumps(macros[name], indent=2, ensure_ascii=False), encoding="utf-8")
        elif action == "Eliminar perfil" and self.confirm(f"Eliminar perfil {name}"):
            self.store.delete("macro", name)
        elif action in ("Ejecutar", "Ejecutar un paso"):
            steps = macros[name]
            if action == "Ejecutar un paso":
                number = self.choose("Número de paso", [str(i) for i in range(1, len(steps)+1)])
                if not number:
                    return
                steps = [steps[int(number)-1]]
            self.execute_macro(name, steps)

    def execute_macro(self, name, steps):
        from .services import validate_macro
        device = self.target()
        steps = validate_macro(steps)
        plan = [(step, self.tools.shell(device, *input_args(step["action"], step.get("args", []))))
                for step in steps]
        if not self.confirm(f"Ejecutar {name}\n\n" + "\n".join(shlex.join(cmd) for _, cmd in plan), device):
            return

        def work(task):
            result = Result(0)
            for index, (step, cmd) in enumerate(plan, 1):
                task.output.emit("event", f"Paso {index}/{len(plan)}\n")
                if task.cancel.is_set():
                    return Result(-1, status="cancelled")
                if "property" in step:
                    check = task.command(self.tools.shell(device, "getprop", step["property"]), visible=False)
                    if not check.ok:
                        return check
                    if check.stdout.strip() != step["equals"]:
                        task.output.emit("event", "Paso omitido por condición\n")
                        continue
                for attempt in range(step.get("retries", 0) + 1):
                    history = "adb shell input text [texto privado]" if step["action"] == "text" else None
                    result = task.command(cmd, history=history)
                    if result.ok or result.status == "cancelled":
                        break
                if not result.ok:
                    return result
                if task.cancel.wait(step.get("pause", 0)):
                    return Result(-1, status="cancelled")
            return result
        self.start(work, device)

    def backup_page(self):
        layout = self.page("Respaldos", "Respaldos de rutas accesibles con manifiesto SHA-256. "
                           "Los datos privados requieren permisos del dispositivo y pueden quedar fuera.")
        self.backup_source = self.field(layout, "Ruta Android", "/sdcard/DCIM")
        self.buttons(layout, ("Respaldar ruta", self.create_backup), ("Verificar respaldo", self.verify_backup),
                     ("Restaurar archivos", self.restore_backup), ("Comparar respaldos", self.compare_backups))
        self.scheduled = []
        self.buttons(layout, ("Programar respaldo", self.schedule_backup),
                     ("Ver / cancelar programación", self.pending_backups))
        layout.addStretch()

    def create_backup(self):
        source = remote(self.backup_source.text())
        device = self.target()
        self.tools.adb(device, "get-state")
        parent = self.directory("Destino del respaldo")
        if not parent or not self.confirm(f"Respaldar {source} en {parent}", device):
            return
        self.start_backup(device, source, parent)

    def start_backup(self, device, source, parent):
        cmd = self.tools.adb(device, "pull", source)
        def work(task):
            return backup(parent, source, lambda data: task.command(
                (*cmd, str(data)), timeout=1800), task.cancel)
        def done(folder):
            if isinstance(folder, Path):
                self.store.put("backup", str(folder), {"serial": device.serial, "source": source})
                self.append("event", f"Respaldo verificado al crear: {folder}\n")
        self.start(work, device, done)

    def verify_backup(self):
        folder = self.directory("Selecciona la carpeta adb-backup-*")
        if folder:
            self.start(lambda task: verified_backup(folder, task.cancel),
                       callback=lambda value: self.report(value) if isinstance(value, dict) else None)

    def compare_backups(self):
        left = self.directory("Respaldo de referencia")
        right = self.directory("Respaldo actual") if left else None
        if not right:
            return
        def work(task):
            old = verified_backup(left, task.cancel)["files"]
            new = verified_backup(right, task.cancel)["files"]
            return {"añadidos": sorted(new.keys()-old.keys()), "retirados": sorted(old.keys()-new.keys()),
                    "modificados": sorted(key for key in old.keys() & new.keys() if old[key] != new[key])}
        self.start(work, callback=lambda value: self.report(value) if isinstance(value, dict) else None)

    def restore_backup(self):
        folder = self.directory("Selecciona el respaldo")
        if not folder:
            return
        dest = self.ask("Directorio Android existente donde se copiará el contenido")
        if not dest:
            return
        dest = remote(dest)
        device = self.target()
        cmd = self.tools.adb(device, "push")
        if not self.confirm(f"Copiar {folder}/data a {dest}. Puede sobrescribir archivos.", device):
            return
        check = self.tools.shell(device, "test", "-d", dest)
        def work(task):
            verified_backup(folder, task.cancel)
            result = task.command(check)
            if not result.ok:
                return result
            contents = sorted(str(path) for path in (folder / "data").iterdir())
            for item in contents:
                result = task.command((*cmd, item, dest.rstrip("/") + "/"), timeout=1800)
                if not result.ok:
                    return result
            return result
        self.start(work, device)

    def fastboot_page(self):
        layout = self.page("Fastboot", "Selecciona un objetivo Fastboot. Consulta variables y prepara manifiestos de imágenes. "
                           "La compatibilidad depende del bootloader y de si estás en fastbootd.")
        self.buttons(layout, ("Consultar variable", self.fastboot_var), ("Reiniciar", self.fastboot_reboot),
                     ("Manifiesto de imagen", self.image_manifest))
        layout.addStretch()

    def fastboot_var(self):
        variable = self.ask("Variable (product, unlocked, current-slot, slot-count, is-userspace, partition-size:boot)", "product")
        if variable:
            device = self.target()
            self.execute(self.tools.fastboot(device, "getvar", token(variable)), device)

    def fastboot_reboot(self):
        target = self.choose("Destino Fastboot", ("Sistema", "Recovery", "Bootloader"))
        if target:
            device = self.target()
            args = {"Sistema": ("reboot",), "Recovery": ("reboot", "recovery"),
                    "Bootloader": ("reboot-bootloader",)}[target]
            self.execute(self.tools.fastboot(device, *args), device, risk=f"Reiniciar a {target} interrumpe la sesión.")

    def image_manifest(self):
        path = self.file("Seleccionar imagen", "Imágenes (*.img);;Todos (*)")
        if not path:
            return
        def work(task):
            if not path.is_file() or path.stat().st_size == 0:
                raise ValueError("La imagen debe ser un archivo regular no vacío")
            kind = image_format(path)
            return {"archivo": str(path), "bytes": path.stat().st_size, "cabecera": kind,
                    "sha256": digest(path, task.cancel)}
        self.start(work, callback=lambda value: self.report(value) if isinstance(value, dict) else None)

    def settings_page(self):
        layout = self.page("Ajustes Android", "Consulta los espacios system, secure y global. "
                           "La edición guiada se limita a ajustes de pantalla del espacio system.")
        self.buttons(layout, ("Listar espacio", self.list_settings), ("Leer ajuste", self.read_setting),
                     ("Cambiar ajuste permitido", self.change_setting), ("Restaurar cambio registrado", self.undo_setting))
        self.buttons(layout, ("Perfiles de ajustes", self.settings_profile))
        layout.addStretch()

    def list_settings(self):
        namespace = self.choose("Espacio Android", ("system", "secure", "global"))
        if namespace:
            self.shell("settings", "list", namespace)

    def read_setting(self):
        namespace = self.choose("Espacio Android", ("system", "secure", "global"))
        if namespace:
            key = self.ask("Clave Android")
            if key:
                self.shell("settings", "get", namespace, token(key))

    def change_setting(self):
        limits = {"screen_brightness": (0, 255), "screen_off_timeout": (5000, 1800000),
                  "accelerometer_rotation": (0, 1), "user_rotation": (0, 3)}
        key = self.choose("Ajuste permitido", limits)
        if not key:
            return
        low, high = limits[key]
        value = self.ask(f"Nuevo valor entre {low} y {high}")
        if value is None:
            return
        if not value.isascii() or not value.isdecimal() or len(value) > 8 or not low <= int(value) <= high:
            raise ValueError("Valor fuera de rango")
        value = str(int(value))
        device = self.target()
        query = self.tools.shell(device, "settings", "list", "system")
        write = self.tools.shell(device, "settings", "put", "system", key, value)
        if not self.confirm(f"Modificar system/{key} a {value}", device):
            return
        def work(task):
            result, before = self.setting_state(task, query, key)
            if not result.ok:
                return result
            task.output.emit("event", f"Valor anterior: {before!r}\n")
            change = str(uuid.uuid4())
            record = {"serial": device.serial, "key": key, "before": before,
                      "after": value, "verified": False}
            self.store.put("settings", change, record)
            result = task.command(write)
            if not result.ok:
                return result
            result, after = self.setting_state(task, query, key)
            if result.ok and after == value:
                record["verified"] = True
                self.store.put("settings", change, record)
            elif result.ok:
                raise ValueError(f"Android devolvió un valor distinto: {after!r}")
            return result
        self.start(work, device)

    @staticmethod
    def setting_state(task, query, key):
        result = task.command(query, visible=False)
        rows = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
        return result, rows.get(key)

    def undo_setting(self):
        device = self.target()
        if not device or device.mode != "adb":
            raise ValueError("Selecciona un dispositivo ADB")
        records = {f"{value['key']} ({value['before']!r} → {value['after']!r}) · {name[:8]}": (name, value)
                   for name, value in self.store.list("settings").items()
                   if value["serial"] == device.serial and value["verified"]}
        if not records:
            raise ValueError("No hay cambios verificados para el dispositivo")
        selected = self.choose("Cambio a restaurar", records)
        if not selected:
            return
        name, record = records[selected]
        key, before = record["key"], record["before"]
        query = self.tools.shell(device, "settings", "list", "system")
        args = ("delete", "system", key) if before is None else ("put", "system", key, before)
        write = self.tools.shell(device, "settings", *args)
        if not self.confirm(f"Restaurar {selected}", device):
            return
        def work(task):
            result, current = self.setting_state(task, query, key)
            if not result.ok:
                return result
            if current != record["after"]:
                raise ValueError("El ajuste cambió desde la última escritura registrada")
            result = task.command(write)
            if not result.ok:
                return result
            result, current = self.setting_state(task, query, key)
            if result.ok and current == before:
                self.store.delete("settings", name)
            elif result.ok:
                raise ValueError("Android no confirmó el valor anterior")
            return result
        self.start(work, device)

    def tools_page(self):
        layout = self.page("Preferencias", "Configura rutas absolutas, apariencia, paquetes protegidos y preferencias locales.")
        self.buttons(layout, ("Rutas de herramientas", self.override_tool), ("Tema", self.theme_choice),
                     ("Paquetes protegidos", self.protected_packages), ("Copia de preferencias", self.local_preferences))
        layout.addStretch()

    def override_tool(self):
        tool = self.choose("Herramienta", self.tools.names)
        if not tool:
            return
        overrides = dict(self.tools.overrides)
        path = self.ask(f"Ruta absoluta de {tool} (vacío para usar PATH)", overrides.get(tool, ""))
        if path is None:
            return
        if path:
            if not Path(path).is_absolute() or not Path(path).is_file() or not os.access(path, os.X_OK):
                raise ValueError("Indica una ruta absoluta a un archivo ejecutable")
            overrides[tool] = path
        else:
            overrides.pop(tool, None)
        self.store.put("config", "tools", overrides)
        from .commands import Tools
        self.tools = Tools(overrides)
        self.refresh()

    def theme_choice(self):
        choice = self.choose("Tema", ("Oscuro", "Claro"))
        if choice:
            self.apply_theme(choice == "Oscuro")

    def protected_packages(self):
        current = self.store.get("config", "protected", [])
        value = self.ask("Paquetes adicionales separados por espacios", " ".join(current))
        if value is not None:
            self.store.put("config", "protected", sorted({token(item) for item in value.split()}))

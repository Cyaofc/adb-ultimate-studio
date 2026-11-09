"""Paneles de dispositivos, terminal, diagnóstico y administración."""
from pathlib import Path
import json
import os
import re
import shlex

import regex as bounded_regex
from PySide6.QtCore import Qt

from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QPlainTextEdit,
)

from .advanced import Advanced
from .monitor import Monitor
from .plugins import Plugins
from .partition import Partition
from .services import INFO, apk_files, endpoint, packages, properties, remote, token


class Pages(Advanced, Monitor, Plugins, Partition):
    def build_pages(self):
        for build in (self.device_page, self.terminal_page, self.apps_page, self.files_page,
                      self.log_page, self.monitor_page, self.screen_page, self.backup_page, self.fastboot_page, self.partition_page,
                      self.network_page, self.settings_page, self.plugin_page, self.tools_page):
            build()

    def field(self, layout, label, value=""):
        layout.addWidget(QLabel(label))
        widget = QLineEdit(value)
        layout.addWidget(widget)
        return widget

    def buttons(self, layout, *actions):
        row = QHBoxLayout()
        for label, action in actions:
            self.button(row, label, action)
        layout.addLayout(row)

    def output_list(self, layout, callback):
        search = self.field(layout, "Filtrar")
        listing = QListWidget()
        layout.addWidget(listing, 1)
        search.textChanged.connect(lambda value: [
            listing.item(i).setHidden(value.casefold() not in listing.item(i).text().casefold())
            for i in range(listing.count())])
        listing.itemActivated.connect(lambda item: self.guard(lambda: callback(item.text())))
        return listing, search

    def fill(self, listing, search, values):
        listing.clear()
        listing.addItems(values)
        for i in range(listing.count()):
            item = listing.item(i)
            item.setHidden(search.text().casefold() not in item.text().casefold())

    def device_page(self):
        layout = self.page("Dispositivos y sistema", "USB y TCP/IP, batería, CPU, memoria, pantalla, sensores y diagnóstico. "
                           "Para USB, activa la depuración y acepta la clave RSA. Un estado «no permissions» requiere revisar udev.")
        self.summary = QLabel("Selecciona un dispositivo ADB y consulta su ficha.")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.buttons(layout, ("Ficha del dispositivo", self.snapshot),
                     ("Exportar ficha", lambda: self.report(self.snapshot_data()) ),
                     ("Consulta del sistema", self.info))
        self.buttons(layout, ("Versiones", self.versions),
                     ("Servidor ADB", self.server),
                     ("Diagnóstico root", self.root_check))
        layout.addStretch()

    def snapshot_data(self):
        snapshot = getattr(self, "last_snapshot", None)
        if snapshot is None:
            raise ValueError("Genera una ficha primero")
        return snapshot

    def snapshot(self):
        device = self.target()
        commands = {k: self.tools.shell(device, *INFO[k]) for k in
                    ("Propiedades", "Kernel", "RAM", "Batería y temperatura", "Almacenamiento", "Resolución", "Densidad")}
        def work(task):
            results = {}
            for label, cmd in commands.items():
                result = task.command(cmd, visible=False)
                if result.status in ("simulated", "cancelled"):
                    return result
                results[label] = {"code": result.code, "stdout": result.stdout, "stderr": result.stderr}
            return {"serial": device.serial, "consultas": results}
        def complete(data):
            if not isinstance(data, dict):
                return
            self.last_snapshot = data
            props = properties(data["consultas"]["Propiedades"]["stdout"])
            labels = {
                "Fabricante": "ro.product.manufacturer", "Modelo": "ro.product.model",
                "Android": "ro.build.version.release", "API": "ro.build.version.sdk",
                "Codename": "ro.product.device", "Arquitectura": "ro.product.cpu.abi",
                "Compilación": "ro.build.display.id", "Slot": "ro.boot.slot_suffix",
            }
            self.summary.setTextFormat(Qt.TextFormat.PlainText)
            self.summary.setText(device.serial + "\n" + "\n".join(
                f"{label} · {props.get(key) or 'No disponible'}" for label, key in labels.items()))
            for label, result in data["consultas"].items():
                if label != "Propiedades":
                    self.append("stdout", f"\n[{label}]\n{result['stdout']}")
                if result["stderr"]:
                    self.append("stderr", result["stderr"])
        self.start(work, device, complete)

    def info(self):
        name = self.choose("Consulta del sistema", INFO)
        if name:
            self.shell(*INFO[name])

    def versions(self):
        def work(task):
            for name in ("adb", "fastboot", "scrcpy"):
                try:
                    task.command(self.tools.host(name, "--version"))
                except ValueError as exc:
                    task.output.emit("stderr", str(exc) + "\n")
        self.start(work)

    def server(self):
        operation = self.choose("Servidor ADB", ("start-server", "kill-server", "Reiniciar"))
        if not operation:
            return
        actions = ("kill-server", "start-server") if operation == "Reiniciar" else (operation,)
        commands = [self.tools.host("adb", action) for action in actions]
        if self.confirm(f"{operation}. Puede afectar todas las sesiones ADB de este servidor."):
            def work(task):
                for cmd in commands:
                    result = task.command(cmd)
                    if not result.ok:
                        break
                return result
            def done(result):
                if result.ok and result.status == "finished":
                    self.adb_stopped = operation == "kill-server"
                    if self.adb_stopped:
                        self.selector.clear()
                        self.selector.addItem("Selecciona un dispositivo")
            self.start(work, callback=done)

    def root_check(self):
        action = self.choose("Diagnóstico root", ("Identidad shell", "SELinux", "Presencia de su",
                             "Presencia de Magisk", "Solicitar su: id", "Consultar Magisk con su",
                             "Listar /data/adb/modules con su"))
        if action in INFO:
            self.shell(*INFO[action])
        elif action:
            command = {"Solicitar su: id": "id", "Consultar Magisk con su": "magisk -v",
                       "Listar /data/adb/modules con su": "ls -la /data/adb/modules"}[action]
            self.shell("su", "-c", command, risk="Solicita acceso root al dispositivo.", timeout=20)

    def terminal_page(self):
        layout = self.page("Terminal ADB", "Shell remoto y sesión persistente por líneas. La consola separa salida, "
                           "errores y eventos. Las órdenes arbitrarias se confirman antes de enviarse.")
        self.terminal = QPlainTextEdit()
        self.terminal.setPlaceholderText("id")
        self.terminal.setMaximumHeight(110)
        layout.addWidget(self.terminal)
        self.buttons(layout, ("Ejecutar una vez", self.shell_once), ("Abrir sesión", self.open_shell),
                     ("Enviar a sesión", self.send_shell), ("Cerrar sesión", self.close_shell))
        self.buttons(layout, ("Biblioteca", self.library), ("Guardar favorito", self.save_shell),
                     ("Cargar favorito", self.load_shell), ("Historial", self.show_history))
        self.session = None
        layout.addStretch()

    def shell_once(self):
        value = self.terminal.toPlainText().strip()
        if not value or "\0" in value:
            raise ValueError("Introduce un comando shell válido")
        device = self.target()
        self.execute(self.tools.adb(device, "shell", value), device,
                     risk="El shell remoto puede modificar o borrar datos.")

    def open_shell(self):
        device = self.target()
        cmd = self.tools.adb(device, "shell", "-T")
        if self.task or self.dry.isChecked():
            raise ValueError("La sesión requiere modo real y una consola libre")
        read_fd, write_fd = os.pipe()
        reader = os.fdopen(read_fd, "rb", buffering=0)
        writer = os.fdopen(write_fd, "wb", buffering=0)
        os.set_blocking(write_fd, False)

        def work(task):
            with reader:
                return task.command(cmd, timeout=None, stdin=reader)

        self.session = (writer, device)
        self.start(work, device, lambda _: self.close_shell())

    def close_shell(self):
        if self.session:
            self.session[0].close()
            self.session = None
            self.cancel_active()

    def send_shell(self):
        if not self.session or not self.task:
            raise ValueError("Abre una sesión primero")
        writer, device = self.session
        line = self.terminal.toPlainText().strip()
        encoded = (line + "\n").encode()
        if not line or "\0" in line or len(encoded) > os.fpathconf(writer.fileno(), "PC_PIPE_BUF"):
            raise ValueError("Comando vacío o demasiado largo")
        if self.confirm(f"Enviar a la sesión activa. Puede modificar datos.\n\n{line}", device):
            writer.write(encoded)
            self.append("event", f"{device.serial} $ {line}\n")

    def library(self):
        name = self.choose("Biblioteca · consultas de lectura", INFO)
        if name:
            self.terminal.setPlainText(shlex.join(INFO[name]))

    def save_shell(self):
        name = self.ask("Nombre del favorito")
        if name:
            self.store.put("shell", name, self.terminal.toPlainText())

    def load_shell(self):
        items = self.store.list("shell")
        if not items:
            raise ValueError("Todavía no hay favoritos")
        name = self.choose("Favoritos shell", items)
        if name:
            self.terminal.setPlainText(items[name])

    def show_history(self):
        query = self.ask("Buscar en el historial (vacío para todo)")
        if query is not None:
            for row in self.store.history(query):
                self.append("stdout", " · ".join(map(str, row)) + "\n")

    def apps_page(self):
        layout = self.page("Aplicaciones APK", "Inventario, APK divididos, metadatos, rutas, permisos y control de paquetes.")
        self.package = self.field(layout, "Identificador de paquete")
        self.app_list, self.app_search = self.output_list(layout, self.package.setText)
        self.buttons(layout, ("Inventario", self.inventory), ("Instalar", self.install_apks),
                     ("Acciones de paquete", self.package_action), ("Extraer APK", self.extract_apks))
        self.buttons(layout, ("Guardar / comparar inventarios", self.inventory_profile),
                     ("Analizar APK local", self.analyze_apk))

    def inventory(self):
        options = {"Todos": (), "Usuario": ("-3",), "Sistema": ("-s",), "Deshabilitados": ("-d",)}
        chosen = self.choose("Inventario de paquetes", options)
        if chosen:
            device = self.target()
            def done(result):
                if result.status == "finished" and result.ok:
                    self.inventory_data = {"serial": device.serial, "tipo": chosen,
                                           "paquetes": packages(result.stdout)}
                    self.fill(self.app_list, self.app_search, self.inventory_data["paquetes"])
            self.shell("pm", "list", "packages", *options[chosen], callback=done)

    def install_apks(self):
        mode = self.choose("Modo de instalación", ("Un APK o lote independiente", "APK divididos de una app"))
        if not mode:
            return
        names, _ = QFileDialog.getOpenFileNames(self, "Seleccionar APK", filter="APK (*.apk *.APK)")
        if not names:
            return
        paths = apk_files(names)
        device = self.target()
        if mode.startswith("APK divididos") and len(paths) < 2:
            raise ValueError("Selecciona APK base y al menos un APK dividido")
        args = [("install-multiple", *paths)] if mode.startswith("APK divididos") else [("install", p) for p in paths]
        cmds = [self.tools.adb(device, *a) for a in args]
        if self.confirm("Instalar los siguientes APK\n" + "\n".join(paths), device):
            def work(task):
                for cmd in cmds:
                    result = task.command(cmd, timeout=300)
                    if not result.ok:
                        break
                return result
            self.start(work, device)

    def package_action(self):
        name = token(self.package.text().strip())
        read = {"Detalles y permisos": ("dumpsys", "package", name), "Rutas APK": ("pm", "path", name)}
        mutate = {
            "Abrir actividad lanzadora": ("monkey", "-p", name, "-c", "android.intent.category.LAUNCHER", "1"),
            "Detener": ("am", "force-stop", name), "Borrar datos": ("pm", "clear", name),
            "Habilitar": ("pm", "enable", name), "Deshabilitar para usuario 0": ("pm", "disable-user", "--user", "0", name),
        }
        action = self.choose("Acción del paquete", (*read, *mutate, "Desinstalar", "Conceder permiso", "Revocar permiso"))
        if action in read:
            self.shell(*read[action])
        elif action:
            device = self.target()
            critical = {"android", "com.android.systemui", "com.android.settings", "com.android.shell",
                        "com.android.permissioncontroller", "com.google.android.permissioncontroller"}
            critical.update(self.store.get("config", "protected", []))
            if name in critical and action in ("Detener", "Borrar datos", "Deshabilitar para usuario 0",
                                               "Desinstalar", "Revocar permiso"):
                raise ValueError(f"Paquete protegido: {name}")
            risk = f"{action} en {name}. Cambiar paquetes del sistema puede afectar Android."
            if action == "Desinstalar":
                self.execute(self.tools.adb(device, "uninstall", name), device, risk=risk)
            elif action in mutate:
                self.shell(*mutate[action], risk=risk)
            else:
                permission = self.ask("Permiso completo", "android.permission.")
                if permission:
                    self.shell("pm", "grant" if action == "Conceder permiso" else "revoke",
                               name, token(permission), risk=risk)

    def inventory_profile(self):
        action = self.choose("Inventarios", ("Guardar perfil", "Comparar con perfil", "Exportar actual"))
        if not action:
            return
        data = getattr(self, "inventory_data", None)
        if not data:
            raise ValueError("Consulta un inventario primero")
        if action == "Guardar perfil":
            name = self.ask("Nombre del perfil", data["serial"])
            if name:
                self.store.put("inventory", name, data)
        elif action == "Exportar actual":
            self.report(data)
        else:
            profiles = self.store.list("inventory")
            if not profiles:
                raise ValueError("Guarda un inventario primero")
            profile = self.choose("Inventario de referencia", profiles)
            if profile:
                old = profiles[profile]
                if old["tipo"] != data["tipo"]:
                    raise ValueError("Usa inventarios con el mismo tipo de filtro")
                before, now = set(old["paquetes"]), set(data["paquetes"])
                self.report({"referencia": old["serial"], "actual": data["serial"],
                             "añadidos": sorted(now-before), "retirados": sorted(before-now)})

    def extract_apks(self):
        name = token(self.package.text().strip())
        parent = self.directory("Destino de extracción APK")
        if not parent:
            return
        device = self.target()
        query = self.tools.shell(device, "pm", "path", name)
        def work(task):
            result = task.command(query)
            if not result.ok or result.status == "simulated":
                return result
            paths = packages(result.stdout)
            if not paths:
                raise ValueError("No se encontraron rutas APK")
            import tempfile
            folder = Path(tempfile.mkdtemp(prefix=name + "-", dir=parent))
            for index, path in enumerate(paths):
                destination = folder / f"{index:02d}-{Path(path).name}"
                result = task.command(self.tools.adb(device, "pull", remote(path), str(destination)), timeout=300)
                if not result.ok:
                    return result
            task.output.emit("event", f"APK guardados en {folder}\n")
            return result
        self.start(work, device)

    def analyze_apk(self):
        apk = self.file("APK local", "APK (*.apk *.APK)")
        if not apk:
            return
        path, = apk_files([apk])
        tool = self.choose("Analizador instalado", ("apkanalyzer", "aapt", "jadx"))
        if tool in ("apkanalyzer", "aapt"):
            args = ("apk", "summary") if tool == "apkanalyzer" else ("dump", "badging")
            self.execute(self.tools.host(tool, *args, path))
        elif tool == "jadx":
            parent = self.directory("Destino de archivos de JADX")
            if parent:
                import tempfile
                executable = self.tools.locate(tool)
                def work(task):
                    if task.dry:
                        return task.command((executable, "-d", "<destino temporal>", path))
                    folder = tempfile.mkdtemp(prefix="jadx-", dir=parent)
                    return task.command((executable, "-d", folder, path), timeout=600)
                self.start(work)

    def files_page(self):
        layout = self.page("Archivos Android", "Explora rutas accesibles, como /sdcard. Las listas detalladas se muestran en Salida.")
        self.path = self.field(layout, "Ruta Android absoluta", self.store.get("config", "remote_path", "/sdcard"))
        self.file_list, self.file_search = self.output_list(layout, self.enter_path)
        self.buttons(layout, ("Listar", self.list_path), ("Subir nivel", self.parent_path),
                     ("Descargar", self.pull), ("Subir", self.push))
        self.buttons(layout, ("Detalle", lambda: self.shell("ls", "-la", "--", remote(self.path.text()))),
                     ("Espacio libre", lambda: self.shell("df", "-h", remote(self.path.text()))),
                     ("Vista previa", lambda: self.shell("head", "-c", "32768", "--", remote(self.path.text()))),
                     ("Modificar", self.file_change))

    def list_path(self):
        path = remote(self.path.text())
        def done(result):
            if result.status == "finished" and result.ok:
                self.store.put("config", "remote_path", path)
                self.fill(self.file_list, self.file_search, result.stdout.splitlines())
        self.shell("ls", "-1A", "--", path, callback=done)

    def enter_path(self, name):
        if "/" in name or name in (".", ".."):
            raise ValueError("Entrada no válida")
        self.path.setText(remote(self.path.text().rstrip("/") + "/" + name))
        self.file_list.clear()

    def parent_path(self):
        path = remote(self.path.text()).rstrip("/")
        self.path.setText(path.rpartition("/")[0] or "/")
        self.list_path()

    def pull(self):
        path = remote(self.path.text())
        parent = self.directory("Carpeta local de descarga")
        if parent:
            device = self.target()
            from .services import backup
            cmd = self.tools.adb(device, "pull", path)
            if self.confirm(f"Descargar {path} a una carpeta nueva en {parent}", device):
                def work(task):
                    if task.dry:
                        return task.command((*cmd, "<carpeta nueva>"))
                    return backup(parent, path, lambda data: task.command(
                        (*cmd, str(data)), timeout=1800), task.cancel)
                self.start(work, device,
                    lambda result: self.append("event", f"Descarga: {result}\n") if isinstance(result, Path) else None)

    def push(self):
        path = remote(self.path.text())
        mode = self.choose("Origen local", ("Archivos", "Carpeta"))
        if mode == "Archivos":
            paths, _ = QFileDialog.getOpenFileNames(self, "Archivos locales")
        elif mode == "Carpeta":
            selected = self.directory("Carpeta local")
            paths = [str(selected)] if selected else []
        else:
            return
        if paths:
            device = self.target()
            local = [str(Path(p).resolve(strict=True)) for p in paths]
            self.execute(self.tools.adb(device, "push", *local, path), device, timeout=1800,
                         risk="La subida puede sobrescribir archivos existentes en Android.")

    def file_change(self):
        path = remote(self.path.text())
        action = self.choose("Operación de archivos", ("Crear carpeta", "Copiar", "Mover o renombrar", "Eliminar archivo o carpeta vacía"))
        if not action:
            return
        if path == "/":
            raise ValueError("Selecciona una ruta distinta de /")
        if action == "Crear carpeta":
            args = ("mkdir", "--", path)
        elif action.startswith("Eliminar"):
            kind = self.choose("Tipo de destino", ("Archivo", "Carpeta vacía"))
            if not kind:
                return
            args = ("rm" if kind == "Archivo" else "rmdir", "--", path)
        else:
            dest = self.ask("Ruta Android de destino")
            if not dest:
                return
            args = ("cp" if action == "Copiar" else "mv", "--", path, remote(dest))
        self.shell(*args, risk=f"{action}. La operación puede cambiar o borrar archivos.")

    def log_page(self):
        layout = self.page("Logcat", "Flujo en tiempo real, prioridad, PID, etiqueta y expresión regular. "
                           "La consola retiene hasta 5000 bloques. Pausar descarta nuevas líneas de la vista.")
        self.log_pid = self.field(layout, "PID opcional")
        self.log_tag = self.field(layout, "Etiqueta opcional")
        self.log_regex = self.field(layout, "Expresión regular opcional")
        self.log_paused = False
        self.buttons(layout, ("Iniciar Logcat", self.start_log),
                     ("Pausar / reanudar", self.pause_log), ("Exportar", self.export_console))
        layout.addStretch()

    def pause_log(self):
        if not self.sink_filter:
            raise ValueError("Logcat no está en ejecución")
        self.log_paused = not self.log_paused
        self.statusBar().showMessage("Vista pausada" if self.log_paused else "Vista reanudada", 3000)

    def start_log(self):
        pid, tag = self.log_pid.text().strip(), self.log_tag.text().strip()
        if pid and not re.fullmatch(r"[1-9][0-9]{0,8}", pid):
            raise ValueError("PID no válido")
        if tag:
            token(tag)
            if ":" in tag:
                raise ValueError("Introduce una sola etiqueta")
        try:
            regex = bounded_regex.compile(self.log_regex.text())
        except bounded_regex.error as exc:
            raise ValueError(str(exc)) from exc
        priority = self.choose("Prioridad mínima", ("V", "D", "I", "W", "E", "F"))
        if not priority:
            return
        args = ["logcat", "-v", "threadtime"]
        if pid:
            args.append(f"--pid={pid}")
        args += [f"{tag}:{priority}", "*:S"] if tag else [f"*:{priority}"]
        device = self.target()
        cmd = self.tools.adb(device, *args)
        pending = ""
        self.log_paused = False
        def filter_lines(data):
            nonlocal pending
            lines = (pending + data).split("\n")
            pending = lines.pop()[-16384:]
            if self.log_paused:
                return ""
            output = []
            for line in lines:
                try:
                    match = regex.search(line[:4096], timeout=0.005)
                except TimeoutError:
                    self.log_paused = True
                    self.append("event", "Filtro pausado por tiempo de evaluación excesivo\n")
                    break
                if match:
                    if "FATAL EXCEPTION" in line or "ANR in " in line:
                        self.append("event", "[Indicador Logcat] " + line + "\n")
                    output.append(line)
            return "".join(line + "\n" for line in output)
        if self.execute(cmd, device, timeout=None):
            self.sink_filter = filter_lines

    def network_page(self):
        layout = self.page("Red y depuración", "Usa el host:puerto indicado por tu dispositivo autorizado. "
                           "El puerto de emparejamiento puede diferir del puerto de conexión.")
        self.address = self.field(layout, "Host:puerto")
        self.buttons(layout, ("Conectar", lambda: self.network("connect")),
                     ("Desconectar", lambda: self.network("disconnect")),
                     ("Emparejar", lambda: self.network("pair")),
                     ("Perfiles conocidos", self.known_hosts))
        self.buttons(layout, ("IP", lambda: self.shell("ip", "addr")),
                     ("Rutas", lambda: self.shell("ip", "route")),
                     ("Wi-Fi", lambda: self.shell("dumpsys", "wifi")),
                     ("Conectividad", lambda: self.shell("dumpsys", "connectivity")))
        layout.addStretch()

    def network(self, action):
        address = endpoint(self.address.text().strip())
        if action == "pair":
            from PySide6.QtWidgets import QInputDialog, QLineEdit
            code, ok = QInputDialog.getText(self, "Emparejamiento", "Código de seis dígitos",
                                            QLineEdit.EchoMode.Password)
            if not ok:
                return
            if not re.fullmatch(r"[0-9]{6}", code):
                raise ValueError("El código debe tener seis dígitos")
            cmd = self.tools.host("adb", "pair", address)
            def work(task):
                read_fd, write_fd = os.pipe()
                with os.fdopen(read_fd, "rb") as reader, os.fdopen(write_fd, "wb") as writer:
                    writer.write((code + "\n").encode())
                    writer.close()
                    return task.command(cmd, stdin=reader, timeout=20)
            if self.confirm(f"Emparejar con {address}"):
                self.start(work)
        else:
            def done(result):
                if action == "connect" and result.status == "finished" and result.ok and (
                        result.stdout.startswith(("connected to ", "already connected to "))):
                    self.store.put("hosts", address, address)
            self.execute(self.tools.host("adb", action, address),
                         risk=f"{action} {address}", callback=done)

    def known_hosts(self):
        profiles = self.store.list("hosts")
        if not profiles:
            raise ValueError("Todavía no hay conexiones guardadas")
        name = self.choose("Dispositivo conocido", profiles)
        if name:
            action = self.choose(name, ("Cargar dirección", "Olvidar perfil"))
            if action == "Cargar dirección":
                self.address.setText(name)
            elif action == "Olvidar perfil":
                self.store.delete("hosts", name)

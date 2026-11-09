"""Inventarios de ajustes y copia de las preferencias locales."""
import json

from .services import token


class Profiles:
    def settings_profile(self):
        action = self.choose("Perfiles de ajustes", ("Capturar ajustes", "Importar perfil JSON", "Exportar perfil JSON",
                                                     "Comparar perfiles"))
        if action == "Capturar ajustes":
            self.capture_settings()
        elif action == "Importar perfil JSON":
            path = self.file("Perfil de ajustes", "JSON (*.json)")
            if path:
                data = self.read_local_json(path)
                if (not isinstance(data, dict) or not isinstance(data.get("serial"), str) or
                        data.get("espacio") not in ("system", "secure", "global") or
                        not isinstance(data.get("ajustes"), dict) or
                        any(not isinstance(value, str) for value in data["ajustes"].values())):
                    raise ValueError("Formato de perfil de ajustes no válido")
                name = self.ask("Nombre del perfil importado", path.stem)
                if name:
                    self.store.put("settings-profile", name, data)
        elif action:
            profiles = self.store.list("settings-profile")
            if not profiles:
                raise ValueError("Captura o importa un perfil primero")
            name = self.choose("Perfil de referencia", profiles)
            if not name:
                return
            old = profiles[name]
            if action == "Exportar perfil JSON":
                path = self.save("Exportar perfil", "json")
                if path:
                    path.write_text(json.dumps(old, indent=2, ensure_ascii=False), encoding="utf-8")
            else:
                second = self.choose("Perfil actual", profiles)
                if second:
                    new = profiles[second]
                    if old["espacio"] != new["espacio"]:
                        raise ValueError("Elige perfiles del mismo espacio Android")
                    before, after = old["ajustes"], new["ajustes"]
                    self.report({"referencia": old["serial"], "actual": new["serial"], "espacio": old["espacio"],
                                 "cambios": {key: [before.get(key), after.get(key)]
                                             for key in sorted(before.keys() | after.keys())
                                             if before.get(key) != after.get(key)}})

    def capture_settings(self):
        device = self.target()
        namespace = self.choose("Espacio Android", ("system", "secure", "global"))
        if not namespace:
            return
        cmd = self.tools.shell(device, "settings", "list", namespace)
        name = self.ask("Nombre del perfil", f"{device.serial}-{namespace}")
        if not name:
            return
        if not self.confirm("Capturar ajustes en un perfil local. Pueden incluir identificadores o datos sensibles.", device):
            return

        def done(result):
            if result.ok and result.status == "finished":
                rows = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
                self.store.put("settings-profile", name, {"serial": device.serial, "espacio": namespace,
                                                          "ajustes": rows})
        self.execute(cmd, device, callback=done)

    @staticmethod
    def read_local_json(path):
        if not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("Selecciona un archivo JSON regular de hasta 2 MB")
        return json.loads(path.read_text(encoding="utf-8"))

    def local_preferences(self):
        choice = self.choose("Copia de preferencias de Studio", ("Exportar", "Restaurar"))
        if choice == "Exportar":
            path = self.save("Guardar preferencias", "json")
            if path:
                data = {key: self.store.get("config", key, default) for key, default in
                        (("dark", True), ("protected", []), ("remote_path", "/sdcard"))}
                path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        elif choice == "Restaurar":
            path = self.file("Copia de preferencias", "JSON (*.json)")
            if not path:
                return
            data = self.read_local_json(path)
            if (not isinstance(data, dict) or type(data.get("dark")) is not bool or
                    not isinstance(data.get("remote_path"), str) or not isinstance(data.get("protected"), list) or
                    any(not isinstance(item, str) for item in data["protected"])):
                raise ValueError("Formato de preferencias no válido")
            from .services import remote
            android_path = remote(data["remote_path"])
            protected = sorted({token(item) for item in data["protected"]})
            if self.confirm("Restaurar tema, ruta Android y lista adicional de paquetes protegidos"):
                self.apply_theme(data["dark"])
                self.store.put("config", "protected", protected)
                self.store.put("config", "remote_path", android_path)
                self.path.setText(android_path)

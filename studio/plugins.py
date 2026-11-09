"""Extensiones locales declarativas. El manifiesto no importa código Python."""
import json
import shlex

from .services import token


def read_plugin(path):
    if path.stat().st_size > 128 * 1024:
        raise ValueError("Manifiesto demasiado grande")
    data = json.loads(path.read_text(encoding="utf-8"))
    fields = ("name", "version", "description", "compatibility", "permissions", "dependencies", "tests")
    if not isinstance(data, dict) or any(not isinstance(data.get(key), str) or not data[key] for key in fields):
        raise ValueError("Completa los metadatos del plugin")
    actions = data.get("actions")
    if not isinstance(actions, dict) or not 1 <= len(actions) <= 50:
        raise ValueError("Declara entre 1 y 50 acciones")
    for name, args in actions.items():
        token(name)
        if (not isinstance(args, list) or not args or
                any(not isinstance(a, str) or not a or "\0" in a for a in args)):
            raise ValueError(f"Argumentos no válidos en {name}")
    return data


class Plugins:
    def plugin_page(self):
        layout = self.page("Plugins locales", "Importa manifiestos JSON para añadir acciones de shell con controles generados. "
                           "Cada ejecución exige confirmación sobre el serial seleccionado.")
        self.buttons(layout, ("Importar manifiesto", self.import_plugin), ("Administrar / ejecutar", self.plugin_action))
        layout.addStretch()

    def import_plugin(self):
        path = self.file("Manifiesto de plugin", "JSON (*.json)")
        if path:
            data = read_plugin(path)
            self.store.put("plugin", data["name"], {"enabled": False, "manifest": data})

    def plugin_action(self):
        installed = self.store.list("plugin")
        if not installed:
            raise ValueError("Importa un manifiesto primero")
        name = self.choose("Plugin local", installed)
        if not name:
            return
        plugin = installed[name]
        data = plugin["manifest"]
        self.append("event", json.dumps({key: value for key, value in data.items() if key != "actions"},
                                        ensure_ascii=False, indent=2) + "\n")
        action = self.choose(name, ("Desactivar", "Ejecutar", "Eliminar") if plugin["enabled"]
                             else ("Activar", "Eliminar"))
        if action == "Activar":
            if self.confirm(f"Activar {name} {data['version']}\n{data['description']}\n{data['permissions']}"):
                plugin["enabled"] = True
                self.store.put("plugin", name, plugin)
        elif action == "Desactivar":
            plugin["enabled"] = False
            self.store.put("plugin", name, plugin)
        elif action == "Eliminar" and self.confirm(f"Eliminar {name}"):
            self.store.delete("plugin", name)
        elif action == "Ejecutar":
            selected = self.choose("Acción", data["actions"])
            if selected:
                args = data["actions"][selected]
                self.shell(*args, risk=f"{name} / {selected}\n{shlex.join(args)}\n{data['permissions']}")

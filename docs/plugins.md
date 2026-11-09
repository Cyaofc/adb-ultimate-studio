# Desarrollo de plugins

Un plugin declarativo añade acciones Android en el panel **Plugins locales**. Guarda un archivo JSON como este:

```json
{
  "name": "Consultas de ejemplo",
  "version": "1.0",
  "description": "Consulta la identidad y resolución del objetivo",
  "compatibility": "Android con shell ADB y utilidad wm",
  "permissions": "Lectura como usuario shell",
  "dependencies": "adb, wm",
  "tests": "Comprobar salida de id y wm size en dispositivo autorizado",
  "actions": {
    "identidad": ["id"],
    "resolucion": ["wm", "size"]
  }
}
```

Las acciones reciben una lista de argumentos. La aplicación cita cada argumento al construir la orden para el shell Android. La primera palabra sigue siendo un programa ejecutable en el dispositivo. Revisa siempre el origen, los argumentos y sus efectos.

La interfaz se genera desde el manifiesto. El plugin se importa desactivado. Selecciona el plugin, revisa sus datos, actívalo y confirma la acción sobre el objetivo explícito. Los metadatos de compatibilidad y pruebas son informativos. Las extensiones declarativas carecen de hooks Python y widgets arbitrarios.

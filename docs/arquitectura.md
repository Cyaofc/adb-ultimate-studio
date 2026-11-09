# Arquitectura y manifiesto

- `studio/commands.py` define objetivos, estados, detección y construcción de argumentos.
- `studio/runner.py` ejecuta procesos aislados con salida incremental, cancelación y plazos.
- `studio/store.py` persiste configuración, perfiles e historial en SQLite.
- `studio/services.py` reúne operaciones Android, respaldos, macros y validadores independientes de Qt.
- `studio/window.py` coordina selección, tareas y navegación. `studio/pages.py` contiene los paneles.
- `studio/__main__.py` inicia la aplicación y configura los registros.
- `tests/` verifica la lógica con procesos locales y contiene pruebas opcionales para hardware autorizado.
- `scripts/` instala en un entorno virtual y arranca la aplicación. `assets/` contiene los recursos del lanzador.
- `README.md` y `docs/alcance.md` documentan instalación, uso y cobertura.

`studio/tasks.py` adapta el ejecutor al modelo de señales de Qt. `studio/advanced.py` contiene flujos de pantalla, respaldo, macros y ajustes. `studio/monitor.py`, `studio/plugins.py`, `studio/partition.py` y `studio/scheduling.py` encapsulan sus paneles y flujos específicos.

Las acciones construyen una orden con un objetivo inmutable antes de iniciar el trabajo. Las consultas del host se identifican como tales. El ejecutor usa un grupo de procesos Linux para cancelar y drenar las dos salidas. La UI recibe texto por señales y conserva un historial acotado de la consola. SQLite se abre por operación para que el hilo de la interfaz y el de ejecución tengan conexiones independientes.

La capa de comandos distingue argumentos del proceso local y argumentos del shell Android. Las acciones guiadas citan los argumentos remotos. La terminal acepta una orden remota deliberadamente arbitraria tras una confirmación. Las extensiones agregan acciones mediante manifiestos JSON.

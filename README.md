# ADB Ultimate Studio

Aplicación de escritorio para Linux que administra dispositivos Android autorizados mediante ADB y Fastboot. Incluye simulación, selector explícito por serial y registro local en SQLite.

## Instalar

Requiere Python 3.12 o posterior con `venv`, un escritorio Linux y bibliotecas del sistema compatibles con Qt 6. En Debian, Ubuntu o Kali, instala `python3-venv` para el Python de la distribución. Si tu versión por defecto es anterior a 3.12, selecciona un Python compatible con `ADB_STUDIO_PYTHON`. Si Qt indica que falta el complemento XCB, revisa las dependencias de Qt de la distribución, entre ellas `libxcb-cursor0`.

Instala ADB y Fastboot desde el SDK Manager o desde el paquete oficial de Platform Tools para Linux. Añade el directorio a `PATH` o indica las rutas absolutas en **Preferencias → Rutas de herramientas**. Puedes instalar scrcpy por separado. [Android SDK Platform Tools](https://developer.android.com/tools/releases/platform-tools), [scrcpy](https://github.com/Genymobile/scrcpy).

Desde la carpeta del proyecto:

```sh
./scripts/install.sh
./scripts/start.sh
```

El instalador crea `.venv`, instala las dependencias Python desde el índice de pip configurado y comprueba qué herramientas están en `PATH`. Usa `./scripts/install.sh --no-desktop` para omitir la entrada del menú. La ruta a la copia instalada debe conservarse para que funcione el lanzador.

## Primer inicio

1. Deja marcada **Simulación** para conocer los paneles. Los objetivos `SIMULACION-*` permiten revisar órdenes sin ejecutar programas externos.
2. Para USB, activa las opciones de desarrollador y la depuración USB, conecta el dispositivo, desbloquéalo y acepta el aviso RSA. Quita **Simulación** y selecciona el serial correcto. Si aparece `no permissions`, aplica las reglas udev de tu distribución y verifica la pertenencia al grupo que esas reglas exigen. Reconecta el cable después de aplicar las reglas. [Configurar dispositivos físicos](https://developer.android.com/studio/run/device).
3. Para Wi-Fi, en Android compatible usa **Depuración inalámbrica** y abre el diálogo de emparejamiento del teléfono. En **Red y depuración**, escribe el host y puerto de emparejamiento, selecciona **Emparejar** e introduce el código. Luego usa el host y puerto de conexión que muestra el dispositivo. [Depuración inalámbrica](https://developer.android.com/tools/adb#wireless).
4. Usa **Ficha del dispositivo** para comprobar el destino. La consola inferior separa salida, errores y eventos.

## Uso por panel

| Panel | Operaciones disponibles |
| --- | --- |
| Dispositivos y sistema | Detección ADB/Fastboot, ficha y exportación, consultas del sistema, gestión del servidor, diagnóstico root y versiones |
| Terminal ADB | Comando remoto, sesión persistente por líneas sin PTY, favoritos, biblioteca y búsqueda en historial |
| Aplicaciones APK | Inventario de usuario, sistema y deshabilitadas, instalación simple, lotes y splits, permisos, extracción, análisis externo y perfiles comparables |
| Archivos Android | Navegación por rutas, detalle, vista previa, espacio libre, transferencias, creación, copia, movimiento y borrado de archivos o carpetas vacías |
| Logcat | Vista en directo, prioridad, PID, etiqueta, expresión regular con límite de evaluación, pausa, guardado y comparación de sesiones |
| Monitor | Muestras de memoria disponible y batería, gráfico temporal y exportación |
| Pantalla y macros | PNG, grabación H.264, scrcpy, entrada de teclas/texto/toques/gestos, perfiles JSON/YAML y ejecución por paso |
| Respaldos | Copias independientes, SHA-256, verificación, restauración, comparación y programación puntual |
| Fastboot | Variables, reinicio y manifiesto local de imagen |
| Particiones Fastboot | Flasheo de imágenes con cabecera reconocida y borrado, ambos con activación de sesión y confirmación escrita por serial y partición |
| Red y depuración | Emparejar, conectar, desconectar, consultar IP, rutas, Wi-Fi y conectividad, guardar y olvidar destinos, resolución DNS y prueba TCP de un destino |
| Ajustes Android | Leer system/secure/global y editar o restaurar un grupo de ajustes de pantalla en system, perfiles y comparación |
| Plugins locales | Importar manifiestos, activar, desactivar, eliminar y ejecutar acciones confirmadas |
| Preferencias | Tema, rutas de ejecutables y lista adicional de paquetes protegidos y copia parcial de preferencias |

La aplicación ejecuta una tarea de usuario a la vez. Usa **Cancelar tarea** para terminar el proceso local. Una operación ya iniciada en el dispositivo puede haber aplicado cambios parciales. Para cambiar de objetivo, verifica siempre el serial mostrado en el encabezado y en la confirmación.

## Solución de problemas

- **unauthorized**. Desbloquea el teléfono y revisa el aviso RSA. Comprueba que el cable permita datos.
- **offline**. Reconecta el dispositivo o reinicia el servidor ADB desde el panel. El servidor se comparte con otras sesiones de ADB.
- **sideload**. El objetivo aparece en la lista. Las operaciones de shell requieren el estado normal `device`.
- **ADB funciona pero Fastboot no**. El dispositivo debe estar en un modo compatible y las reglas USB pueden usar un identificador distinto. Algunos fabricantes emplean otro protocolo.
- **Permiso denegado**. El usuario de shell depende de Android, el fabricante y SELinux. Las consultas con `su` necesitan root concedido en el dispositivo. Los respaldos cubren las rutas accesibles que se seleccionen.
- **El paquete o el ajuste no cambia**. Examina ambas salidas. La disponibilidad de comandos, servicios y permisos depende de Android y de sus políticas.
- **Grabación vacía o fallida**. El modo directo H.264 necesita una implementación de `screenrecord` que acepte salida a stdout. Las superficies protegidas pueden quedar ocultas.
- **Fastboot**. Revisa las instrucciones del fabricante, modo, slots e imagen. Una firma de cabecera y el SHA-256 sirven para identificar el archivo y comprobar su integridad local. La compatibilidad con el dispositivo y la partición depende del fabricante. [Referencia de Fastboot en AOSP](https://android.googlesource.com/platform/system/core/+/refs/heads/main/fastboot/README.md).

## Pruebas y distribución

```sh
.venv/bin/python -m pip install -e '.[test]'
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest
```

La prueba física es de lectura y exige un serial autorizado explícito:

```sh
ADB_STUDIO_TEST_SERIAL=MI_SERIAL .venv/bin/python -m pytest -m hardware
```

Para compilar un ejecutable de escritorio con PyInstaller desde Linux, instala también la biblioteca compartida de tu Python, por ejemplo `libpython3.13` si ese es el paquete de tu distribución:

```sh
.venv/bin/python -m pip install -e '.[bundle]'
.venv/bin/python -m PyInstaller --name adb-ultimate-studio --noconfirm --onedir scripts/bundle.py
dist/adb-ultimate-studio/adb-ultimate-studio --check
```

Distribuye la carpeta completa de `dist`. Compila en una distribución compatible con la más antigua de destino. ADB, Fastboot y scrcpy se instalan por separado. El lanzador del instalador Python se configura por separado.

Para actualizar manualmente, respalda la carpeta de datos, verifica el origen y el hash de la distribución que vas a instalar y ejecuta su instalador. Para desinstalar, cierra la aplicación, retira el directorio del proyecto y borra el lanzador `applications/adb-ultimate-studio.desktop` y su icono `icons/hicolor/scalable/apps/adb-ultimate-studio.svg` en `${XDG_DATA_HOME:-~/.local/share}`. Borra la carpeta de datos solo si deseas eliminar historial y perfiles.

La base de datos y los registros están en `${XDG_DATA_HOME:-~/.local/share}/adb-ultimate-studio`. Las órdenes guiadas y las rutas pueden quedar en el historial. El texto de comandos libres se guarda en SQLite solo al activar su casilla o guardarlo como favorito. Evita incluir secretos en órdenes, perfiles y exportaciones. El código de emparejamiento se envía por stdin. La aplicación usa archivos locales y procesos configurados por el usuario.

Consulta [arquitectura y manifiesto](docs/arquitectura.md), [estado por función](docs/alcance.md) y [desarrollo de extensiones](docs/plugins.md).

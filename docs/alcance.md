# Estado de la entrega

## Implementado

Los paneles y acciones de la tabla del README están conectados a procesos reales, a operaciones locales o al modo de simulación. La prueba Qt usa un ADB simulado con dos seriales y comprueba el objetivo, las salidas, la ficha y el rechazo de una acción destructiva. Las pruebas de núcleo cubren procesos, tiempos, cancelación, persistencia, validación, macros y manifiestos.

## Sujeto al dispositivo o experimental

- Grabación directa H.264, filtros Logcat por PID, detalles de servicios y acceso a rutas privadas dependen del sistema.
- Diagnóstico root requiere autorización de `su` y disponibilidad de las herramientas consultadas.
- Flasheo y borrado están implementados con confirmación escrita, deshabilitados inicialmente. La identificación de formato reconoce cabeceras y el hash protege contra cambios del archivo entre preparación y ejecución. Las pruebas de la entrega carecen de operaciones reales sobre particiones. Usa documentación del fabricante para establecer compatibilidad.
- La cancelación afecta el proceso local y no revierte cambios aplicados.
- Los respaldos programados se ejecutan durante la sesión abierta. Si hay una tarea activa, falta el objetivo o está activa la simulación, se omiten y dejan un evento.
- El historial de métricas se conserva en memoria hasta iniciar otro muestreo o cerrar la ventana. Exporta las muestras para conservarlas.

## Pendiente

- Aplicaciones. Inventario de apps suspendidas y estimación de espacio por app. La disponibilidad de borrar caché o retirar actualizaciones se comprueba en la ayuda de `pm`.
- Explorador. Fechas y tamaños en columnas, iconos por tipo, progreso porcentual y velocidad normalizados. La salida de las herramientas puede mostrar progreso de transferencia.
- Terminal. PTY real y envío de Ctrl+C remoto, variables parametrizadas y detección automática de requisitos. La sesión persistente acepta líneas y puede cerrarse con la cancelación local.
- Logcat. Filtros guardados y captura automática de contexto. La detección básica marca ANR y excepciones fatales.
- Automatización. Programación persistente de macros, perfiles ligados al serial y editor visual de pasos.
- Root y Fastboot. Perfiles de dispositivos modificados, análisis de boot image remota, validación exhaustiva de formatos y matrices de compatibilidad por dispositivo y favoritos específicos.
- Respaldos. Copia integral de base de datos desde la interfaz y programación con la aplicación cerrada. La copia guiada de preferencias comprende el tema, la última ruta y los paquetes protegidos adicionales.
- Red. Detección avanzada de conexiones duplicadas.
- Plugins. UI nativa personalizada y ejecución de pruebas del plugin desde el gestor.
- Distribución. Instalador nativo DEB y actualizador integrado.

## Fuera del alcance operativo

El respaldo de datos privados depende de permisos reales y del sistema. El desbloqueo de bootloader, la instalación de root y la elusión de autenticación o controles antirrobo carecen de acciones dedicadas.

"""Plantillas de consulta y referencias a los paneles especializados."""
from dataclasses import dataclass

from .services import INFO


@dataclass(frozen=True)
class Entry:
    category: str
    name: str
    args: tuple[str, ...]
    requirements: str = "ADB autorizado, estado device"
    compatibility: str = "Sujeto a servicios, comandos y permisos de Android"
    risk: str = "Lectura. La salida puede contener datos del dispositivo."
    route: str = "shell"


ENTRIES = [
    Entry("Información del dispositivo", name, INFO[name])
    for name in ("Propiedades", "Kernel", "Tiempo de actividad", "Resolución", "Densidad")
] + [
    Entry("Diagnóstico", "Políticas visibles", INFO["Políticas"]),
    Entry("Paquetes", "Inventario de usuario", ("pm", "list", "packages", "-3")),
    Entry("Archivos", "Listar almacenamiento compartido", ("ls", "-la", "/sdcard")),
    Entry("Shell", "Identidad del usuario remoto", ("id",)),
    Entry("Logcat", "Seguir mensajes de aviso o superior", ("logcat", "*:W"), route="Logcat"),
    Entry("Batería", "Estado de batería", INFO["Batería y temperatura"]),
    Entry("Memoria", "Memoria del sistema", INFO["RAM"]),
    Entry("Red", "Interfaces IP", INFO["Interfaces IP"]),
    Entry("Capturas de pantalla", "Generar PNG", ("exec-out", "screencap", "-p"), route="Pantalla y macros"),
    Entry("Automatización", "Pulsar Atrás", ("input", "keyevent", "4"),
          risk="Modifica la interacción de la aplicación en pantalla."),
    Entry("Fastboot", "Consultar producto", ("getvar", "product"), requirements="Serial en modo Fastboot",
          compatibility="Requiere soporte del bootloader o fastbootd", route="Fastboot"),
    Entry("Root", "Buscar el binario su", INFO["Presencia de su"]),
    Entry("Respaldos", "Copiar una ruta accesible", ("pull", "/sdcard/DCIM", "./copia"),
          risk="Escribe una copia en el equipo local.", route="Respaldos"),
    Entry("Configuración", "Listar ajustes system", ("settings", "list", "system")),
    Entry("Desarrollo", "Listar servicios", INFO["Servicios"]),
    Entry("Recuperación de errores", "Consultar versión local de ADB", ("version",),
          requirements="ADB en el equipo local", route="Dispositivos y sistema"),
]

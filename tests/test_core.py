from pathlib import Path
import subprocess
import sys
from threading import Event, Timer

import pytest

from studio.commands import Device, Tools, devices
from studio.runner import Result, run
from studio.services import (
    apk_files, backup, endpoint, input_args, load_macro, manifest, packages, properties, remote,
    verified_backup,
)
from studio.store import Store


def test_adb_device_states():
    raw = """List of devices attached
ZX012 device usb:1-2 product:test model:Pixel transport_id:1
192.168.0.2:5555 offline transport_id:2
NOAUTH unauthorized usb:1-4
NOUSB no permissions (missing udev rules)
TEST sideload
"""
    assert [(d.serial, d.state) for d in devices("adb", raw)] == [
        ("ZX012", "device"), ("192.168.0.2:5555", "offline"), ("NOAUTH", "unauthorized"),
        ("NOUSB", "no permissions"), ("TEST", "sideload")]
    assert devices("fastboot", "abcd\tfastboot\n") == [Device("fastboot", "abcd", "fastboot")]


def test_multiple_and_quote(monkeypatch):
    tools = Tools()
    monkeypatch.setattr(tools, "locate", lambda name: "/usr/bin/" + name)
    device = Device("adb", "TARGET", "device")
    assert tools.shell(device, "ls", "/sdcard/a; b") == (
        "/usr/bin/adb", "-s", "TARGET", "shell", "ls '/sdcard/a; b'")
    with pytest.raises(ValueError):
        tools.adb(None, "install", "/tmp/test.apk")
    with pytest.raises(ValueError):
        tools.adb(Device("adb", "N", "unauthorized"), "shell", "id")
    with pytest.raises(ValueError):
        tools.fastboot(device, "getvar", "product")


def test_runner_outputs_errors():
    output = []
    result = run([sys.executable, "-c", "import sys; print('ok'); print('bad', file=sys.stderr); sys.exit(3)"],
                 Event(), lambda *data: output.append(data))
    assert result.code == 3 and not result.ok
    assert result.stdout == "ok\n" and result.stderr == "bad\n"
    assert set(output) == {("stdout", "ok\n"), ("stderr", "bad\n")}


def test_timeout_and_missing():
    result = run([sys.executable, "-c", "import time; time.sleep(20)"], Event(), timeout=0.2)
    assert result.status == "timeout" and result.duration < 3
    assert run(["/no/executable"], Event()).status == "error"


def test_cancellation():
    cancel = Event()
    timer = Timer(0.25, cancel.set)
    timer.start()
    try:
        result = run([sys.executable, "-c", "import time; time.sleep(20)"], cancel)
    finally:
        timer.cancel()
        timer.join()
    assert result.status == "cancelled" and result.duration < 3


def test_dry_run_install(tmp_path, monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("Se inició un proceso en simulación")

    monkeypatch.setattr(subprocess, "Popen", unexpected)
    apk = tmp_path / "sample.apk"
    apk.write_bytes(b"sample")
    result = run(("/fake/adb", "-s", "serial", "install", *apk_files([apk])), Event(), dry=True)
    assert result.ok and result.status == "simulated"
    with pytest.raises(ValueError):
        apk_files([tmp_path])


@pytest.mark.parametrize("path", ["relative", "/sdcard/../data", "/file\nname"])
def test_unsafe_remote_path(path):
    with pytest.raises(ValueError):
        remote(path)


def test_parsers():
    assert remote("//sdcard/./app") == "/sdcard/app"
    assert endpoint("[fe80::1]:5555") == "[fe80::1]:5555"
    with pytest.raises(ValueError):
        endpoint("-option:5555")
    assert properties("[ro.product.name]: [Pixel]\nnoise\n") == {"ro.product.name": "Pixel"}
    assert packages("package:z\npackage:a\npackage:z\n") == ["a", "z"]


def test_sqlite(tmp_path):
    path = tmp_path / "nested" / "studio.sqlite"
    store = Store(path)
    store.put("macro", "Prueba", [{"action": "tap"}])
    store.record("SERIAL", "adb -s SERIAL shell id", Result(0, duration=0.1))
    reopened = Store(path)
    assert reopened.get("macro", "Prueba") == [{"action": "tap"}]
    assert reopened.history("serial")[0][1] == "SERIAL"
    assert not reopened.history("absent")
    reopened.delete("macro", "Prueba")
    assert not reopened.list("macro")
    assert path.stat().st_mode & 0o777 == 0o600


def test_macro_validation(tmp_path):
    path = tmp_path / "macro.yaml"
    path.write_text("- action: tap\n  args: ['20', '50']\n  retries: 2\n")
    assert load_macro(path)[0]["retries"] == 2
    assert input_args("text", ["hola mundo"]) == ("input", "text", "hola%smundo")
    path.write_text('- action: text\n  args: ["; rm -rf /"]\n')
    with pytest.raises(ValueError):
        load_macro(path)


def test_backup_integrity_and_uniqueness(tmp_path):
    def execute(data):
        (data / "test.txt").write_text("contenido")
        return Result(0)
    a = backup(tmp_path, "/sdcard/test.txt", execute, Event())
    b = backup(tmp_path, "/sdcard/test.txt", execute, Event())
    assert a != b
    assert verified_backup(a, Event())["files"] == manifest(b / "data", Event())
    (a / "data" / "test.txt").write_text("cambio")
    with pytest.raises(ValueError, match="no coinciden"):
        verified_backup(a, Event())
    (b / "data" / "alias").symlink_to("/etc/passwd")
    with pytest.raises(ValueError, match="enlace"):
        verified_backup(b, Event())


def test_failed_backup_does_not_publish_partial_files(tmp_path):
    def fail(data):
        (data / "partial").touch()
        return Result(1)
    assert not backup(tmp_path, "/x", fail, Event()).ok
    assert not list(tmp_path.iterdir())


def test_plugin_import_only_parses_manifest(tmp_path):
    import json

    from studio.plugins import read_plugin

    plugin = tmp_path / "example.json"
    data = dict.fromkeys(("name", "version", "description", "compatibility", "permissions", "dependencies", "tests"), "x")
    data["actions"] = {"diagnostic": ["id"]}
    plugin.write_text(json.dumps(data))
    assert read_plugin(plugin)["actions"]["diagnostic"] == ["id"]
    data["actions"]["diagnostic"] = "id"
    plugin.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        read_plugin(plugin)


def test_log_compare(tmp_path):
    from studio.log_sessions import compare_logs

    before, after = tmp_path / "before.txt", tmp_path / "after.txt"
    before.write_text("old\n")
    after.write_text("new\n")
    result = list(compare_logs(before, after))
    assert "-old\n" in result and "+new\n" in result


def test_sparse_image_size_check(tmp_path):
    import struct

    from studio.partition import expanded_size, image_format

    path = tmp_path / "test.img"
    header = struct.pack("<IHHHHIIII", 0xED26FF3A, 1, 0, 28, 12, 4096, 128, 1, 0)
    path.write_bytes(header + bytes(36))
    assert image_format(path) == "Android sparse"
    assert expanded_size(path, "Android sparse") == 4096 * 128
    path.write_bytes(header)
    with pytest.raises(ValueError):
        expanded_size(path, "Android sparse")

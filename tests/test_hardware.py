import os
from threading import Event

import pytest

from studio.commands import Tools, devices
from studio.runner import run


@pytest.mark.hardware
def test_read_authorized_hardware():
    serial = os.environ.get("ADB_STUDIO_TEST_SERIAL")
    if not serial:
        pytest.skip("Define ADB_STUDIO_TEST_SERIAL para habilitar la prueba física")
    tools = Tools()
    result = run(tools.host("adb", "devices", "-l"), Event(), timeout=10)
    assert result.ok, result.stderr
    targets = [device for device in devices("adb", result.stdout) if device.serial == serial]
    assert len(targets) == 1 and targets[0].state == "device"
    result = run(tools.shell(targets[0], "getprop", "ro.build.version.sdk"), Event(), timeout=10)
    assert result.ok and result.stdout.strip().isdecimal(), result.stderr

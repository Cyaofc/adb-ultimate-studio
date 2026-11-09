import os
from pathlib import Path
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from studio.store import Store
from studio.window import Window


def until(app, condition, timeout=5):
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert condition()


def test_launch_select_and_read_through_fake_adb(tmp_path):
    app = QApplication.instance() or QApplication([])
    fake = tmp_path / "adb"
    fake.write_text(f"""#!{sys.executable}
import sys
a = sys.argv[1:]
if a == ['devices', '-l']:
    print('List of devices attached\\nFIRST device model:One\\nSECOND device model:Two')
elif a == ['-s', 'SECOND', 'shell', 'id']:
    print('uid=2000(shell)')
    print('stderr separado', file=sys.stderr)
elif a == ['-s', 'SECOND', 'shell', 'getprop']:
    print('[ro.product.model]: [Modelo simulado]')
else:
    sys.exit(17)
""")
    fake.chmod(0o700)
    store = Store(tmp_path / "studio.sqlite")
    store.put("config", "tools", {"adb": str(fake), "fastboot": str(tmp_path / "no-fastboot")})
    window = Window(store)
    window.show()
    try:
        until(app, lambda: window.selector.count() == 3 and not window.discovery)
        assert window.selector.currentData() is None
        assert window.device_metrics["adb"].text() == "2"
        window.selector.setCurrentIndex(2)
        assert window.target().serial == "SECOND"
        assert window.device_metrics["target"].text() == "Two · device"
        window.shell("id")
        until(app, lambda: not window.task)
        assert "uid=2000(shell)" in window.views["stdout"].toPlainText()
        assert "stderr separado" in window.views["stderr"].toPlainText()
        assert store.history()[0][1] == "SECOND"
        window.confirm = lambda *_: False
        assert not window.shell("pm", "clear", "com.test.app", risk="Borrar datos")
        assert len(store.history()) == 1
        window.snapshot()
        until(app, lambda: not window.task)
        assert "Modelo simulado" in window.summary.text()
    finally:
        window.close()
        app.processEvents()


def test_partition_disabled_and_typed_confirmation(tmp_path):
    import pytest

    app = QApplication.instance() or QApplication([])
    window = Window(Store(tmp_path / "studio.sqlite"))
    try:
        with pytest.raises(ValueError, match="Habilita"):
            window.partition_target()
        window.ask = lambda *_: "ERASE OTHER userdata"
        assert not window.partition_confirm("TARGET", "ERASE", "userdata", "")
        window.ask = lambda *_: "ERASE TARGET userdata"
        assert window.partition_confirm("TARGET", "ERASE", "userdata", "")
    finally:
        window.close()
        app.processEvents()

"""Procesos Linux sin shell local. Cada operación posee su grupo de procesos."""
from dataclasses import dataclass
import codecs
import os
import selectors
import signal
import subprocess
import time


@dataclass(frozen=True)
class Result:
    code: int
    stdout: str = ""
    stderr: str = ""
    duration: float = 0
    status: str = "finished"

    @property
    def ok(self):
        return self.code == 0 and self.status in ("finished", "simulated")


def run(argv, cancel, emit=lambda channel, data: None, *, timeout=60,
        dry=False, sink=None, stdin=None, capture_limit=1024 * 1024):
    start = time.monotonic()
    if cancel.is_set():
        return Result(-1, status="cancelled")
    if dry:
        return Result(0, status="simulated")
    try:
        process = subprocess.Popen(argv, stdin=stdin or subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True)
    except OSError as exc:
        return Result(-1, stderr=str(exc), status="error")
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    decoders = {key: codecs.getincrementaldecoder("utf-8")("replace") for key in buffers}
    status = "finished"
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            while selector.get_map() or process.poll() is None:
                if cancel.is_set() or (timeout is not None and time.monotonic() - start >= timeout):
                    status = "cancelled" if cancel.is_set() else "timeout"
                    break
                for key, _ in selector.select(0.1):
                    stream = key.data
                    data = os.read(key.fd, 65536)
                    if not data:
                        selector.unregister(key.fileobj)
                        if stream != "stdout" or sink is None:
                            tail = decoders[stream].decode(b"", final=True)
                            if tail:
                                emit(stream, tail)
                        continue
                    if stream == "stdout" and sink is not None:
                        sink.write(data)
                    else:
                        buffer = buffers[stream]
                        buffer.extend(data)
                        if len(buffer) > capture_limit:
                            del buffer[:-capture_limit]
                        emit(stream, decoders[stream].decode(data))
    finally:
        if process.poll() is None or status != "finished":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait()
        process.stdout.close()
        process.stderr.close()
    return Result(process.returncode, *(b.decode("utf-8", "replace") for b in buffers.values()),
                  time.monotonic() - start, status)

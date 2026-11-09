"""Persistencia local en el directorio XDG del usuario."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3


def data_dir():
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "adb-ultimate-studio"


class Store:
    def __init__(self, path):
        self.path = path
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS profiles (
                    category TEXT, name TEXT, value TEXT, PRIMARY KEY(category,name));
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY, time TEXT DEFAULT CURRENT_TIMESTAMP,
                    target TEXT, command TEXT, status TEXT, code INTEGER, duration REAL);
            """)
        path.chmod(0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        try:
            with db:
                yield db
        finally:
            db.close()

    def put(self, category, name, value):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO profiles VALUES (?,?,?)",
                       (category, name, json.dumps(value, ensure_ascii=False)))

    def get(self, category, name, default=None):
        with self.connect() as db:
            row = db.execute("SELECT value FROM profiles WHERE category=? AND name=?",
                             (category, name)).fetchone()
        return json.loads(row[0]) if row else default

    def list(self, category):
        with self.connect() as db:
            rows = db.execute("SELECT name,value FROM profiles WHERE category=? ORDER BY name",
                              (category,)).fetchall()
        return {name: json.loads(value) for name, value in rows}

    def delete(self, category, name):
        with self.connect() as db:
            db.execute("DELETE FROM profiles WHERE category=? AND name=?", (category, name))

    def record(self, target, command, result):
        with self.connect() as db:
            db.execute("INSERT INTO history(target,command,status,code,duration) VALUES (?,?,?,?,?)",
                       (target, command, result.status, result.code, result.duration))

    def history(self, query=""):
        with self.connect() as db:
            return db.execute("""SELECT time,target,command,status,code,duration FROM history
                              WHERE instr(lower(target||' '||command),lower(?)) > 0 OR ?=''
                              ORDER BY id DESC LIMIT 1000""", (query, query)).fetchall()

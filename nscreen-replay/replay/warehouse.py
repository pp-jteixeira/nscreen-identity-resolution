"""Streaming Trino access with writes confined to the requested sandbox prefix."""

import getpass
import importlib.util
import json
import os
import re
from contextlib import suppress
from pathlib import Path

from dotenv import load_dotenv


def connect():
    config = Path(os.environ.get("PULSEPOINT_HOME", "~/.pulsepoint")).expanduser()
    load_dotenv(config / ".env", override=False)
    if not os.environ.get("TRINO_PASSWORD"):
        raise RuntimeError(
            "TRINO_PASSWORD must be available; interactive credential prompts are disabled"
        )
    path = Path(
        os.environ.get("PULSEPOINT_DBFUNCS", str(config / "dbfuncs.py"))
    ).expanduser()
    if path.is_dir():
        path /= "dbfuncs.py"
    spec = importlib.util.spec_from_file_location("replay_dbfuncs", path)
    module = importlib.util.module_from_spec(spec)
    previous = getpass.getpass

    def no_prompt(*args, **kwargs):
        raise RuntimeError("Interactive credential prompts are disabled")

    getpass.getpass = no_prompt
    try:
        spec.loader.exec_module(module)
    finally:
        getpass.getpass = previous
    session = json.loads(os.environ.get("NSCREEN_TRINO_SESSION", "{}"))
    allowed = {
        "max_writer_task_count",
        "task_max_writer_count",
        "task_scale_writers_enabled",
    }
    if not isinstance(session, dict) or set(session) - allowed:
        raise ValueError(
            "NSCREEN_TRINO_SESSION accepts only writer concurrency settings"
        )
    return module.get_trino_connection(session_properties=session or None)


def check_write(sql):
    clean = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL).lstrip()
    match = re.match(
        r"(?:CREATE\s+(?:TABLE|VIEW)|INSERT\s+INTO)\s+([a-z0-9_.]+)\b",
        clean,
        re.IGNORECASE,
    )
    if not match or not re.fullmatch(
        r"iceberg\.jteixeira_ipa\.nscreen2_[a-z0-9_]+", match[1]
    ):
        raise ValueError(
            "Replay writes are restricted to iceberg.jteixeira_ipa.nscreen2_*; no DROP/DELETE/REPLACE"
        )


class Warehouse:
    def __init__(self):
        self.last_query_id = None

    def stream_batches(self, sql, write=False, batch_rows=100_000):
        if batch_rows <= 0:
            raise ValueError("batch_rows must be positive")
        if write:
            check_write(sql)
        else:
            clean = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL).lstrip()
        if not write and not re.match(
            r"(SELECT|WITH|SHOW|DESCRIBE|EXPLAIN)\b", clean, re.IGNORECASE
        ):
            raise ValueError("Read operation must be read-only")
        conn = connect()
        cur = conn.cursor()
        try:
            cur.execute(sql)
            self.last_query_id = cur.query_id
            while rows := cur.fetchmany(batch_rows):
                yield rows
        except BaseException:
            # Cancel this client's query on failure; never cancel someone else's job.
            if getattr(cur, "_query", None) is not None:
                with suppress(Exception):
                    cur.cancel()
            raise
        finally:
            cur.close()
            conn.close()

    def stream(self, sql, write=False):
        for rows in self.stream_batches(sql, write=write, batch_rows=5000):
            yield from rows

    def rows(self, sql, write=False):
        return list(self.stream(sql, write=write))

    def execute(self, sql):
        return self.rows(sql, write=True)

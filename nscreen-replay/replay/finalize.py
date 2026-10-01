"""Wait for an existing replay, then perform its production comparisons."""

import argparse
import fcntl
import json
import os
import subprocess
import sys
from pathlib import Path

from .runner import ROOT, Replay, save_json, stamp
from .sql import FILES, identifier


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--forge", type=Path, default=Path.home() / "forge")
    parser.add_argument("--background", action="store_true")
    parser.add_argument("--accept-engine-change", action="store_true")
    args = parser.parse_args()
    directory = ROOT / "runs" / identifier(args.run_id)
    manifest = directory / "manifest.json"
    if not manifest.exists():
        parser.error("An existing replay run is required")
    if args.background:
        cmd = [
            sys.executable,
            "-m",
            "replay.finalize",
            "--run-id",
            args.run_id,
            "--forge",
            str(args.forge),
        ]
        if args.accept_engine_change:
            cmd.append("--accept-engine-change")
        with (directory / "finalizer.log").open("a") as log:
            process = subprocess.Popen(
                cmd,
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        print(
            f"Comparison finalizer PID {process.pid}; log: {directory / 'finalizer.log'}"
        )
        return

    status_path = directory / "finalizer.json"
    with (directory / ".finalizer.lock").open("w") as finalizer_lock:
        # One finalizer per run; an accidental second invocation cannot race writes.
        fcntl.flock(finalizer_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        status = {
            "pid": os.getpid(),
            "run_id": args.run_id,
            "status": "waiting_for_replay",
            "at": stamp(),
        }
        save_json(status_path, status)
        with (directory / ".lock").open("a") as computation_lock:
            fcntl.flock(computation_lock, fcntl.LOCK_EX)
            state = json.loads(manifest.read_text())
            incomplete = [
                stage
                for stage in FILES
                if state["artifacts"].get(stage, {}).get("status") != "complete"
            ]
        if incomplete:
            status.update(
                status="blocked",
                incomplete_stages=incomplete,
                error=state.get(
                    "last_error", "Computation stopped before all stages completed"
                ),
                at=stamp(),
            )
            save_json(status_path, status)
            print("Comparison blocked: computation incomplete", incomplete, flush=True)
            return
        replay = None
        try:
            replay = Replay(
                args.run_id, args.forge, accept_engine_change=args.accept_engine_change
            )
            status.update(status="comparing", at=stamp())
            save_json(status_path, status)
            replay.compare()
            status.update(
                status="complete", comparisons=replay.state["comparisons"], at=stamp()
            )
        except BaseException as error:
            status.update(status="failed", error=str(error), at=stamp())
            if replay is not None:
                replay.state.update(status="comparison_failed", last_error=str(error))
                replay.save()
            raise
        finally:
            save_json(status_path, status)
            if replay is not None:
                replay.write_report()


if __name__ == "__main__":
    main()

"""Opt-in full integration test; writes tiny isolated nscreen2_* fixture tables."""

import importlib.util
import os
import uuid
from pathlib import Path

import pytest

from replay.runner import Replay
from replay.sql import REMAINDER, RESULT, STAGED, literal


@pytest.mark.skipif(
    not os.environ.get("NSCREEN_WRITE_TEST"), reason="Opt-in sandbox write integration"
)
def test_full_pipeline_and_structural_comparison():
    path = (
        Path(__file__).resolve().parents[2]
        / "nscreen-graph-exploration/docs/provider_alignment_app/alignment_example.py"
    )
    spec = importlib.util.spec_from_file_location("pipeline_fixture", path)
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    expected = fixture.build_example()

    def query(rows, columns, types):
        encoded = []
        for row in rows:
            fields = []
            for col, kind in zip(columns, types):
                val = row.get(col)
                text = repr(val) if isinstance(val, float) else literal(val)
                fields.append(f"CAST({text} AS {kind})")
            encoded.append("(" + ",".join(fields) + ")")
        return (
            "SELECT * FROM (VALUES "
            + ",".join(encoded)
            + ") AS fixture("
            + ",".join(columns)
            + ")"
        )

    class FixtureReplay(Replay):
        def pin(self):
            pass

        def ref(self, table):
            return self.state["fixture_inputs"][table]

        def production(self, stage):
            reference = {"lrth": "raw1", "connected_ns": "connected"}.get(stage, stage)
            table = (
                REMAINDER
                if stage == "remainder"
                else RESULT
                if stage == "result"
                else STAGED
            )
            schema = self.state["snapshots"][table]["schema"]
            rows = [dict(row, day=self.day, stage=stage) for row in expected[reference]]
            return query(rows, [r[0] for r in schema], [r[1] for r in schema])

    forge = Path(os.environ.get("NSCREEN_FORGE", str(Path.home() / "forge")))
    replay = FixtureReplay("smoke_" + uuid.uuid4().hex[:12], forge, fixture.DAY)
    replay.state["fixture_inputs"] = {}
    cols = ["uid", "matchid", "householdid", "stable", "day"]
    types = ["varchar", "bigint", "bigint", "boolean", "varchar"]
    for table, rows in [
        ("liveramp_source", fixture.LIVERAMP),
        ("throtle_source", fixture.THROTLE),
        ("experian_source", fixture.EXPERIAN),
    ]:
        replay.state["fixture_inputs"][table] = replay.artifact(
            "input_" + table,
            query([dict(r, day=fixture.DAY) for r in rows], cols, types),
        )
    replay.state["fixture_inputs"]["nscreen_ipcollocation_daily_clean"] = (
        replay.artifact(
            "input_edges",
            query(
                [dict(r, day=fixture.DAY) for r in fixture.EDGES],
                ["uid1", "uid2", "weight", "samedevice", "differentusers", "day"],
                ["varchar", "varchar", "real", "boolean", "boolean", "varchar"],
            ),
        )
    )
    replay.state["fixture_inputs"]["nscreen_geo_daily_ua"] = replay.artifact(
        "input_geo",
        query(
            [dict(r, day=fixture.DAY) for r in fixture.GEO],
            ["uid", "geo", "day"],
            ["varchar", "varchar", "varchar"],
        ),
    )
    replay.save()
    replay.run(heap="512m")
    for table, stage in [
        (STAGED, "lrth"),
        (REMAINDER, "remainder"),
        (RESULT, "result"),
    ]:
        replay.state["snapshots"][table] = {
            "schema": replay.db.rows(
                f"DESCRIBE {replay.state['artifacts'][stage]['table']}"
            )
        }
    replay.compare(
        stages=[
            "lrth",
            "initial",
            "connected_ns",
            "stage1",
            "stage2",
            "remainder",
            "result",
        ]
    )
    comparisons = replay.state["comparisons"]
    assert all(
        comparisons[stage]["exact"]
        for stage in [
            "lrth",
            "initial",
            "connected_ns",
            "stage1",
            "stage2",
            "remainder",
        ]
    )
    assert comparisons["structural"]["equivalent"]
    count = replay.db.rows(
        f"SELECT count(*) FROM {replay.state['artifacts']['result']['table']}"
    )[0][0]
    assert count == len(expected["result"]) == 29
    print("End-to-end sandbox fixture:", replay.run_id)

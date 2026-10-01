import json

from replay import finalize
from replay.sql import FILES


def test_finalizer_refuses_partial_replay(tmp_path, monkeypatch):
    directory = tmp_path / "runs" / "partial"
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_text(
        json.dumps({"artifacts": {}, "last_error": "storage failure"})
    )
    monkeypatch.setattr(finalize, "ROOT", tmp_path)
    monkeypatch.setattr(finalize.sys, "argv", ["finalize", "--run-id", "partial"])
    finalize.main()
    state = json.loads((directory / "finalizer.json").read_text())
    assert state["status"] == "blocked"
    assert state["incomplete_stages"] == list(FILES)


def test_finalizer_compares_completed_replay(tmp_path, monkeypatch):
    directory = tmp_path / "runs" / "complete"
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_text(
        json.dumps({"artifacts": {stage: {"status": "complete"} for stage in FILES}})
    )
    calls = []

    class FakeReplay:
        def __init__(self, *args, **kwargs):
            self.state = {
                "comparisons": {
                    "result": {"exact": False},
                    "structural": {"equivalent": True},
                }
            }

        def compare(self):
            calls.append("compare")

        def write_report(self):
            calls.append("report")

    monkeypatch.setattr(finalize, "ROOT", tmp_path)
    monkeypatch.setattr(finalize, "Replay", FakeReplay)
    monkeypatch.setattr(finalize.sys, "argv", ["finalize", "--run-id", "complete"])
    finalize.main()
    state = json.loads((directory / "finalizer.json").read_text())
    assert state["status"] == "complete"
    assert not state["comparisons"]["result"]["exact"]
    assert calls == ["compare", "report"]

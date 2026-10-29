"""Safety regressions using simulated database state; no warehouse access."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "state_loader", ROOT / "build_state_daily.py"
)
loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loader)


class LoaderSafetyTests(unittest.TestCase):
    def test_partial_bucket_stops_before_any_write(self):
        expected = {("CA", 0): (100, "complete")}
        for actual in [
            {("CA", 0): (50, "partial")},
            {("CA", 0): (100, "wrong")},
            {("TX", 0): (1, "extra")},
        ]:
            with (
                self.subTest(actual=actual),
                patch.object(loader, "signatures", side_effect=[expected, actual]),
                patch.object(loader, "run") as write,
            ):
                with self.assertRaisesRegex(RuntimeError, "refusing append"):
                    loader.load_day(object(), "2026-10-20", "source", "mapping", 16)
                write.assert_not_called()

    def test_resume_skips_complete_and_loads_missing_null_state(self):
        expected = {("CA", 0): (100, "ca"), (None, 3): (2, "unknown")}
        with (
            patch.object(
                loader,
                "signatures",
                side_effect=[expected, {("CA", 0): (100, "ca")}, expected],
            ),
            patch.object(loader, "run") as write,
        ):
            loader.load_day(object(), "2026-10-20", "source", "mapping", 16)
            write.assert_called_once()
            sql = write.call_args.args[1]
            self.assertIn("state IS NULL", sql)
            self.assertIn("crc32(to_utf8(coalesce(uid, '')))", sql)
            self.assertNotIn("substr(uid", sql)
            self.assertNotIn("GROUP BY", sql)  # Preserve source duplicates.
            self.assertIn("LEFT JOIN mapping", sql)

    def test_ambiguous_write_stops_without_retry_or_delete(self):
        expected = {("CA", 0): (100, "ca"), ("TX", 1): (10, "tx")}
        with (
            patch.object(loader, "signatures", side_effect=[expected, {}]),
            patch.object(
                loader, "run", side_effect=ConnectionError("ambiguous")
            ) as write,
        ):
            with self.assertRaises(ConnectionError):
                loader.load_day(object(), "2026-10-20", "source", "mapping", 16)
            self.assertEqual(write.call_count, 1)
            self.assertTrue(write.call_args.args[1].startswith("INSERT"))

    def test_post_write_mismatch_fails(self):
        expected = {("CA", 0): (100, "ca")}
        with (
            patch.object(
                loader,
                "signatures",
                side_effect=[expected, {}, {("CA", 0): (99, "bad")}],
            ),
            patch.object(loader, "run"),
            self.assertRaisesRegex(RuntimeError, "Post-write"),
        ):
            loader.load_day(object(), "2026-10-20", "source", "mapping", 16)

    def test_fully_loaded_day_never_writes(self):
        expected = {("CA", 0): (100, "ca")}
        with (
            patch.object(loader, "signatures", return_value=expected),
            patch.object(loader, "run") as write,
        ):
            loader.load_day(object(), "2026-10-20", "source", "mapping", 16)
            write.assert_not_called()

    def test_mapping_creation_never_drops_existing_table(self):
        with patch.object(
            loader, "run", side_effect=RuntimeError("already exists")
        ) as write:
            with self.assertRaises(RuntimeError):
                loader.build_mapping(object())
            self.assertEqual(write.call_count, 1)
            self.assertNotIn("DROP", write.call_args.args[1])

    def test_cli_dry_run_never_bootstraps(self):
        with (
            patch.object(sys, "argv", ["loader", "--days", "2026-10-20", "--dry-run"]),
            patch.object(loader, "bootstrap") as connect,
        ):
            loader.main()
            connect.assert_not_called()

    def test_invalid_date_rejected_before_connection(self):
        with (
            patch.object(
                sys, "argv", ["loader", "--days", "2026-10-20'; DROP TABLE x"]
            ),
            patch.object(loader, "bootstrap") as connect,
        ):
            with self.assertRaises(SystemExit) as error:
                loader.main()
            self.assertEqual(error.exception.code, 2)
            connect.assert_not_called()


class EvidenceTests(unittest.TestCase):
    def run_finalizer(self, evidence):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base / "tools").mkdir()
            (base / "evidence").mkdir()
            script = base / "tools/finalize_seven_day_audit.py"
            script.write_text((ROOT / "tools/finalize_seven_day_audit.py").read_text())
            for name, value in evidence.items():
                (base / "evidence" / name).write_text(json.dumps(value))
            result = subprocess.run(
                [sys.executable, str(script)],
                capture_output=True,
                text=True,
                check=False,
            )
            output = base / "evidence/seven_day_validation.json"
            return result, json.loads(output.read_text()) if output.exists() else None

    def evidence(self):
        return {
            p.name: json.loads(p.read_text())
            for p in (ROOT / "evidence").glob("audit_7d_*.json")
        }

    def test_saved_audits_reproduce_manifest(self):
        result, manifest = self.run_finalizer(self.evidence())
        self.assertEqual(result.returncode, 0, result.stderr)
        saved = json.loads((ROOT / "evidence/seven_day_validation.json").read_text())
        for field in [
            "rows",
            "total_rows",
            "unmapped_state_rows",
            "source_snapshot",
            "status",
        ]:
            self.assertEqual(manifest[field], saved[field])

    def test_mismatched_checksum_never_publishes_manifest(self):
        evidence = self.evidence()
        evidence["audit_7d_target_2026-10-22_2026-10-22.json"]["rows"][0][-1] = "wrong"
        result, manifest = self.run_finalizer(evidence)
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(manifest)

    def test_missing_day_never_publishes_manifest(self):
        evidence = self.evidence()
        evidence["audit_7d_source_2026-10-20_2026-10-26.json"]["rows"].pop()
        result, manifest = self.run_finalizer(evidence)
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(manifest)


if __name__ == "__main__":
    unittest.main()

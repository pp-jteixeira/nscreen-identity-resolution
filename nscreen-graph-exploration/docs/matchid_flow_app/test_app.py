from pathlib import Path
from unittest.mock import patch

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest
from test_support import build_test_snapshot

APP = Path(__file__).with_name("streamlit_app.py")
TEST_DAY = "2026-09-17"


def available_days(*days: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "day": list(days),
            "state": ["complete"] * len(days),
            "missing_groups": [[] for _ in days],
        }
    )


def load_dashboard(snapshot: dict[str, object]) -> AppTest:
    st.cache_data.clear()
    with (
        patch("data.load_available_days", return_value=available_days(TEST_DAY)),
        patch("data.load_materialized_snapshot", return_value=snapshot),
    ):
        app = AppTest.from_file(str(APP), default_timeout=20).run()
        app.date_input[0].set_value(TEST_DAY).run()
        app.button[0].click().run()
    return app


def test_live_dashboard_renders_core_sections():
    app = load_dashboard(build_test_snapshot(TEST_DAY))

    assert not app.exception
    assert app.title[0].value == "NScreen matchid flow"
    assert len(app.metric) == 4
    assert len(app.get("plotly_chart")) == 2
    assert [tab.label for tab in app.tabs] == ["Matchids", "UIDs"]
    assert len(app.dataframe) == 0
    assert len(app.get("vega_lite_chart")) == 0
    assert all("demo" not in info.value.lower() for info in app.info)


def test_partial_materialized_day_shows_warning():
    snapshot = build_test_snapshot(TEST_DAY)
    snapshot["status"]["state"] = "partial"
    snapshot["status"]["missing_groups"] = ["stage_flow", "stage_reason"]
    snapshot["metrics"]["flow"] = snapshot["metrics"]["flow"].iloc[0:0]
    snapshot["metrics"]["stage_reason"] = snapshot["metrics"]["stage_reason"].iloc[
        0:0
    ]

    app = load_dashboard(snapshot)

    assert not app.exception
    assert "Snapshot incomplete" in app.warning[0].value
    assert "Cumulative flow requires" in app.info[0].value
    assert len(app.get("vega_lite_chart")) == 2


def test_empty_materialized_catalog_shows_message():
    st.cache_data.clear()
    with patch("data.load_available_days", return_value=pd.DataFrame()):
        app = AppTest.from_file(str(APP), default_timeout=20).run()
        app.button[0].click().run()

    assert not app.exception
    assert app.warning[0].value == "No pipeline snapshots are available."


def test_legacy_snapshot_reports_missing_uid_metrics():
    snapshot = build_test_snapshot(TEST_DAY)
    snapshot["metrics"]["uids"] = {
        key: frame.iloc[0:0] for key, frame in snapshot["metrics"]["uids"].items()
    }

    app = load_dashboard(snapshot)

    assert not app.exception
    assert len(app.get("plotly_chart")) == 1
    message = next(
        info.value for info in app.info if "UID analysis is incomplete" in info.value
    )
    for expected in (
        "LiveRamp source UIDs",
        "Throtle source UIDs",
        "Experian source UIDs",
        "Vendor alignment UIDs",
        "After LU / final UIDs",
        "stage attribution UIDs",
        "vendor and reason overlap UIDs",
    ):
        assert expected in message
    assert len(app.dataframe) == 0


def test_multiple_initial_reasons_render_with_warning():
    snapshot = build_test_snapshot(TEST_DAY)
    membership = snapshot["metrics"]["uids"]["membership"]
    membership.loc[membership.reason.eq("LR"), "reason"] = "multiple_reasons"

    app = load_dashboard(snapshot)

    assert not app.exception
    assert len(app.get("plotly_chart")) == 2
    assert any("Multiple initial reasons" in warning.value for warning in app.warning)


def test_uid_warning_identifies_only_missing_membership():
    snapshot = build_test_snapshot(TEST_DAY)
    membership = snapshot["metrics"]["uids"]["membership"]
    snapshot["metrics"]["uids"]["membership"] = membership.iloc[0:0]

    app = load_dashboard(snapshot)

    assert not app.exception
    message = next(
        info.value for info in app.info if "UID analysis is incomplete" in info.value
    )
    assert "vendor and reason overlap UIDs" in message
    assert "source UIDs" not in message
    assert "Vendor alignment UIDs" not in message
    assert "stage attribution UIDs" not in message
    assert len(app.get("plotly_chart")) == 1


def test_day_change_does_not_query():
    st.cache_data.clear()
    snapshot = build_test_snapshot(TEST_DAY)
    days = available_days("2026-09-18", TEST_DAY)

    with (
        patch("data.load_available_days", return_value=days),
        patch(
            "data.load_materialized_snapshot", return_value=snapshot
        ) as snapshot_loader,
    ):
        app = AppTest.from_file(str(APP), default_timeout=20).run()
        app.date_input[0].set_value(TEST_DAY).run()
        app.button[0].click().run()
        assert snapshot_loader.call_count == 1

        app.selectbox[0].set_value("2026-09-18").run()

    assert snapshot_loader.call_count == 1
    assert "Pipeline day changed" in app.warning[0].value

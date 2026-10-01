"""Deterministic fixtures shared by dashboard tests."""

from __future__ import annotations

from datetime import date

import pandas as pd
from data import iso_day, normalize_metrics


def build_test_snapshot(day: date | str) -> dict[str, object]:
    """Build one complete snapshot matching materialized Trino schemas."""
    selected_day = iso_day(day)
    rows = [
        ("source", "LiveRamp", None, 122_400_000, 811_000_000),
        ("source", "Throtle", None, 78_100_000, 292_000_000),
        ("source", "Experian", None, 94_700_000, 387_000_000),
        ("flow", "Vendor alignment", None, 206_200_000, 1_278_000_000),
        ("flow", "After IC stage 1", None, 206_200_000, 1_311_000_000),
        ("flow", "After IC stage 2", None, 206_200_000, 1_319_000_000),
        ("flow", "After LU / final", None, 219_500_000, 1_333_000_000),
        ("stage_reason", "initial", "LR", 64_900_000, 602_000_000),
        ("stage_reason", "initial", "LRTH", 20_000_000, 224_000_000),
        ("stage_reason", "initial", "LREX", 18_000_000, 124_000_000),
        ("stage_reason", "initial", "LRTHEX", 19_000_000, 102_000_000),
        ("stage_reason", "initial", "TH", 27_100_000, 82_000_000),
        ("stage_reason", "initial", "THEX", 11_500_000, 68_000_000),
        ("stage_reason", "initial", "EX", 45_700_000, 268_000_000),
        ("stage_reason", "stage1", "IC", 34_000_000, 33_000_000),
        ("stage_reason", "stage2", "IC", 8_000_000, 8_000_000),
        ("stage_reason", "louvain", "LU", 13_300_000, 14_000_000),
        ("final_reason", "LR", None, 64_900_000, 602_000_000),
        ("final_reason", "EX", None, 45_700_000, 268_000_000),
        ("final_reason", "IC", None, 42_000_000, 41_000_000),
        ("final_reason", "LRTH", None, 20_000_000, 224_000_000),
        ("final_reason", "LREX", None, 18_000_000, 124_000_000),
        ("final_reason", "LRTHEX", None, 19_000_000, 102_000_000),
        ("final_reason", "TH", None, 27_100_000, 82_000_000),
        ("final_reason", "THEX", None, 11_500_000, 68_000_000),
        ("final_reason", "LU", None, 13_300_000, 14_000_000),
    ]
    uid_reasons = dict(
        zip(
            ["LR", "LRTH", "LREX", "LRTHEX", "TH", "THEX", "EX"],
            [400, 100, 80, 40, 100, 30, 250],
            strict=True,
        )
    )
    uid_rows = [
        ("source", "LiveRamp", None, 811),
        ("source", "Throtle", None, 292),
        ("source", "Experian", None, 387),
        ("flow", "Vendor alignment", None, 1000),
        ("flow", "After LU / final", None, 1055),
        *[
            ("stage_reason", "initial", reason, value)
            for reason, value in uid_reasons.items()
        ],
        ("stage_reason", "stage1", "IC", 33),
        ("stage_reason", "stage2", "IC", 8),
        ("stage_reason", "louvain", "LU", 14),
    ]
    membership = []
    reason_masks = {
        "LR": 1,
        "LRTH": 3,
        "LREX": 5,
        "LRTHEX": 7,
        "TH": 2,
        "THEX": 6,
        "EX": 4,
    }
    for reason, value in uid_reasons.items():
        membership.append((reason, reason_masks[reason], value))
    membership.extend(("unrepresented", bit, 10) for bit in (1, 2, 4))
    vendor_masks = {"LiveRamp": 1, "Throtle": 2, "Experian": 4}
    uid_rows = [
        (
            kind,
            first_dimension,
            second_dimension,
            sum(
                value
                for _, mask, value in membership
                if mask & vendor_masks[first_dimension]
            ),
        )
        if kind == "source"
        else (kind, first_dimension, second_dimension, count)
        for kind, first_dimension, second_dimension, count in uid_rows
    ]
    rows.extend(
        ("uid_membership", reason, str(mask), count * 1_000_000, count * 1_000_000)
        for reason, mask, count in membership
    )
    rows.extend(
        (f"uid_{kind}", first_dimension, second_dimension, count * 1_000_000, count * 1_000_000)
        for kind, first_dimension, second_dimension, count in uid_rows
    )
    raw = pd.DataFrame(
        rows,
        columns=["metric_type", "dimension_1", "dimension_2", "matchids", "rows"],
    )
    status = {
        "day": selected_day,
        "state": "complete",
        "available_groups": [
            "source_liveramp",
            "source_throtle",
            "source_experian",
            "stage_flow",
            "stage_reason",
            "final",
        ],
        "missing_groups": [],
        "started_at": None,
        "completed_at": None,
        "error_message": None,
    }
    return {"status": status, "metrics": normalize_metrics(raw)}

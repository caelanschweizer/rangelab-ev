from __future__ import annotations

import csv

from rangelab.evaluation import evaluate_csv
from rangelab.synthetic import HEADERS, generate_rows


def test_evaluation_reproduces_diagnostics(tmp_path) -> None:
    path = tmp_path / "synthetic_fixture.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(generate_rows(trips=10, seed=2018))
    report = evaluate_csv(path)
    assert report["synthetic"] is True
    assert report["trip_count"] == 10
    assert report["point_count"] > 700
    assert report["model_diagnostics"]["eligible_trip_count"] == 10
    assert report["model_diagnostics"]["evaluated_trip_count"] == 2

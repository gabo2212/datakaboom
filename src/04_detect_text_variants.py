from __future__ import annotations

from pathlib import Path
import sys
from collections import Counter

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parent))

from project_utils import (  # noqa: E402
    DEFAULT_VARIANTS_REPORT,
    choose_canonical_label,
    collapse_repeated_segments,
    compact_text,
    ensure_raw_csv,
    fuzzy_similarity_score,
    is_uqam_accept_alias,
    is_uqam_review_candidate,
    normalize_text,
    write_dataframe,
)

import pandas as pd


TARGET_COLUMN = "recipient_legal_name"


def resolve_target_column(csv_path: Path, preferred_column: str = TARGET_COLUMN) -> str:
    header = pd.read_csv(csv_path, nrows=0, low_memory=False).columns.tolist()
    if preferred_column in header:
        return preferred_column
    if header:
        return header[0]
    raise ValueError("The source CSV does not contain any columns.")


def count_values(csv_path: Path, column: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for chunk in pd.read_csv(
        csv_path,
        usecols=[column],
        chunksize=50_000,
        dtype=str,
        keep_default_na=True,
        low_memory=False,
    ):
        series = chunk[column].dropna().astype(str)
        counts.update(series.tolist())
    return counts


def build_variants_report(csv_path: Path, column: str) -> pd.DataFrame:
    counts = count_values(csv_path, column)
    values_df = pd.DataFrame(
        {
            "original_value": list(counts.keys()),
            "count": list(counts.values()),
        }
    )
    values_df["collapsed_value"] = values_df["original_value"].map(collapse_repeated_segments)
    values_df["normalized_value"] = values_df["collapsed_value"].map(normalize_text)
    values_df["compact_value"] = values_df["normalized_value"].map(compact_text)

    compact_to_originals = (
        values_df.groupby("compact_value")["original_value"].apply(list).to_dict()
    )
    compact_group_sizes = (
        values_df.groupby("compact_value")["original_value"].nunique().to_dict()
    )

    records: list[dict[str, object]] = []
    for row in values_df.itertuples(index=False):
        original_value = row.original_value
        normalized_value = row.normalized_value
        compact_value = row.compact_value
        count = int(row.count)

        group_size = int(compact_group_sizes.get(compact_value, 1))
        if not normalized_value:
            continue

        accepted_alias = is_uqam_accept_alias(original_value)
        review_alias = is_uqam_review_candidate(original_value)
        if not accepted_alias and group_size <= 1 and not review_alias:
            continue

        if accepted_alias:
            suggested_group = "UQAM"
            similarity_score = 100
            decision = "accepted"
        elif group_size > 1:
            originals = compact_to_originals.get(compact_value, [original_value])
            if any(is_uqam_accept_alias(value) for value in originals):
                suggested_group = "UQAM"
            else:
                suggested_group = choose_canonical_label(originals, counts)
            similarity_score = fuzzy_similarity_score(original_value, suggested_group)
            decision = _decision_from_score(similarity_score)
        else:
            suggested_group = "UQAM"
            similarity_score = fuzzy_similarity_score(original_value, suggested_group)
            decision = _decision_from_score(similarity_score)

        records.append(
            {
                "original_value": original_value,
                "normalized_value": normalized_value,
                "suggested_group": suggested_group,
                "similarity_score": similarity_score,
                "count": count,
                "decision": decision,
            }
        )

    report = pd.DataFrame(records)
    if not report.empty:
        decision_order = pd.Categorical(
            report["decision"],
            categories=["accepted", "review", "rejected"],
            ordered=True,
        )
        report = report.assign(_decision_order=decision_order).sort_values(
            ["_decision_order", "count", "original_value"],
            ascending=[True, False, True],
        )
        report = report.drop(columns=["_decision_order"]).reset_index(drop=True)
    return report


def _decision_from_score(score: int) -> str:
    if score >= 95:
        return "accepted"
    if score >= 80:
        return "review"
    return "rejected"


def main() -> None:
    csv_path = ensure_raw_csv()
    column = resolve_target_column(csv_path)
    report = build_variants_report(csv_path, column)
    write_dataframe(DEFAULT_VARIANTS_REPORT, report)
    print(f"Variant report written to {DEFAULT_VARIANTS_REPORT}")
    print(f"Candidate values found: {len(report)}")
    print(f"Target column: {column}")


if __name__ == "__main__":
    main()

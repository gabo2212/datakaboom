from __future__ import annotations

from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parent))

from project_utils import (  # noqa: E402
    DEFAULT_DUPLICATES_REPORT,
    DEFAULT_FINAL_SUMMARY,
    DEFAULT_MAPPING_REPORT,
    DEFAULT_MISSING_VALUES_REPORT,
    DEFAULT_PROCESSED_CSV,
    DEFAULT_RAW_CSV,
    count_csv_rows,
    dataframe_to_markdown,
    ensure_raw_csv,
    write_text,
)

import pandas as pd


TARGET_COLUMN = "recipient_legal_name"
TARGET_CLEAN_COLUMN = "recipient_legal_name_clean"


def count_unique_values(csv_path: Path, column: str, *, chunksize: int = 50_000) -> int:
    uniques: set[str] = set()
    for chunk in pd.read_csv(
        csv_path,
        usecols=[column],
        chunksize=chunksize,
        dtype=str,
        keep_default_na=True,
        low_memory=False,
    ):
        series = chunk[column].dropna().astype(str)
        uniques.update(series.tolist())
    return len(uniques)


def count_cleaning_changes(csv_path: Path, raw_column: str, clean_column: str) -> int:
    changed = 0
    for chunk in pd.read_csv(
        csv_path,
        usecols=[raw_column, clean_column],
        chunksize=50_000,
        dtype=str,
        keep_default_na=True,
        low_memory=False,
    ):
        raw = chunk[raw_column]
        clean = chunk[clean_column]
        mask = raw.notna() & clean.notna() & (raw != clean)
        changed += int(mask.sum())
    return changed


def summarize_duplicates(report_path: Path) -> tuple[pd.DataFrame, int]:
    if not report_path.exists():
        return pd.DataFrame(columns=["duplicate_type", "duplicate_groups", "duplicate_rows_flagged"]), 0

    report = pd.read_csv(report_path, dtype=str, keep_default_na=True, low_memory=False)
    if report.empty:
        return pd.DataFrame(columns=["duplicate_type", "duplicate_groups", "duplicate_rows_flagged"]), 0

    report["duplicate_count"] = pd.to_numeric(report["duplicate_count"], errors="coerce").fillna(0).astype(int)
    summary = (
        report.groupby("duplicate_type", as_index=False)
        .agg(
            duplicate_groups=("duplicate_type", "size"),
            duplicate_rows_flagged=("duplicate_count", lambda s: int((s - 1).clip(lower=0).sum())),
        )
        .sort_values("duplicate_rows_flagged", ascending=False)
    )
    total_flagged = int(summary["duplicate_rows_flagged"].sum()) if not summary.empty else 0
    return summary.reset_index(drop=True), total_flagged


def summarize_mapping(report_path: Path) -> tuple[pd.DataFrame, int]:
    if not report_path.exists():
        return pd.DataFrame(columns=["status", "count"]), 0

    report = pd.read_csv(report_path, dtype=str, keep_default_na=True, low_memory=False)
    if report.empty:
        return pd.DataFrame(columns=["status", "count"]), 0

    summary = report.groupby("status", as_index=False).size().rename(columns={"size": "count"})
    review_count = int(summary.loc[summary["status"] == "review", "count"].sum()) if not summary.empty else 0
    return summary.sort_values("count", ascending=False).reset_index(drop=True), review_count


def build_summary() -> str:
    raw_csv = ensure_raw_csv()
    processed_csv = DEFAULT_PROCESSED_CSV

    raw_rows = count_csv_rows(raw_csv)
    raw_columns = len(pd.read_csv(raw_csv, nrows=0, low_memory=False).columns)
    raw_unique = count_unique_values(raw_csv, TARGET_COLUMN)

    missing_report = pd.read_csv(DEFAULT_MISSING_VALUES_REPORT, dtype=str, keep_default_na=True, low_memory=False)
    missing_report["valeurs_manquantes"] = pd.to_numeric(
        missing_report["valeurs_manquantes"], errors="coerce"
    ).fillna(0).astype(int)
    missing_report["pourcentage_manquant"] = pd.to_numeric(
        missing_report["pourcentage_manquant"], errors="coerce"
    ).fillna(0).round(2)

    duplicates_summary, duplicate_rows_flagged = summarize_duplicates(DEFAULT_DUPLICATES_REPORT)
    mapping_summary, review_count = summarize_mapping(DEFAULT_MAPPING_REPORT)

    if processed_csv.exists():
        clean_unique = count_unique_values(processed_csv, TARGET_CLEAN_COLUMN)
        corrections_applied = count_cleaning_changes(processed_csv, TARGET_COLUMN, TARGET_CLEAN_COLUMN)
    else:
        clean_unique = 0
        corrections_applied = 0

    summary_sections = [
        "# Final Summary",
        "",
        "## Dataset Overview",
        f"- Original rows: {raw_rows:,}",
        f"- Columns: {raw_columns}",
        f"- Unique raw organization names: {raw_unique:,}",
        f"- Unique cleaned organization names: {clean_unique:,}",
        "",
        "## Missing Values",
        dataframe_to_markdown(missing_report, index=False),
        "",
        "## Duplicate Detection",
        dataframe_to_markdown(duplicates_summary, index=False),
        f"- Total duplicate rows flagged across rules: {duplicate_rows_flagged:,}",
        "",
        "## Cleaning Mapping",
        dataframe_to_markdown(mapping_summary, index=False),
        f"- Corrections applied in the cleaned file: {corrections_applied:,}",
        f"- Corrections left for review: {review_count:,}",
        "",
        "## Limitations",
        "- The raw workbook was converted to a CSV snapshot before chunked processing.",
        "- Review rows were intentionally not applied to avoid incorrect automated merges.",
        "- Duplicate rules can overlap, so duplicate counts are reported by rule.",
        "- Contextual organization names that merely contain UQAM were treated conservatively.",
        "",
        "## Recommendations",
        "- Manually validate the review rows in `entity_cleaning_mapping.csv`.",
        "- Check the largest duplicate groups before downstream analysis or modeling.",
        "- Re-run the pipeline if the raw workbook changes.",
        "",
    ]
    return "\n".join(summary_sections)


def main() -> None:
    summary = build_summary()
    write_text(DEFAULT_FINAL_SUMMARY, summary)
    print(f"Final summary written to {DEFAULT_FINAL_SUMMARY}")


if __name__ == "__main__":
    main()

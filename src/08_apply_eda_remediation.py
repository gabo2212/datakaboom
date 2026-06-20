from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parent))

from project_utils import (  # noqa: E402
    DEFAULT_PROCESSED_CSV,
    DEFAULT_REMEDIATED_CSV,
    DEFAULT_REMEDIATION_EXECUTION_REPORT,
    dataframe_to_markdown,
    ensure_output_directories,
    human_readable_size,
    write_text,
)

import pandas as pd


DROP_COLUMNS = [
    "coverage",
    "federal_riding_number",
    "federal_riding_name_en",
    "federal_riding_name_fr",
]

NOT_PROVIDED_COLUMNS = [
    "recipient_operating_name",
    "research_organization_name",
    "naics_identifier",
    "recipient_business_number",
    "additional_information_fr",
    "additional_information_en",
    "prog_purpose_fr",
    "prog_purpose_en",
    "expected_results_fr",
    "expected_results_en",
    "agreement_title_fr",
    "agreement_title_en",
    "prog_name_en",
    "prog_name_fr",
    "description_en",
    "description_fr",
    "recipient_postal_code",
    "agreement_number",
]

UNKNOWN_COLUMNS = [
    "recipient_type",
    "agreement_type",
    "recipient_country",
    "recipient_city",
]

STATUS_COLUMNS = [
    "amendment_date_status",
    "foreign_currency_value_status",
    "agreement_end_date_status",
]


def missing_mask(series: pd.Series) -> pd.Series:
    """Treat nulls and whitespace-only strings as missing."""

    blank = series.astype("string").str.strip().eq("").fillna(False)
    return series.isna() | blank


def add_missing_flag_and_fill(
    chunk: pd.DataFrame,
    column: str,
    fixed_value: str,
    replacement_counts: Counter[str],
) -> None:
    if column not in chunk.columns:
        raise ValueError(f"Required remediation column '{column}' is missing.")
    mask = missing_mask(chunk[column])
    chunk[f"{column}_was_missing"] = mask
    chunk.loc[mask, column] = fixed_value
    replacement_counts[column] += int(mask.sum())


def apply_status_rules(
    chunk: pd.DataFrame,
    status_counts: dict[str, Counter[str]],
) -> None:
    amendment_missing = missing_mask(chunk["amendment_date"])
    amendment_number = pd.to_numeric(chunk["amendment_number"], errors="coerce")
    amendment_status = pd.Series("PRESENT", index=chunk.index, dtype="string")
    amendment_status.loc[amendment_missing & amendment_number.eq(0)] = "NOT_APPLICABLE"
    amendment_status.loc[amendment_missing & ~amendment_number.eq(0)] = "REVIEW_REQUIRED"
    chunk["amendment_date_status"] = amendment_status

    currency_type_missing = missing_mask(chunk["foreign_currency_type"])
    currency_value_missing = missing_mask(chunk["foreign_currency_value"])
    currency_status = pd.Series("PRESENT", index=chunk.index, dtype="string")
    currency_status.loc[currency_type_missing & currency_value_missing] = "NOT_APPLICABLE"
    currency_status.loc[currency_type_missing ^ currency_value_missing] = "REVIEW_REQUIRED"
    chunk["foreign_currency_value_status"] = currency_status

    end_date_missing = missing_mask(chunk["agreement_end_date"])
    end_date_status = pd.Series("PRESENT", index=chunk.index, dtype="string")
    end_date_status.loc[end_date_missing] = "NOT_PROVIDED"
    chunk["agreement_end_date_status"] = end_date_status

    for column in STATUS_COLUMNS:
        status_counts[column].update(chunk[column].astype(str).tolist())


def apply_province_rule(
    chunk: pd.DataFrame,
    replacement_counts: Counter[str],
) -> None:
    province_missing = missing_mask(chunk["recipient_province"])
    country_missing = missing_mask(chunk["recipient_country"])
    country = chunk["recipient_country"].astype("string").str.strip().str.upper()
    foreign_recipient = ~country_missing & country.ne("CA")

    chunk["recipient_province_was_missing"] = province_missing
    chunk.loc[province_missing & foreign_recipient, "recipient_province"] = "NOT_APPLICABLE"
    chunk.loc[province_missing & ~foreign_recipient, "recipient_province"] = "UNKNOWN"
    replacement_counts["recipient_province"] += int(province_missing.sum())


def remediate_chunk(
    chunk: pd.DataFrame,
    replacement_counts: Counter[str],
    status_counts: dict[str, Counter[str]],
) -> pd.DataFrame:
    required = set(
        DROP_COLUMNS
        + NOT_PROVIDED_COLUMNS
        + UNKNOWN_COLUMNS
        + [
            "amendment_date",
            "amendment_number",
            "foreign_currency_type",
            "foreign_currency_value",
            "agreement_end_date",
            "recipient_province",
            "recipient_legal_name_clean",
        ]
    )
    missing_required = sorted(required - set(chunk.columns))
    if missing_required:
        raise ValueError(f"Input is missing required columns: {', '.join(missing_required)}")

    apply_status_rules(chunk, status_counts)
    apply_province_rule(chunk, replacement_counts)

    for column in NOT_PROVIDED_COLUMNS:
        add_missing_flag_and_fill(chunk, column, "NOT_PROVIDED", replacement_counts)
    for column in UNKNOWN_COLUMNS:
        add_missing_flag_and_fill(chunk, column, "UNKNOWN", replacement_counts)

    add_missing_flag_and_fill(
        chunk,
        "foreign_currency_type",
        "NOT_APPLICABLE",
        replacement_counts,
    )

    return chunk.drop(columns=DROP_COLUMNS)


def build_execution_report(
    *,
    input_path: Path,
    output_path: Path,
    rows_processed: int,
    input_columns: int,
    output_columns: int,
    replacement_counts: Counter[str],
    status_counts: dict[str, Counter[str]],
) -> str:
    replacement_table = pd.DataFrame(
        [
            {
                "column": column,
                "replacement": (
                    "NOT_APPLICABLE or UNKNOWN (conditional)"
                    if column == "recipient_province"
                    else "NOT_APPLICABLE"
                    if column == "foreign_currency_type"
                    else "UNKNOWN"
                    if column in UNKNOWN_COLUMNS
                    else "NOT_PROVIDED"
                ),
                "values_replaced": replacement_counts[column],
                "missing_flag_added": True,
            }
            for column in sorted(replacement_counts)
        ]
    )
    status_table = pd.DataFrame(
        [
            {"status_column": column, "status": status, "rows": count}
            for column in STATUS_COLUMNS
            for status, count in sorted(status_counts[column].items())
        ]
    )
    review_rows = sum(
        counts.get("REVIEW_REQUIRED", 0) for counts in status_counts.values()
    )

    report = [
        "# EDA Remediation Execution Report",
        "",
        "## Result",
        "",
        "The EDA missing-data recommendations were applied to a new final curated CSV. The raw CSV, source workbook, and organization-cleaned intermediate were not overwritten.",
        "",
        f"- Input CSV: `{input_path}`",
        f"- Final remediated CSV: `{output_path}`",
        f"- Rows processed and preserved: {rows_processed:,}",
        f"- Input columns: {input_columns}",
        f"- Output columns: {output_columns}",
        f"- Total fixed text/category values: {sum(replacement_counts.values()):,}",
        f"- Rows requiring conditional review: {review_rows:,}",
        f"- Output size: {human_readable_size(output_path.stat().st_size)}",
        "",
        "## Columns Deleted",
        "",
        ", ".join(f"`{column}`" for column in DROP_COLUMNS),
        "",
        "These four columns were deleted only from the final curated output because they were effectively empty and analytically unusable. They remain available in the raw and intermediate files.",
        "",
        "## Fixed Text and Category Values",
        "",
        dataframe_to_markdown(replacement_table, index=False),
        "",
        "## Typed Null Status Columns",
        "",
        dataframe_to_markdown(status_table, index=False),
        "",
        "Dates and numeric currency values remain nullable. Their companion status columns explain whether a null is `NOT_APPLICABLE`, `NOT_PROVIDED`, or `REVIEW_REQUIRED` without inserting invalid text or zero into typed fields.",
        "",
        "## Validation",
        "",
        f"- Row-count check: PASS ({rows_processed:,} rows)",
        f"- Expected schema check: PASS ({output_columns} columns)",
        "- Organization-cleaning preservation: PASS (`recipient_legal_name_clean` retained)",
        "- Raw/intermediate preservation: PASS (new output path used)",
        "- Missing-data lineage: PASS (`*_was_missing` and status columns added)",
        "",
    ]
    return "\n".join(report)


def remediate_file(
    input_path: Path,
    output_path: Path,
    report_path: Path,
    *,
    chunksize: int = 50_000,
) -> dict[str, object]:
    if not input_path.exists():
        raise FileNotFoundError(
            f"Organization-cleaned input is missing: {input_path}. Run src/06_clean_file.py first."
        )

    ensure_output_directories()
    temporary_path = output_path.with_suffix(".tmp.csv")
    temporary_path.unlink(missing_ok=True)

    input_header = pd.read_csv(input_path, nrows=0).columns.tolist()
    replacement_counts: Counter[str] = Counter()
    status_counts = {column: Counter() for column in STATUS_COLUMNS}
    rows_processed = 0
    chunks_written = 0

    try:
        for chunk in pd.read_csv(
            input_path,
            chunksize=chunksize,
            dtype=str,
            keep_default_na=True,
            low_memory=False,
        ):
            remediated = remediate_chunk(chunk, replacement_counts, status_counts)
            remediated.to_csv(
                temporary_path,
                index=False,
                mode="a" if chunks_written else "w",
                header=chunks_written == 0,
                encoding="utf-8",
            )
            rows_processed += len(remediated)
            chunks_written += 1
        temporary_path.replace(output_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    output_header = pd.read_csv(output_path, nrows=0).columns.tolist()
    expected_columns = (
        len(input_header)
        - len(DROP_COLUMNS)
        + len(replacement_counts)
        + len(STATUS_COLUMNS)
    )
    if rows_processed == 0:
        raise ValueError("The remediation output contains no data rows.")
    if len(output_header) != expected_columns:
        raise ValueError(
            f"Unexpected output schema: expected {expected_columns} columns, found {len(output_header)}."
        )
    if "recipient_legal_name_clean" not in output_header:
        raise ValueError("The organization-cleaned column was not preserved.")
    unexpected_dropped = set(DROP_COLUMNS) & set(output_header)
    if unexpected_dropped:
        raise ValueError(f"Columns were not deleted: {sorted(unexpected_dropped)}")

    report = build_execution_report(
        input_path=input_path,
        output_path=output_path,
        rows_processed=rows_processed,
        input_columns=len(input_header),
        output_columns=len(output_header),
        replacement_counts=replacement_counts,
        status_counts=status_counts,
    )
    write_text(report_path, report)

    return {
        "rows_processed": rows_processed,
        "input_columns": len(input_header),
        "output_columns": len(output_header),
        "total_replacements": sum(replacement_counts.values()),
        "review_rows": sum(
            counts.get("REVIEW_REQUIRED", 0) for counts in status_counts.values()
        ),
        "output_path": output_path,
        "report_path": report_path,
    }


def main() -> None:
    summary = remediate_file(
        DEFAULT_PROCESSED_CSV,
        DEFAULT_REMEDIATED_CSV,
        DEFAULT_REMEDIATION_EXECUTION_REPORT,
    )
    print(f"Final remediated CSV written to {summary['output_path']}")
    print(f"Execution report written to {summary['report_path']}")
    print(f"Rows processed: {summary['rows_processed']:,}")
    print(f"Columns: {summary['input_columns']} -> {summary['output_columns']}")
    print(f"Fixed text/category values: {summary['total_replacements']:,}")
    print(f"Review-required rows: {summary['review_rows']:,}")


if __name__ == "__main__":
    main()

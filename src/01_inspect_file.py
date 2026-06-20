from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parent))

from project_utils import (  # noqa: E402
    DEFAULT_EDA_REPORT,
    DEFAULT_SOURCE_SHEET,
    DEFAULT_RAW_CSV,
    count_csv_rows,
    dataframe_to_markdown,
    discover_workbook_path,
    ensure_raw_csv,
    file_size_bytes,
    human_readable_size,
    infer_column_roles,
    iter_csv_chunks,
)

import pandas as pd


MISSING_DATA_POLICY_GROUPS = [
    {
        "columns": (
            "coverage",
            "federal_riding_number",
            "federal_riding_name_en",
            "federal_riding_name_fr",
        ),
        "decision": "DELETE COLUMN",
        "future_rule": "Remove from the analytical table; retain only in the immutable raw snapshot.",
        "reason": "Essentially empty and not reliable enough for analysis or imputation.",
    },
    {
        "columns": ("amendment_date",),
        "decision": "SET FIXED VALUE CONDITIONALLY",
        "future_rule": (
            "When amendment_number = 0, expose NOT_APPLICABLE in a text/status field. "
            "If amendment_number > 0 and the date is missing, reject the row for data-quality review."
        ),
        "reason": "A missing date is expected for a non-amendment but invalid for an amendment.",
    },
    {
        "columns": ("recipient_operating_name", "research_organization_name"),
        "decision": "SET FIXED VALUE",
        "future_rule": "Set missing text to NOT_PROVIDED and add a Boolean was_missing flag.",
        "reason": "These optional names remain useful when supplied; inventing a name would create a false entity.",
    },
    {
        "columns": ("foreign_currency_type",),
        "decision": "SET FIXED VALUE",
        "future_rule": "Set missing text to NOT_APPLICABLE; do not assume CAD from frequency alone.",
        "reason": "The field is an optional currency detail and mode imputation could misclassify an agreement.",
    },
    {
        "columns": ("foreign_currency_value",),
        "decision": "SET FIXED STATUS VALUE",
        "future_rule": (
            "Keep the numeric value NULL and set foreign_currency_value_status to NOT_APPLICABLE. "
            "Never replace it with 0."
        ),
        "reason": "Zero is a real monetary amount; a status field preserves numeric type and null meaning.",
    },
    {
        "columns": ("naics_identifier", "recipient_business_number"),
        "decision": "SET FIXED VALUE",
        "future_rule": "Store as text and set missing identifiers to NOT_PROVIDED with a was_missing flag.",
        "reason": "Identifiers are categorical keys, so mean, median, and mode imputation are invalid.",
    },
    {
        "columns": ("recipient_type", "agreement_type"),
        "decision": "SET FIXED VALUE",
        "future_rule": "Set missing category codes to UNKNOWN and retain the original raw value separately.",
        "reason": "UNKNOWN is an explicit controlled category and avoids guessing a business classification.",
    },
    {
        "columns": (
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
        ),
        "decision": "SET FIXED VALUE",
        "future_rule": "Set missing narrative text to NOT_PROVIDED and add a was_missing flag.",
        "reason": "Free text and bilingual content cannot be reconstructed reliably with statistical imputation.",
    },
    {
        "columns": ("recipient_postal_code", "agreement_number"),
        "decision": "SET FIXED VALUE",
        "future_rule": "Store as text and set missing values to NOT_PROVIDED with a was_missing flag.",
        "reason": "These are identifiers, not measurements; fabricated or modal values would create false matches.",
    },
    {
        "columns": ("agreement_end_date",),
        "decision": "SET FIXED STATUS VALUE",
        "future_rule": (
            "Keep the date NULL and set agreement_end_date_status to NOT_PROVIDED. "
            "Do not copy the start date or invent a duration."
        ),
        "reason": "A sentinel string would break the date type and a guessed end date would distort durations.",
    },
    {
        "columns": ("recipient_province",),
        "decision": "SET FIXED VALUE CONDITIONALLY",
        "future_rule": (
            "Set NOT_APPLICABLE when recipient_country is not CA; otherwise set UNKNOWN. "
            "Add a was_missing flag."
        ),
        "reason": "Province is structurally inapplicable outside Canada but unknown for an incomplete Canadian address.",
    },
    {
        "columns": ("recipient_country", "recipient_city"),
        "decision": "SET FIXED VALUE",
        "future_rule": "Set missing text to UNKNOWN and add a was_missing flag; do not use the most frequent value.",
        "reason": "Even at low missingness, mode imputation can assign a real agreement to the wrong location.",
    },
]


def missing_value_profile(csv_path: Path) -> pd.DataFrame:
    """Measure null and whitespace-only values without loading the full CSV."""

    missing_counts: Counter[str] = Counter()
    total_rows = 0
    columns: list[str] = []

    for chunk in iter_csv_chunks(csv_path, chunksize=50_000):
        if not columns:
            columns = list(chunk.columns)
            missing_counts.update({column: 0 for column in columns})
        whitespace = chunk.apply(lambda col: col.astype(str).str.match(r"^\s*$", na=False))
        chunk = chunk.mask(whitespace, pd.NA)
        total_rows += len(chunk)
        missing_counts.update(
            {column: int(count) for column, count in chunk.isna().sum().items()}
        )

    rows = [
        {
            "column": column,
            "missing_count": missing_counts[column],
            "missing_percent": round(missing_counts[column] / total_rows * 100, 2),
        }
        for column in columns
        if missing_counts[column] > 0
    ]
    return pd.DataFrame(rows).sort_values(
        ["missing_percent", "missing_count"], ascending=False
    )


def build_missing_data_plan(profile: pd.DataFrame) -> pd.DataFrame:
    """Attach a concrete, semantics-aware treatment to every incomplete column."""

    policy_by_column = {
        column: policy
        for policy in MISSING_DATA_POLICY_GROUPS
        for column in policy["columns"]
    }
    rows = []
    for record in profile.to_dict(orient="records"):
        column = str(record["column"])
        policy = policy_by_column.get(
            column,
            {
                "decision": "SET FIXED VALUE",
                "future_rule": "Set missing text to UNKNOWN and add a was_missing flag.",
                "reason": "No trustworthy deterministic source is available for imputation.",
            },
        )
        rows.append(
            {
                "column": column,
                "missing": f"{int(record['missing_count']):,} ({record['missing_percent']:.2f}%)",
                "recommended decision": policy["decision"],
                "exact future treatment": policy["future_rule"],
                "business rationale": policy["reason"],
            }
        )
    return pd.DataFrame(rows)


def inspect_file(csv_path: Path) -> dict[str, object]:
    sample = pd.read_csv(csv_path, nrows=1000, low_memory=False)
    roles = infer_column_roles(sample)
    row_count = count_csv_rows(csv_path)
    missing_profile = missing_value_profile(csv_path)
    missing_plan = build_missing_data_plan(missing_profile)

    columns_df = pd.DataFrame(
        {
            "column": sample.columns,
            "detected_dtype": sample.dtypes.astype(str).tolist(),
        }
    )

    role_df = pd.DataFrame(
        [
            {"category": "numeric", "columns": ", ".join(roles["numeric"]) or "None"},
            {"category": "text", "columns": ", ".join(roles["text"]) or "None"},
            {"category": "date", "columns": ", ".join(roles["date"]) or "None"},
        ]
    )

    report = [
        "# EDA Report",
        "",
        "## Professional Recommendation: How to Repair the Dataset",
        "",
        "The dataset should be repaired through a controlled transformation that creates a new curated file while preserving the original workbook and raw CSV unchanged. The first step is to remove `coverage`, `federal_riding_number`, `federal_riding_name_en`, and `federal_riding_name_fr` from the curated analytical dataset because they are effectively empty and cannot support reliable analysis. No other column should be deleted solely because it has many missing values; several sparse columns still contain valid business information when populated.",
        "",
        "For the retained columns, missing text and identifier fields should be standardized with explicit controlled values instead of guessed values. Use `UNKNOWN` when a value should exist but is not known, `NOT_PROVIDED` when the source did not supply an optional value, and `NOT_APPLICABLE` when the field does not apply to that record. Add a `*_was_missing` Boolean flag before replacing each missing text value so analysts can distinguish original values from cleaning placeholders. Do not use averages, medians, modes, copied values, or generated text for identifiers, locations, categories, bilingual descriptions, or organization names because those methods would fabricate business facts.",
        "",
        "Numeric and date columns must remain nullable rather than receiving text placeholders or zero. Their missing-state explanation should be stored in a companion status column. In particular, a missing `amendment_date` is `NOT_APPLICABLE` only when `amendment_number` is 0; an amended record without a date must be sent for review. A missing province is `NOT_APPLICABLE` for a non-Canadian recipient and `UNKNOWN` for a Canadian recipient. Missing foreign-currency values must remain null with a `NOT_APPLICABLE` status and must never be replaced with zero.",
        "",
        "After applying these rules to a new curated output, validate that all 224,000 source rows are still accounted for, required fields remain populated, dates and monetary fields retain their correct data types, amendment and foreign-currency dependencies are valid, and every replacement or deleted column is recorded in an audit log. This produces an analysis-ready dataset without hiding uncertainty or inventing information. The recommendations below document the exact decision for every incomplete column; they have not been applied to the data in this project.",
        "",
        "## Missing Data Remediation Plan (Recommended, Not Applied)",
        "",
        "> This section is a proposed production cleaning policy only. No missing values were changed and no columns were deleted from the supplied or processed datasets.",
        "",
        "### Decision Standard",
        "",
        "The recommended policy follows conservative industry data-quality practice: preserve an immutable raw copy; do not invent identifiers, dates, monetary values, categories, or narrative text; distinguish `UNKNOWN`, `NOT_PROVIDED`, and `NOT_APPLICABLE`; and keep typed numeric/date fields nullable with a companion status field instead of inserting a text sentinel or zero.",
        "",
        f"- Incomplete columns assessed: {len(missing_plan)} of {sample.shape[1]}",
        f"- Complete columns requiring no treatment: {sample.shape[1] - len(missing_plan)}",
        "- Recommended deletion threshold: only fields that are effectively empty and analytically unusable; business-meaningful sparse fields are retained.",
        "- Prohibited approach: mean/median/mode filling for identifiers, categories, dates, currency values, and free text because it fabricates facts.",
        "",
        "### Column-by-Column Recommendation",
        "",
        dataframe_to_markdown(missing_plan, index=False),
        "",
        "### Implementation Guardrails",
        "",
        "1. Apply these rules only in a new curated output; never overwrite the raw workbook or raw CSV snapshot.",
        "2. Add `*_was_missing` Boolean flags before filling text/category fields so downstream analysis can identify imputed display values.",
        "3. Validate conditional rules row by row, especially `amendment_date`, `recipient_province`, and the foreign-currency pair.",
        "4. Re-run missingness, schema, and row-count checks after implementation and document every changed cell and deleted column.",
        "",
        "## File Overview",
        f"- Source workbook: `{discover_workbook_path()}`",
        f"- Source sheet: `{DEFAULT_SOURCE_SHEET}`",
        f"- Raw CSV snapshot: `{csv_path}`",
        f"- Raw CSV size: {human_readable_size(file_size_bytes(csv_path))}",
        f"- Estimated data rows: {row_count:,}",
        f"- Number of columns: {sample.shape[1]}",
        "",
        "## Column Names",
        ", ".join(f"`{column}`" for column in sample.columns),
        "",
        "## Detected Types",
        dataframe_to_markdown(columns_df, index=False),
        "",
        "## Inferred Column Roles",
        dataframe_to_markdown(role_df, index=False),
        "",
        "## Sample Rows",
        dataframe_to_markdown(sample.head(10).fillna(""), index=False),
        "",
    ]

    DEFAULT_EDA_REPORT.write_text("\n".join(report), encoding="utf-8")

    return {
        "rows": count_csv_rows(csv_path),
        "columns": list(sample.columns),
        "roles": roles,
        "report_path": DEFAULT_EDA_REPORT,
    }


def main() -> None:
    csv_path = ensure_raw_csv()
    summary = inspect_file(csv_path)
    print(f"EDA report written to {summary['report_path']}")
    print(f"Rows: {summary['rows']:,}")
    print(f"Columns: {len(summary['columns'])}")


if __name__ == "__main__":
    main()

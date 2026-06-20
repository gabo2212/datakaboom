from __future__ import annotations

from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parent))

from project_utils import (  # noqa: E402
    DEFAULT_CLEANING_EXECUTION_REPORT,
    DEFAULT_MAPPING_REPORT,
    DEFAULT_PROCESSED_CSV,
    ensure_output_directories,
    ensure_raw_csv,
    write_text,
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


def load_accepted_mapping(mapping_path: Path) -> pd.DataFrame:
    mapping = pd.read_csv(mapping_path, dtype=str, keep_default_na=True, low_memory=False)
    if mapping.empty:
        return mapping
    accepted = mapping[mapping["status"] == "accepted"].copy()
    return accepted.reset_index(drop=True)


def clean_file(
    csv_path: Path,
    mapping_path: Path,
    output_path: Path,
    *,
    target_column: str = TARGET_COLUMN,
    chunksize: int = 50_000,
) -> dict[str, object]:
    accepted = load_accepted_mapping(mapping_path)
    accepted_map = {
        str(row.original_value): str(row.clean_value)
        for row in accepted.itertuples(index=False)
    }

    ensure_output_directories()
    if output_path.exists():
        output_path.unlink()

    total_rows = 0
    applied_corrections = 0
    chunks_written = 0

    for chunk in pd.read_csv(
        csv_path,
        chunksize=chunksize,
        dtype=str,
        keep_default_na=True,
        low_memory=False,
    ):
        total_rows += len(chunk)
        if target_column not in chunk.columns:
            raise ValueError(f"Target column '{target_column}' was not found in the source CSV.")

        original_values = chunk[target_column]
        cleaned_values = original_values.map(accepted_map)
        applied_mask = cleaned_values.notna() & original_values.notna() & (cleaned_values != original_values)
        applied_corrections += int(applied_mask.sum())
        final_values = cleaned_values.where(cleaned_values.notna(), original_values)

        clean_column = f"{target_column}_clean"
        insert_at = chunk.columns.get_loc(target_column) + 1
        chunk.insert(insert_at, clean_column, final_values)

        chunk.to_csv(
            output_path,
            index=False,
            mode="a" if chunks_written else "w",
            header=chunks_written == 0,
            encoding="utf-8",
        )
        chunks_written += 1

    report = [
        "# Cleaning Execution Report",
        "",
        f"- Input CSV: `{csv_path}`",
        f"- Mapping file: `{mapping_path}`",
        f"- Output CSV: `{output_path}`",
        f"- Target column: `{target_column}`",
        f"- Rows processed: {total_rows:,}",
        f"- Accepted corrections available: {len(accepted):,}",
        f"- Corrections applied: {applied_corrections:,}",
        f"- Review/rejected mappings skipped: {max(len(pd.read_csv(mapping_path, dtype=str)) - len(accepted), 0):,}",
        "",
        "## Notes",
        "- Only rows with `status = accepted` were applied to the clean column.",
        "- The original column was preserved unchanged.",
        "- Review rows remain in the mapping file for manual validation.",
        "",
    ]
    write_text(DEFAULT_CLEANING_EXECUTION_REPORT, "\n".join(report))

    return {
        "rows_processed": total_rows,
        "corrections_applied": applied_corrections,
        "output_path": output_path,
        "accepted_rows": len(accepted),
    }


def main() -> None:
    csv_path = ensure_raw_csv()
    target_column = resolve_target_column(csv_path)
    summary = clean_file(
        csv_path,
        DEFAULT_MAPPING_REPORT,
        DEFAULT_PROCESSED_CSV,
        target_column=target_column,
    )
    print(f"Processed file written to {summary['output_path']}")
    print(f"Rows processed: {summary['rows_processed']:,}")
    print(f"Corrections applied: {summary['corrections_applied']:,}")


if __name__ == "__main__":
    main()

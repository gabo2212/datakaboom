from __future__ import annotations

from pathlib import Path
import sys
from collections import Counter

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parent))

from project_utils import (  # noqa: E402
    DEFAULT_DUPLICATES_REPORT,
    ensure_raw_csv,
    iter_csv_chunks,
    write_dataframe,
)

import pandas as pd


SAMPLE_COLUMNS = [
    "ref_number",
    "recipient_legal_name",
    "recipient_city",
    "recipient_postal_code",
    "agreement_start_date",
    "agreement_value",
]


def _sample_record(row: tuple[object, ...], columns: list[str], row_number: int) -> dict[str, object]:
    values = dict(zip(columns, row, strict=False))
    record = {
        "row_number": row_number,
        "ref_number": values.get("ref_number", ""),
        "recipient_legal_name": values.get("recipient_legal_name", ""),
        "recipient_city": values.get("recipient_city", ""),
        "recipient_postal_code": values.get("recipient_postal_code", ""),
        "agreement_start_date": values.get("agreement_start_date", ""),
        "agreement_value": values.get("agreement_value", ""),
    }
    return record


def _append_key_stats(
    counts: Counter[str],
    samples: dict[str, dict[str, object]],
    key: str,
    sample: dict[str, object],
) -> None:
    counts[key] += 1
    samples.setdefault(key, sample)


def _exact_row_key(chunk: pd.DataFrame) -> pd.Series:
    normalized = chunk.fillna("")
    return pd.util.hash_pandas_object(normalized, index=False).astype(str)


def detect_duplicates(csv_path: Path) -> pd.DataFrame:
    exact_counts: Counter[str] = Counter()
    exact_samples: dict[str, dict[str, object]] = {}

    ref_counts: Counter[str] = Counter()
    ref_samples: dict[str, dict[str, object]] = {}

    org_date_counts: Counter[str] = Counter()
    org_date_samples: dict[str, dict[str, object]] = {}

    org_location_counts: Counter[str] = Counter()
    org_location_samples: dict[str, dict[str, object]] = {}

    row_offset = 0

    for chunk in iter_csv_chunks(csv_path, chunksize=50_000):
        whitespace_mask = chunk.apply(lambda col: col.astype(str).str.match(r"^\s*$", na=False))
        chunk = chunk.mask(whitespace_mask, pd.NA)
        columns = list(chunk.columns)
        hashes = _exact_row_key(chunk)
        filled = chunk.fillna("")

        for row_number, row_values, row_hash in zip(
            range(row_offset + 1, row_offset + len(chunk) + 1),
            filled.itertuples(index=False, name=None),
            hashes,
            strict=False,
        ):
            sample = _sample_record(row_values, columns, row_number)
            _append_key_stats(exact_counts, exact_samples, row_hash, sample)

            ref_number = str(sample.get("ref_number", "")).strip()
            if ref_number:
                _append_key_stats(ref_counts, ref_samples, f"ref_number={ref_number}", sample)

            org_name = str(sample.get("recipient_legal_name", "")).strip()
            start_date = str(sample.get("agreement_start_date", "")).strip()
            agreement_value = str(sample.get("agreement_value", "")).strip()
            city = str(sample.get("recipient_city", "")).strip()
            postal_code = str(sample.get("recipient_postal_code", "")).strip()

            if org_name and start_date and agreement_value:
                org_date_key = f"org={org_name}|date={start_date}|value={agreement_value}"
                _append_key_stats(org_date_counts, org_date_samples, org_date_key, sample)

            if org_name and city and postal_code:
                org_location_key = f"org={org_name}|city={city}|postal={postal_code}"
                _append_key_stats(
                    org_location_counts,
                    org_location_samples,
                    org_location_key,
                    sample,
                )

        row_offset += len(chunk)

    records: list[dict[str, object]] = []

    def add_records(
        duplicate_type: str,
        counts: Counter[str],
        samples: dict[str, dict[str, object]],
    ) -> None:
        for key, count in counts.items():
            if count <= 1:
                continue
            sample = samples[key]
            records.append(
                {
                    "duplicate_type": duplicate_type,
                    "duplicate_key": key,
                    "duplicate_count": count,
                    "sample_row_number": sample["row_number"],
                    "sample_ref_number": sample["ref_number"],
                    "sample_recipient_legal_name": sample["recipient_legal_name"],
                    "sample_recipient_city": sample["recipient_city"],
                    "sample_recipient_postal_code": sample["recipient_postal_code"],
                    "sample_agreement_start_date": sample["agreement_start_date"],
                    "sample_agreement_value": sample["agreement_value"],
                }
            )

    add_records("exact_row", exact_counts, exact_samples)
    add_records("ref_number", ref_counts, ref_samples)
    add_records("org_date_value", org_date_counts, org_date_samples)
    add_records("org_city_postal", org_location_counts, org_location_samples)

    report = pd.DataFrame(records)
    if not report.empty:
        report = report.sort_values(
            ["duplicate_type", "duplicate_count", "sample_row_number"],
            ascending=[True, False, True],
        ).reset_index(drop=True)
    return report


def main() -> None:
    csv_path = ensure_raw_csv()
    report = detect_duplicates(csv_path)
    write_dataframe(DEFAULT_DUPLICATES_REPORT, report)
    print(f"Duplicates report written to {DEFAULT_DUPLICATES_REPORT}")
    print(f"Duplicate groups found: {len(report)}")


if __name__ == "__main__":
    main()

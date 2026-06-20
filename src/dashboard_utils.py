from __future__ import annotations

from pathlib import Path
import re

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
REPORTS_DIR = ROOT_DIR / "reports"
RAW_CSV = DATA_DIR / "raw" / "fichier_original.csv"
PROCESSED_CSV = DATA_DIR / "processed" / "fichier_nettoye.csv"
SUMMARY_PATH = REPORTS_DIR / "final_summary.md"
EDA_REPORT_PATH = REPORTS_DIR / "eda_report.md"
MISSING_REPORT_PATH = REPORTS_DIR / "missing_values_report.csv"
DUPLICATES_REPORT_PATH = REPORTS_DIR / "duplicates_report.csv"
VARIANTS_REPORT_PATH = REPORTS_DIR / "organization_variants_report.csv"
MAPPING_REPORT_PATH = REPORTS_DIR / "entity_cleaning_mapping.csv"
CLEANING_EXECUTION_REPORT_PATH = REPORTS_DIR / "cleaning_execution_report.md"


def exists(path: Path) -> bool:
    return path.exists()


def pretty_bytes(num_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} GB"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def read_csv(path: Path, **kwargs) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    default_kwargs = {
        "dtype": str,
        "keep_default_na": True,
        "low_memory": False,
    }
    default_kwargs.update(kwargs)
    return pd.read_csv(path, **default_kwargs)


def parse_summary_metrics(summary_text: str) -> dict[str, int]:
    patterns = {
        "raw_rows": r"Original rows: ([0-9,]+)",
        "columns": r"Columns: ([0-9,]+)",
        "unique_raw_orgs": r"Unique raw organization names: ([0-9,]+)",
        "unique_clean_orgs": r"Unique cleaned organization names: ([0-9,]+)",
        "corrections_applied": r"Corrections applied in the cleaned file: ([0-9,]+)",
        "corrections_review": r"Corrections left for review: ([0-9,]+)",
        "duplicate_rows_flagged": r"Total duplicate rows flagged across rules: ([0-9,]+)",
    }

    metrics: dict[str, int] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, summary_text)
        metrics[key] = int(match.group(1).replace(",", "")) if match else 0
    return metrics


def load_summary_metrics() -> dict[str, int]:
    return parse_summary_metrics(read_text(SUMMARY_PATH))


def assignment_checklist(metrics: dict[str, int]) -> pd.DataFrame:
    items = [
        ("01 Inspect file", "reports/eda_report.md"),
        ("02 Missing values", "reports/missing_values_report.csv"),
        ("03 Duplicate detection", "reports/duplicates_report.csv"),
        ("04 Variant detection", "reports/organization_variants_report.csv"),
        ("05 Cleaning mapping", "reports/entity_cleaning_mapping.csv"),
        ("06 Cleaned output", "data/processed/fichier_nettoye.csv"),
        ("07 Final summary", "reports/final_summary.md"),
    ]
    return pd.DataFrame(
        [
            {
                "Step": step,
                "Output": output,
                "Status": "Complete" if Path(output).exists() else "Missing",
            }
            for step, output in items
        ]
    )


def report_catalog() -> pd.DataFrame:
    files = [
        EDA_REPORT_PATH,
        MISSING_REPORT_PATH,
        DUPLICATES_REPORT_PATH,
        VARIANTS_REPORT_PATH,
        MAPPING_REPORT_PATH,
        CLEANING_EXECUTION_REPORT_PATH,
        SUMMARY_PATH,
        RAW_CSV,
        PROCESSED_CSV,
    ]
    rows = []
    for path in files:
        rows.append(
            {
                "name": path.name,
                "path": str(path),
                "exists": path.exists(),
                "size": pretty_bytes(path.stat().st_size) if path.exists() else "Missing",
            }
        )
    return pd.DataFrame(rows)


def sample_columns(path: Path, columns: list[str], rows: int = 200) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, usecols=columns, nrows=rows, dtype=str, keep_default_na=True, low_memory=False)


def top_rows(path: Path, *, sort_column: str, n: int = 20, ascending: bool = False) -> pd.DataFrame:
    df = read_csv(path)
    if df.empty:
        return df
    if sort_column in df.columns:
        numeric = pd.to_numeric(df[sort_column], errors="coerce")
        df = df.assign(_sort=numeric)
        df = df.sort_values("_sort", ascending=ascending, na_position="last").drop(columns=["_sort"])
    return df.head(n).reset_index(drop=True)


def filter_report(df: pd.DataFrame, query: str = "", limit: int = 200) -> pd.DataFrame:
    if df.empty:
        return df
    filtered = df
    if query.strip():
        query_lower = query.casefold()
        mask = pd.Series(False, index=df.index)
        for col in df.columns:
            mask = mask | df[col].astype(str).str.casefold().str.contains(query_lower, regex=False, na=False)
        filtered = df.loc[mask]
    return filtered.head(limit).reset_index(drop=True)


def search_csv_rows(
    csv_path: Path,
    *,
    query: str,
    columns: list[str],
    limit: int = 100,
    chunksize: int = 50_000,
) -> pd.DataFrame:
    if not csv_path.exists() or not query.strip():
        return pd.DataFrame(columns=columns)

    matches: list[pd.DataFrame] = []
    query_lower = query.casefold()
    for chunk in pd.read_csv(
        csv_path,
        usecols=columns,
        chunksize=chunksize,
        dtype=str,
        keep_default_na=True,
        low_memory=False,
    ):
        mask = pd.Series(False, index=chunk.index)
        for col in columns:
            mask = mask | chunk[col].astype(str).str.casefold().str.contains(query_lower, regex=False, na=False)
        if mask.any():
            matches.append(chunk.loc[mask])
            total = sum(len(m) for m in matches)
            if total >= limit:
                break
    if not matches:
        return pd.DataFrame(columns=columns)
    return pd.concat(matches, ignore_index=True).head(limit)


def search_mapping(query: str, *, status: str | None = None, limit: int = 200) -> pd.DataFrame:
    df = read_csv(MAPPING_REPORT_PATH)
    if df.empty:
        return df
    if status and status != "All":
        df = df[df["status"] == status]
    if query.strip():
        query_lower = query.casefold()
        mask = pd.Series(False, index=df.index)
        for col in df.columns:
            mask = mask | df[col].astype(str).str.casefold().str.contains(query_lower, regex=False, na=False)
        df = df.loc[mask]
    return df.head(limit).reset_index(drop=True)


def search_variants(
    query: str,
    *,
    decision: str | None = None,
    limit: int | None = 200,
) -> pd.DataFrame:
    df = read_csv(VARIANTS_REPORT_PATH)
    if df.empty:
        return df
    if decision and decision != "All":
        df = df[df["decision"] == decision]
    if query.strip():
        query_lower = query.casefold()
        mask = pd.Series(False, index=df.index)
        for col in df.columns:
            mask = mask | df[col].astype(str).str.casefold().str.contains(query_lower, regex=False, na=False)
        df = df.loc[mask]
    if limit is None:
        return df.reset_index(drop=True)
    return df.head(limit).reset_index(drop=True)

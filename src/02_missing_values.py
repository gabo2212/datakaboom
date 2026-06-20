from __future__ import annotations

from pathlib import Path
import sys
from collections import Counter

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parent))

from project_utils import (  # noqa: E402
    DEFAULT_MISSING_VALUES_REPORT,
    ensure_raw_csv,
    iter_csv_chunks,
    write_dataframe,
)

import pandas as pd


def recommend_action(missing_percentage: float) -> str:
    if missing_percentage == 0:
        return "Rien à faire"
    if missing_percentage < 5:
        return "Imputation simple"
    if missing_percentage <= 40:
        return "Imputation + colonne is_missing"
    if missing_percentage > 70:
        return "Suppression possible, sauf valeur métier importante"
    return "Évaluer l'utilité de la colonne"


def analyze_missing_values(csv_path: Path) -> pd.DataFrame:
    missing_counts: Counter[str] = Counter()
    total_rows = 0
    columns: list[str] | None = None

    for chunk in iter_csv_chunks(csv_path, chunksize=50_000):
        whitespace_mask = chunk.apply(lambda col: col.astype(str).str.match(r"^\s*$", na=False))
        chunk = chunk.mask(whitespace_mask, pd.NA)
        if columns is None:
            columns = list(chunk.columns)
            missing_counts.update({column: 0 for column in columns})
        total_rows += len(chunk)
        chunk_missing = chunk.isna().sum()
        missing_counts.update({column: int(count) for column, count in chunk_missing.items()})

    if columns is None:
        return pd.DataFrame(columns=["colonne", "valeurs_manquantes", "total_lignes", "pourcentage_manquant", "recommandation"])

    report = pd.DataFrame(
        [
            {
                "colonne": column,
                "valeurs_manquantes": int(count),
                "total_lignes": total_rows,
                "pourcentage_manquant": round((count / total_rows) * 100, 2) if total_rows else 0,
                "recommandation": recommend_action((count / total_rows) * 100 if total_rows else 0),
            }
            for column, count in sorted(missing_counts.items())
        ]
    ).sort_values(["pourcentage_manquant", "valeurs_manquantes"], ascending=False)

    return report.reset_index(drop=True)


def main() -> None:
    csv_path = ensure_raw_csv()
    report = analyze_missing_values(csv_path)
    write_dataframe(DEFAULT_MISSING_VALUES_REPORT, report)
    print(f"Missing values report written to {DEFAULT_MISSING_VALUES_REPORT}")
    print(f"Columns analyzed: {len(report)}")


if __name__ == "__main__":
    main()

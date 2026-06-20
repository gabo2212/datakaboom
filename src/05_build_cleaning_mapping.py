from __future__ import annotations

from pathlib import Path
import sys

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parent))

from project_utils import (  # noqa: E402
    DEFAULT_MAPPING_REPORT,
    DEFAULT_VARIANTS_REPORT,
    is_uqam_accept_alias,
    is_uqam_review_candidate,
    normalize_text,
    write_dataframe,
)

import pandas as pd


def build_mapping(variants_report_path: Path) -> pd.DataFrame:
    report = pd.read_csv(variants_report_path, dtype=str, keep_default_na=True, low_memory=False)
    if report.empty:
        return pd.DataFrame(columns=["original_value", "clean_value", "status", "reason"])

    rows: list[dict[str, object]] = []
    for row in report.itertuples(index=False):
        original = str(row.original_value)
        clean_value = str(row.suggested_group)
        decision = str(row.decision)
        score = int(float(row.similarity_score))
        normalized = normalize_text(original)

        if decision == "accepted":
            reason = _accepted_reason(original, clean_value, normalized, score)
        elif decision == "review":
            reason = _review_reason(original, clean_value, normalized, score)
        else:
            reason = "similarité insuffisante ou contexte différent"

        rows.append(
            {
                "original_value": original,
                "clean_value": clean_value,
                "status": decision,
                "reason": reason,
            }
        )

    mapping = pd.DataFrame(rows)
    if not mapping.empty:
        mapping = mapping.drop_duplicates(subset=["original_value"], keep="first").reset_index(drop=True)
    return mapping


def _accepted_reason(original: str, clean_value: str, normalized: str, score: int) -> str:
    if is_uqam_accept_alias(original):
        if normalized == "UNIVERSITE DU QUEBEC A MONTREAL":
            return "nom complet reconnu"
        if normalized in {"UQAM", "U Q A M"}:
            return "forme évidente ou acronymie équivalente"
    if score >= 100:
        return "même forme compacte après normalisation"
    return f"variante validée vers {clean_value}"


def _review_reason(original: str, clean_value: str, normalized: str, score: int) -> str:
    if is_uqam_review_candidate(original):
        if score >= 90:
            return "forte similarité mais validation recommandée"
        return "possible faute de frappe ou variante ambiguë"
    if "UQAM" in normalized.replace(" ", ""):
        return "contexte potentiellement distinct autour de UQAM"
    if score >= 80:
        return "proposition proche mais à vérifier"
    return "similarité à confirmer manuellement"


def main() -> None:
    mapping = build_mapping(DEFAULT_VARIANTS_REPORT)
    write_dataframe(DEFAULT_MAPPING_REPORT, mapping)
    print(f"Cleaning mapping written to {DEFAULT_MAPPING_REPORT}")
    print(f"Mapping rows: {len(mapping)}")


if __name__ == "__main__":
    main()

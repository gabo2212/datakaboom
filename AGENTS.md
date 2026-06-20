# AGENTS

- Keep the raw workbook untouched.
- Treat `data/raw/fichier_original.csv` as the chunked-processing snapshot generated from `Extraction brute`.
- Run the scripts in the documented order so later reports have their inputs.
- Only apply accepted cleaning mappings in `src/06_clean_file.py`.
- Preserve the original organization name column and write the cleaned value to `recipient_legal_name_clean`.
- Use chunked CSV processing for large-file steps.
- Keep generated reports in `reports/` and processed data in `data/processed/`.

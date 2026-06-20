# Cleaning Execution Report

- Input CSV: `/home/gablegoob/Desktop/Skool/datakaboom/data/raw/fichier_original.csv`
- Mapping file: `/home/gablegoob/Desktop/Skool/datakaboom/reports/entity_cleaning_mapping.csv`
- Output CSV: `/home/gablegoob/Desktop/Skool/datakaboom/data/processed/fichier_nettoye.csv`
- Target column: `recipient_legal_name`
- Rows processed: 224,000
- Accepted corrections available: 17,289
- Corrections applied: 10,162
- Review/rejected mappings skipped: 2,927

## Notes
- Only rows with `status = accepted` were applied to the clean column.
- The original column was preserved unchanged.
- Review rows remain in the mapping file for manual validation.

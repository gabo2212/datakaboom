# Big File EDA and Cleaning with Codex

This project analyzes and cleans a large administrative dataset from the provided workbook.

The source file in this workspace is an Excel workbook:
`data/2026-05-13_donnees-ouvertes_divulgation-octrois-subventions-et-contributions.xlsx`

The pipeline extracts the `Extraction brute` sheet into:
`data/raw/fichier_original.csv`

## Project Structure

```text
data/
  raw/
  processed/
reports/
src/
```

## Dependencies

Install the required packages in a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If your system Python blocks package installs with `externally-managed-environment`, use the virtual environment commands above instead of installing globally.
As a last resort on a managed system, you can use:

```bash
python -m pip install --break-system-packages -r requirements.txt
```

The workbook source requires `openpyxl`, and the variant detection step uses `rapidfuzz`.

## Run Order

Run the scripts in this order:

```bash
python src/01_inspect_file.py
python src/02_missing_values.py
python src/03_detect_duplicates.py
python src/04_detect_text_variants.py
python src/05_build_cleaning_mapping.py
python src/06_clean_file.py
python src/07_final_summary.py
python src/08_apply_eda_remediation.py
```

## Outputs

- `reports/eda_report.md`
- `reports/missing_values_report.csv`
- `reports/duplicates_report.csv`
- `reports/organization_variants_report.csv`
- `reports/entity_cleaning_mapping.csv`
- `reports/cleaning_execution_report.md`
- `reports/final_summary.md`
- `reports/eda_remediation_execution_report.md`
- `data/processed/fichier_nettoye.csv`
- `data/processed/fichier_corrige_eda.csv`

## Dashboard

If you want a simple UI to inspect the work, run:

```bash
streamlit run app.py
```

If you created `.venv`, activate it first before running Streamlit.

The dashboard includes:

- a project checklist that maps the GitHub brief to the generated files
- summary metrics for the raw and cleaned dataset
- an AI assistant grounded in the reports and targeted dataset evidence
- a dedicated Fixed Dataset tab with remediation metrics, audit details, search, preview, and download
- tabs for missing values, duplicates, variant detection, and cleaning
- side-by-side raw vs cleaned row previews for quick comparison
- direct download links for every generated report and dataset

The dashboard is read-only. It does not change the cleaning pipeline or the data.

### AI Assistant

The AI tab uses NVIDIA's OpenAI-compatible API. Keep the API key out of source
code and provide it through the environment before starting Streamlit:

```bash
export NVIDIA_API_KEY="your-rotated-key"
streamlit run app.py
```

You can also enter the key in the password field in the AI tab. The assistant
does not send both 200 MB datasets to the model. It retrieves bounded excerpts
from every report and scans the final fixed CSV only for a high-confidence exact
organization or reference lookup.

## Notes

- The raw workbook is not modified.
- Only `status = accepted` mappings are applied to the cleaned file.
- `review` rows remain in the mapping file for manual validation.
- The cleaning step adds `recipient_legal_name_clean` and preserves the original column.
- `data/processed/fichier_nettoye.csv` is organization-name cleaned only. The
  missing-data treatments documented in the EDA report are not applied to that intermediate file.
- `data/processed/fichier_corrige_eda.csv` is the final fixed dataset. It retains
  the accepted organization-name corrections and applies the EDA missing-data
  rules with auditable flags and status columns.

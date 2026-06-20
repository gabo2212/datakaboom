# Final Summary

## Dataset Overview
- Original rows: 224,000
- Columns: 39
- Unique raw organization names: 77,631
- Unique cleaned organization names: 70,046

## Missing Values
| colonne                    |   valeurs_manquantes |   total_lignes |   pourcentage_manquant | recommandation                                      |
|:---------------------------|---------------------:|---------------:|-----------------------:|:----------------------------------------------------|
| coverage                   |               223998 |         224000 |                 100    | Suppression possible, sauf valeur métier importante |
| federal_riding_number      |               223995 |         224000 |                 100    | Suppression possible, sauf valeur métier importante |
| federal_riding_name_fr     |               223994 |         224000 |                 100    | Suppression possible, sauf valeur métier importante |
| federal_riding_name_en     |               223993 |         224000 |                 100    | Suppression possible, sauf valeur métier importante |
| amendment_date             |               214478 |         224000 |                  95.75 | Suppression possible, sauf valeur métier importante |
| recipient_operating_name   |               213037 |         224000 |                  95.11 | Suppression possible, sauf valeur métier importante |
| foreign_currency_type      |               208126 |         224000 |                  92.91 | Suppression possible, sauf valeur métier importante |
| foreign_currency_value     |               208126 |         224000 |                  92.91 | Suppression possible, sauf valeur métier importante |
| research_organization_name |               207372 |         224000 |                  92.58 | Suppression possible, sauf valeur métier importante |
| naics_identifier           |               200998 |         224000 |                  89.73 | Suppression possible, sauf valeur métier importante |
| recipient_business_number  |               190153 |         224000 |                  84.89 | Suppression possible, sauf valeur métier importante |
| recipient_type             |               164764 |         224000 |                  73.56 | Suppression possible, sauf valeur métier importante |
| additional_information_fr  |               150085 |         224000 |                  67    | Évaluer l'utilité de la colonne                     |
| additional_information_en  |               150046 |         224000 |                  66.98 | Évaluer l'utilité de la colonne                     |
| prog_purpose_fr            |               117334 |         224000 |                  52.38 | Évaluer l'utilité de la colonne                     |
| prog_purpose_en            |               114945 |         224000 |                  51.31 | Évaluer l'utilité de la colonne                     |
| expected_results_fr        |               114085 |         224000 |                  50.93 | Évaluer l'utilité de la colonne                     |
| expected_results_en        |               113951 |         224000 |                  50.87 | Évaluer l'utilité de la colonne                     |
| agreement_title_fr         |                85754 |         224000 |                  38.28 | Imputation + colonne is_missing                     |
| agreement_title_en         |                85744 |         224000 |                  38.28 | Imputation + colonne is_missing                     |
| recipient_postal_code      |                84543 |         224000 |                  37.74 | Imputation + colonne is_missing                     |
| agreement_number           |                68985 |         224000 |                  30.8  | Imputation + colonne is_missing                     |
| prog_name_en               |                65247 |         224000 |                  29.13 | Imputation + colonne is_missing                     |
| prog_name_fr               |                62903 |         224000 |                  28.08 | Imputation + colonne is_missing                     |
| agreement_end_date         |                55585 |         224000 |                  24.81 | Imputation + colonne is_missing                     |
| recipient_province         |                47204 |         224000 |                  21.07 | Imputation + colonne is_missing                     |
| description_en             |                45911 |         224000 |                  20.5  | Imputation + colonne is_missing                     |
| description_fr             |                45911 |         224000 |                  20.5  | Imputation + colonne is_missing                     |
| recipient_country          |                   47 |         224000 |                   0.02 | Imputation simple                                   |
| recipient_city             |                   12 |         224000 |                   0.01 | Imputation simple                                   |
| agreement_type             |                    1 |         224000 |                   0    | Imputation simple                                   |
| #                          |                    0 |         224000 |                   0    | Rien à faire                                        |
| agreement_start_date       |                    0 |         224000 |                   0    | Rien à faire                                        |
| agreement_value            |                    0 |         224000 |                   0    | Rien à faire                                        |
| amendment_number           |                    0 |         224000 |                   0    | Rien à faire                                        |
| owner_org                  |                    0 |         224000 |                   0    | Rien à faire                                        |
| owner_org_title            |                    0 |         224000 |                   0    | Rien à faire                                        |
| recipient_legal_name       |                    0 |         224000 |                   0    | Rien à faire                                        |
| ref_number                 |                    0 |         224000 |                   0    | Rien à faire                                        |

## Duplicate Detection
| duplicate_type   |   duplicate_groups |   duplicate_rows_flagged |
|:-----------------|-------------------:|-------------------------:|
| org_city_postal  |              23117 |                    74894 |
| org_date_value   |               3805 |                     4552 |
| ref_number       |               2046 |                     2368 |
- Total duplicate rows flagged across rules: 81,814

## Cleaning Mapping
| status   |   count |
|:---------|--------:|
| accepted |   17289 |
| review   |    2927 |
- Corrections applied in the cleaned file: 10,162
- Corrections left for review: 2,927

## Limitations
- The raw workbook was converted to a CSV snapshot before chunked processing.
- Review rows were intentionally not applied to avoid incorrect automated merges.
- Duplicate rules can overlap, so duplicate counts are reported by rule.
- Contextual organization names that merely contain UQAM were treated conservatively.

## Recommendations
- Manually validate the review rows in `entity_cleaning_mapping.csv`.
- Check the largest duplicate groups before downstream analysis or modeling.
- Re-run the pipeline if the raw workbook changes.

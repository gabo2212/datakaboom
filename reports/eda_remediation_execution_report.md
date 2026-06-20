# EDA Remediation Execution Report

## Result

The EDA missing-data recommendations were applied to a new final curated CSV. The raw CSV, source workbook, and organization-cleaned intermediate were not overwritten.

- Input CSV: `/home/gablegoob/Desktop/Skool/datakaboom/data/processed/fichier_nettoye.csv`
- Final remediated CSV: `/home/gablegoob/Desktop/Skool/datakaboom/data/processed/fichier_corrige_eda.csv`
- Rows processed and preserved: 224,000
- Input columns: 40
- Output columns: 63
- Total fixed text/category values: 2,537,158
- Rows requiring conditional review: 0
- Output size: 273.04 MB

## Columns Deleted

`coverage`, `federal_riding_number`, `federal_riding_name_en`, `federal_riding_name_fr`

These four columns were deleted only from the final curated output because they were effectively empty and analytically unusable. They remain available in the raw and intermediate files.

## Fixed Text and Category Values

| column                     | replacement                             |   values_replaced | missing_flag_added   |
|:---------------------------|:----------------------------------------|------------------:|:---------------------|
| additional_information_en  | NOT_PROVIDED                            |            150046 | True                 |
| additional_information_fr  | NOT_PROVIDED                            |            150085 | True                 |
| agreement_number           | NOT_PROVIDED                            |             68985 | True                 |
| agreement_title_en         | NOT_PROVIDED                            |             85744 | True                 |
| agreement_title_fr         | NOT_PROVIDED                            |             85754 | True                 |
| agreement_type             | UNKNOWN                                 |                 1 | True                 |
| description_en             | NOT_PROVIDED                            |             45911 | True                 |
| description_fr             | NOT_PROVIDED                            |             45911 | True                 |
| expected_results_en        | NOT_PROVIDED                            |            113951 | True                 |
| expected_results_fr        | NOT_PROVIDED                            |            114085 | True                 |
| foreign_currency_type      | NOT_APPLICABLE                          |            208126 | True                 |
| naics_identifier           | NOT_PROVIDED                            |            200998 | True                 |
| prog_name_en               | NOT_PROVIDED                            |             65247 | True                 |
| prog_name_fr               | NOT_PROVIDED                            |             62903 | True                 |
| prog_purpose_en            | NOT_PROVIDED                            |            114945 | True                 |
| prog_purpose_fr            | NOT_PROVIDED                            |            117334 | True                 |
| recipient_business_number  | NOT_PROVIDED                            |            190153 | True                 |
| recipient_city             | UNKNOWN                                 |                12 | True                 |
| recipient_country          | UNKNOWN                                 |                47 | True                 |
| recipient_operating_name   | NOT_PROVIDED                            |            213037 | True                 |
| recipient_postal_code      | NOT_PROVIDED                            |             84543 | True                 |
| recipient_province         | NOT_APPLICABLE or UNKNOWN (conditional) |             47204 | True                 |
| recipient_type             | UNKNOWN                                 |            164764 | True                 |
| research_organization_name | NOT_PROVIDED                            |            207372 | True                 |

## Typed Null Status Columns

| status_column                 | status         |   rows |
|:------------------------------|:---------------|-------:|
| amendment_date_status         | NOT_APPLICABLE | 214478 |
| amendment_date_status         | PRESENT        |   9522 |
| foreign_currency_value_status | NOT_APPLICABLE | 208126 |
| foreign_currency_value_status | PRESENT        |  15874 |
| agreement_end_date_status     | NOT_PROVIDED   |  55585 |
| agreement_end_date_status     | PRESENT        | 168415 |

Dates and numeric currency values remain nullable. Their companion status columns explain whether a null is `NOT_APPLICABLE`, `NOT_PROVIDED`, or `REVIEW_REQUIRED` without inserting invalid text or zero into typed fields.

## Validation

- Row-count check: PASS (224,000 rows)
- Expected schema check: PASS (63 columns)
- Organization-cleaning preservation: PASS (`recipient_legal_name_clean` retained)
- Raw/intermediate preservation: PASS (new output path used)
- Missing-data lineage: PASS (`*_was_missing` and status columns added)

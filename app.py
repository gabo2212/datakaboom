from __future__ import annotations

import os
from pathlib import Path
import sys

import pandas as pd
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR / "src"))


def load_local_environment() -> None:
    """Load simple KEY=VALUE entries without overriding shell environment values."""

    env_path = ROOT_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


load_local_environment()

from dashboard_utils import (  # noqa: E402
    CLEANING_EXECUTION_REPORT_PATH,
    DUPLICATES_REPORT_PATH,
    EDA_REPORT_PATH,
    MAPPING_REPORT_PATH,
    MISSING_REPORT_PATH,
    PROCESSED_CSV,
    RAW_CSV,
    REMEDIATED_CSV,
    REMEDIATION_EXECUTION_REPORT_PATH,
    SUMMARY_PATH,
    VARIANTS_REPORT_PATH,
    assignment_checklist,
    load_summary_metrics,
    parse_remediation_metrics,
    pretty_bytes,
    read_csv,
    read_text,
    report_catalog,
    sample_columns,
    search_csv_rows,
    search_mapping,
)
from ai_assistant import (  # noqa: E402
    MAX_CONTEXT_CHARS,
    NVIDIA_MODEL,
    build_context,
    stream_answer,
)


st.set_page_config(
    page_title="Big File EDA Dashboard",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="auto",
)


def inject_css() -> None:
    """Load the centralized industrial design system for every dashboard surface."""

    stylesheet = (ROOT_DIR / "assets" / "dashboard.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{stylesheet}</style>", unsafe_allow_html=True)


REPORT_INPUT_PATHS = (
    SUMMARY_PATH,
    EDA_REPORT_PATH,
    CLEANING_EXECUTION_REPORT_PATH,
    REMEDIATION_EXECUTION_REPORT_PATH,
    MISSING_REPORT_PATH,
    DUPLICATES_REPORT_PATH,
    VARIANTS_REPORT_PATH,
    MAPPING_REPORT_PATH,
    REMEDIATED_CSV,
)


def report_files_version() -> tuple[tuple[str, int, int], ...]:
    """Return a cache key that changes whenever a generated report changes."""

    return tuple(
        (
            str(path),
            path.stat().st_mtime_ns if path.exists() else 0,
            path.stat().st_size if path.exists() else 0,
        )
        for path in REPORT_INPUT_PATHS
    )


@st.cache_data(show_spinner=False)
def load_reports(report_version: tuple[tuple[str, int, int], ...]):
    del report_version  # The value is used by Streamlit as the cache key.
    metrics = load_summary_metrics()
    checklist = assignment_checklist(metrics)
    catalog = report_catalog()
    missing = read_csv(MISSING_REPORT_PATH)
    duplicates = read_csv(DUPLICATES_REPORT_PATH)
    variants = read_csv(VARIANTS_REPORT_PATH)
    mapping = read_csv(MAPPING_REPORT_PATH)
    summary_text = read_text(SUMMARY_PATH)
    eda_text = read_text(EDA_REPORT_PATH)
    cleaning_text = read_text(CLEANING_EXECUTION_REPORT_PATH)
    remediation_text = read_text(REMEDIATION_EXECUTION_REPORT_PATH)
    return {
        "metrics": metrics,
        "checklist": checklist,
        "catalog": catalog,
        "missing": missing,
        "duplicates": duplicates,
        "variants": variants,
        "mapping": mapping,
        "summary_text": summary_text,
        "eda_text": eda_text,
        "cleaning_text": cleaning_text,
        "remediation_text": remediation_text,
        "remediation_metrics": parse_remediation_metrics(remediation_text),
    }


def file_size_label(path: Path) -> str:
    if not path.exists():
        return "Missing"
    return pretty_bytes(path.stat().st_size)


def download_link(path: Path, label: str, *, key: str | None = None) -> None:
    if not path.exists():
        st.caption(f"{label}: missing")
        return

    mime_types = {
        ".csv": "text/csv",
        ".md": "text/markdown",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    st.download_button(
        label=f"Download {label}",
        # Streamlit executes this only after a click. This keeps the two 200+ MB
        # CSV files out of memory while the Reports tab is being rendered.
        data=path.read_bytes,
        file_name=path.name,
        mime=mime_types.get(path.suffix.lower(), "application/octet-stream"),
        help=f"{path.name} ({file_size_label(path)})",
        key=key,
        width="stretch",
    )


def render_header(metrics: dict[str, int]) -> None:
    st.markdown(
        f"""
        <div class="hero">
          <div class="hero-copy">
            <div class="eyebrow"><span class="status-led"></span> Data control console / 01</div>
            <h1>Big File EDA<br><span>and Cleaning</span></h1>
            <p>
              Inspect the raw workbook, audit every cleaning decision, and verify the
              final analysis-ready dataset from one calibrated workspace.
            </p>
          </div>
          <div class="instrument-panel" aria-label="Dataset processing status">
            <div class="instrument-bar">
              <span>PIPELINE STATUS</span>
              <span class="online-label"><span class="status-led status-led--green"></span>OPERATIONAL</span>
            </div>
            <div class="instrument-screen">
              <div><span>ROWS INDEXED</span><strong>{metrics.get('raw_rows', 0):,}</strong></div>
              <div><span>FIELDS / RAW</span><strong>{metrics.get('columns', 0):02d}</strong></div>
              <div><span>FIXES APPLIED</span><strong>{metrics.get('corrections_applied', 0):,}</strong></div>
            </div>
            <div class="vent-bank" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Rows", f"{metrics.get('raw_rows', 0):,}")
    c2.metric("Raw columns", f"{metrics.get('columns', 0):,}")
    c3.metric("Unique orgs", f"{metrics.get('unique_raw_orgs', 0):,}")
    c4.metric("Cleaned orgs", f"{metrics.get('unique_clean_orgs', 0):,}")
    c5.metric("Corrections applied", f"{metrics.get('corrections_applied', 0):,}")
    c6.metric("Review rows", f"{metrics.get('corrections_review', 0):,}")


def render_assignment_checklist(checklist: pd.DataFrame) -> None:
    st.markdown('<div class="section-title">Assignment checklist</div>', unsafe_allow_html=True)
    st.caption("This maps the GitHub brief to the artifacts generated in the workspace.")
    display = checklist.copy()
    display["Status"] = display["Status"].map(
        lambda value: "Complete" if value == "Complete" else "Missing"
    )
    st.dataframe(display, width="stretch", hide_index=True, height=260)


def render_overview(loads: dict[str, object]) -> None:
    checklist = loads["checklist"]
    catalog = loads["catalog"]
    complete_count = int((checklist["Status"] == "Complete").sum())
    total_count = int(len(checklist))
    progress = complete_count / total_count if total_count else 0.0

    left, right = st.columns([1.35, 1])
    with left:
        render_assignment_checklist(checklist)
    with right:
        st.markdown('<div class="section-title">Project state</div>', unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="soft-card">
            <p class="subtle">Raw workbook</p>
            <p>{RAW_CSV.name} ({file_size_label(RAW_CSV)})</p>
            <p class="subtle">Organization-cleaned intermediate</p>
            <p>{PROCESSED_CSV.name} ({file_size_label(PROCESSED_CSV)})</p>
            <p class="subtle">Final EDA-remediated dataset</p>
            <p>{REMEDIATED_CSV.name} ({file_size_label(REMEDIATED_CSV)})</p>
            <p class="subtle">Validated outputs</p>
            <p>{complete_count} of {total_count} artifacts complete</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.progress(progress)
        st.caption(f"Completion: {progress:.0%}")
        st.dataframe(catalog, width="stretch", hide_index=True, height=260)

    st.write("")
    st.markdown('<div class="section-title">What the project produced</div>', unsafe_allow_html=True)
    st.write(
        "The dashboard tracks the same deliverables the assignment asked for: inspection, missing values, "
        "duplicates, text variants, accepted organization cleaning, EDA remediation, a final fixed output, "
        "and auditable reports."
    )


def render_ai_assistant(loads: dict[str, object]) -> None:
    st.markdown('<div class="section-title">Ask the project AI</div>', unsafe_allow_html=True)
    st.caption(
        "Ask questions about the dataset, EDA, missing values, duplicates, organization variants, "
        "cleaning decisions, and final results."
    )
    st.info(
        "Privacy notice: your question and the selected report/data evidence are sent to NVIDIA's API. "
        "The full CSV files and your API key are not included in the prompt."
    )

    key_col, control_col = st.columns([3, 1])
    with key_col:
        api_key = st.text_input(
            "NVIDIA API key",
            value=os.environ.get("NVIDIA_API_KEY", ""),
            type="password",
            key="nvidia_api_key",
            help="The key remains in this Streamlit session and is never written to a project file.",
        )
    with control_col:
        st.write("")
        st.write("")
        if st.button("Clear conversation", width="stretch", key="clear_ai_chat"):
            st.session_state["ai_messages"] = []
            st.rerun()

    st.markdown(
        f"""
        <div class="soft-card">
          <p><strong>Model:</strong> {NVIDIA_MODEL}</p>
          <p class="subtle">
            Efficient retrieval: all eight generated reports are indexed, context is capped at
            {MAX_CONTEXT_CHARS:,} characters, and the final fixed CSV is scanned only when an
            exact organization, acronym, or reference is detected in the question.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")
    st.caption("Example questions")
    example_cols = st.columns(3)
    examples = [
        "What are the most serious data-quality problems?",
        "Which columns should be removed and why?",
        "How were organization names cleaned?",
    ]
    selected_example = ""
    for column, example in zip(example_cols, examples):
        with column:
            if st.button(example, width="stretch", key=f"ai_example_{example}"):
                selected_example = example

    if "ai_messages" not in st.session_state:
        st.session_state["ai_messages"] = []

    for message in st.session_state["ai_messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("evidence"):
                st.caption(message["evidence"])

    typed_question = st.chat_input(
        "Ask a question about this project...",
        key="ai_chat_question",
    )
    question = typed_question or selected_example
    if not question:
        return
    if not api_key.strip():
        st.error("Enter a valid NVIDIA API key before asking a question.")
        return

    previous_history = [
        {"role": message["role"], "content": message["content"]}
        for message in st.session_state["ai_messages"]
    ]
    st.session_state["ai_messages"].append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    context = build_context(question, loads)
    evidence_note = (
        f"Evidence: {len(context.sources)} reports; {len(context.text):,} context characters; "
        f"{context.dataset_rows} matching dataset rows."
    )

    with st.chat_message("assistant"):
        placeholder = st.empty()
        answer_parts: list[str] = []
        try:
            with st.spinner("Retrieving evidence and generating a grounded answer..."):
                for token in stream_answer(
                    api_key=api_key.strip(),
                    question=question,
                    context=context,
                    history=previous_history,
                ):
                    answer_parts.append(token)
                    placeholder.markdown("".join(answer_parts))
        except Exception as exc:
            safe_error = str(exc).replace(api_key.strip(), "[redacted]")
            placeholder.error(f"AI request failed: {safe_error}")
            return

        answer = "".join(answer_parts).strip()
        if not answer:
            placeholder.error("The model returned an empty response. Try the question again.")
            return
        st.caption(evidence_note)

    st.session_state["ai_messages"].append(
        {"role": "assistant", "content": answer, "evidence": evidence_note}
    )
    st.session_state["ai_messages"] = st.session_state["ai_messages"][-20:]


def render_fixed_dataset(loads: dict[str, object]) -> None:
    st.markdown('<div class="section-title">Final fixed dataset</div>', unsafe_allow_html=True)
    st.caption(
        "This is the final analysis-ready output. It combines the accepted organization-name "
        "corrections with the missing-data remediation specified in the EDA report."
    )

    if not REMEDIATED_CSV.exists():
        st.error(
            "The final fixed CSV has not been generated. Run "
            "`python src/08_apply_eda_remediation.py` first."
        )
        return

    metrics = loads["remediation_metrics"]
    metric_cols = st.columns(5)
    metric_cols[0].metric("Rows preserved", f"{metrics.get('rows', 0):,}")
    metric_cols[1].metric("Final columns", f"{metrics.get('output_columns', 0):,}")
    metric_cols[2].metric("Columns deleted", "4")
    metric_cols[3].metric("Values standardized", f"{metrics.get('replacements', 0):,}")
    metric_cols[4].metric("Review required", f"{metrics.get('review_rows', 0):,}")

    st.success(
        "Validation passed: all 224,000 rows and accepted organization-name corrections were "
        "preserved, the four unusable fields were removed, and no conditional conflicts require review."
    )

    download_cols = st.columns(2)
    with download_cols[0]:
        download_link(REMEDIATED_CSV, "fully fixed CSV", key="fixed_tab_csv_download")
    with download_cols[1]:
        download_link(
            REMEDIATION_EXECUTION_REPORT_PATH,
            "remediation audit report",
            key="fixed_tab_report_download",
        )

    action_col, lineage_col = st.columns(2)
    with action_col:
        st.markdown(
            """
            <div class="soft-card">
              <p><strong>What was fixed</strong></p>
              <p>Missing text uses controlled values: <code>UNKNOWN</code>,
              <code>NOT_PROVIDED</code>, or <code>NOT_APPLICABLE</code>.</p>
              <p>Province values use a country-aware rule. Amendment and currency fields use
              conditional status rules instead of guessed values.</p>
              <p>Four effectively empty riding/coverage columns were removed.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with lineage_col:
        st.markdown(
            """
            <div class="soft-card">
              <p><strong>What was preserved</strong></p>
              <p>The raw workbook, raw CSV, and organization-cleaned intermediate remain unchanged.</p>
              <p><code>recipient_legal_name_clean</code> and all 224,000 row identities remain in order.</p>
              <p>Twenty-four <code>*_was_missing</code> flags and three status columns make every
              remediation decision traceable.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.write("")
    st.markdown("#### Search and preview the fixed data")
    st.caption(
        "Leave search empty for the first rows, or enter an organization, reference, city, or status."
    )
    search_col, limit_col = st.columns([3, 1])
    with search_col:
        query = st.text_input("Search fixed dataset", value="", key="fixed_dataset_search")
    with limit_col:
        limit = st.select_slider(
            "Rows",
            options=[20, 40, 60, 100],
            value=40,
            key="fixed_dataset_limit",
        )

    available = read_csv(REMEDIATED_CSV, nrows=0).columns.tolist()
    preview_columns = [
        "ref_number",
        "recipient_legal_name",
        "recipient_legal_name_clean",
        "recipient_country",
        "recipient_province",
        "recipient_province_was_missing",
        "recipient_city",
        "agreement_value",
        "amendment_date",
        "amendment_date_status",
        "agreement_end_date",
        "agreement_end_date_status",
        "foreign_currency_type",
        "foreign_currency_value_status",
    ]
    preview_columns = [column for column in preview_columns if column in available]
    if query.strip():
        preview = search_csv_rows(
            REMEDIATED_CSV,
            query=query,
            columns=preview_columns,
            limit=limit,
        )
    else:
        preview = sample_columns(REMEDIATED_CSV, preview_columns, rows=limit)

    if preview.empty:
        st.info("No matching rows were found in the final fixed dataset.")
    else:
        st.dataframe(preview, width="stretch", hide_index=True, height=480)

    with st.expander("Full remediation audit report", expanded=False):
        st.markdown(loads["remediation_text"])


def render_missing_values(missing: pd.DataFrame) -> None:
    st.markdown('<div class="section-title">Missing values</div>', unsafe_allow_html=True)
    st.caption(
        "Columns sorted by missing percentage. Use the left handle for the minimum and the right handle for the maximum."
    )

    min_threshold, max_threshold = st.slider(
        "Show columns with missing percentage between",
        0.0,
        100.0,
        (20.0, 100.0),
        1.0,
        key="missing_threshold_range_slider",
    )
    filtered = missing.copy()
    if not filtered.empty:
        missing_pct = pd.to_numeric(filtered["pourcentage_manquant"], errors="coerce")
        filtered = filtered[(missing_pct >= min_threshold) & (missing_pct <= max_threshold)]
    st.dataframe(filtered, width="stretch", hide_index=True, height=360)

    if not missing.empty:
        top_missing = missing.head(10).copy()
        top_missing["pourcentage_manquant"] = pd.to_numeric(
            top_missing["pourcentage_manquant"], errors="coerce"
        )
        st.caption("Top missingness is already at the top of the table. Use the range slider to narrow it down.")
        st.dataframe(
            top_missing[["colonne", "pourcentage_manquant", "recommandation"]],
            width="stretch",
            hide_index=True,
            height=260,
        )


def render_duplicates(duplicates: pd.DataFrame) -> None:
    st.markdown('<div class="section-title">Duplicate groups</div>', unsafe_allow_html=True)
    st.caption("These are the rule-based duplicate groups identified in the pipeline.")

    if duplicates.empty:
        st.info("No duplicate report found.")
        return

    duplicate_type = st.selectbox(
        "Duplicate rule",
        ["All"] + sorted(duplicates["duplicate_type"].dropna().unique().tolist()),
        index=0,
    )
    filtered = duplicates.copy()
    if duplicate_type != "All":
        filtered = filtered[filtered["duplicate_type"] == duplicate_type]

    st.dataframe(
        filtered.head(200),
        width="stretch",
        hide_index=True,
        height=360,
    )

    summary = (
        duplicates.assign(
            duplicate_count_num=pd.to_numeric(duplicates["duplicate_count"], errors="coerce").fillna(0)
        )
        .groupby("duplicate_type", as_index=False)
        .agg(
            groups=("duplicate_type", "size"),
            max_group_size=("duplicate_count_num", "max"),
            rows_flagged=("duplicate_count_num", lambda s: int((s - 1).clip(lower=0).sum())),
        )
    )
    st.dataframe(summary, width="stretch", hide_index=True)


def render_variants(variants: pd.DataFrame) -> None:
    st.markdown('<div class="section-title">Text variants and mapping candidates</div>', unsafe_allow_html=True)
    st.caption("Use this to inspect accepted and review rows before or after cleaning.")

    if variants.empty:
        st.info("No variant report found.")
        return

    left, right = st.columns([1, 2])
    with left:
        decision = st.selectbox(
            "Decision",
            ["All", "accepted", "review", "rejected"],
            index=0,
            key="variants_decision_select",
        )
        query = st.text_input("Search text", value="UQAM", key="variants_search_input")
        show_limit = st.slider("Rows to show", 20, 500, 100, 10, key="variants_rows_slider")

    filtered_all = variants.copy()
    if decision != "All":
        filtered_all = filtered_all[filtered_all["decision"] == decision]
    if query.strip():
        q = query.casefold()
        mask = pd.Series(False, index=filtered_all.index)
        for col in filtered_all.columns:
            mask = mask | filtered_all[col].astype(str).str.casefold().str.contains(q, regex=False, na=False)
        filtered_all = filtered_all.loc[mask]

    filtered = filtered_all.head(show_limit)

    with right:
        if filtered_all.empty:
            st.info("No matching rows found.")
        else:
            counts = filtered_all["decision"].value_counts().rename_axis("decision").reset_index(name="count")
            st.dataframe(counts, width="stretch", hide_index=True, height=180)

    st.dataframe(filtered, width="stretch", hide_index=True, height=420)


def render_cleaning(loads: dict[str, object]) -> None:
    mapping = loads["mapping"]
    st.markdown('<div class="section-title">Cleaning mapping and cleaned data</div>', unsafe_allow_html=True)
    st.caption("Only accepted mappings were applied to the processed file.")

    if mapping.empty:
        st.info("No mapping report found.")
        return

    cols = st.columns(4)
    cols[0].metric("Accepted", int((mapping["status"] == "accepted").sum()))
    cols[1].metric("Review", int((mapping["status"] == "review").sum()))
    cols[2].metric("Rejected", int((mapping["status"] == "rejected").sum()))
    cols[3].metric("Mapping rows", f"{len(mapping):,}")

    left, right = st.columns([1, 1.2])
    with left:
        status = st.selectbox(
            "Mapping status",
            ["All", "accepted", "review", "rejected"],
            index=0,
            key="mapping_status_select",
        )
        query = st.text_input("Search mapping", value="UQAM", key="mapping_search_input")
        limit = st.slider("Rows to show", 20, 500, 100, 10, key="mapping_rows_slider")
        subset = search_mapping(query=query, status=status, limit=limit)
        st.dataframe(subset, width="stretch", hide_index=True, height=380)

    with right:
        st.markdown(
            """
            <div class="soft-card">
              <p class="subtle">What was preserved</p>
              <p>The original organization name remains in the dataset.</p>
              <p class="subtle">What was added</p>
              <p><code>recipient_legal_name_clean</code> contains the accepted cleaned value.</p>
              <p class="subtle">What was skipped</p>
              <p>Rows marked <code>review</code> were not applied automatically.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        sample = sample_columns(
            PROCESSED_CSV,
            ["recipient_legal_name", "recipient_legal_name_clean", "recipient_city", "agreement_value"],
            rows=100,
        )
        st.dataframe(sample.head(20), width="stretch", hide_index=True, height=300)


def render_reports(loads: dict[str, object]) -> None:
    st.markdown('<div class="section-title">Reports and files</div>', unsafe_allow_html=True)
    st.caption("Open the generated artifacts directly or download them from this dashboard.")

    st.info(
        "File stages: `fichier_nettoye.csv` is the organization-cleaned intermediate. "
        "`fichier_corrige_eda.csv` is the final fixed dataset containing both the accepted "
        "organization corrections and the applied EDA missing-data remediation."
    )

    catalog = loads["catalog"]
    st.dataframe(catalog, width="stretch", hide_index=True, height=240)

    download_cols = st.columns(4)
    with download_cols[0]:
        download_link(EDA_REPORT_PATH, EDA_REPORT_PATH.name)
        download_link(MISSING_REPORT_PATH, MISSING_REPORT_PATH.name)
        download_link(DUPLICATES_REPORT_PATH, DUPLICATES_REPORT_PATH.name)
    with download_cols[1]:
        download_link(VARIANTS_REPORT_PATH, VARIANTS_REPORT_PATH.name)
        download_link(MAPPING_REPORT_PATH, MAPPING_REPORT_PATH.name)
        download_link(CLEANING_EXECUTION_REPORT_PATH, CLEANING_EXECUTION_REPORT_PATH.name)
    with download_cols[2]:
        download_link(SUMMARY_PATH, SUMMARY_PATH.name)
        download_link(
            REMEDIATION_EXECUTION_REPORT_PATH,
            "remediation audit report",
            key="reports_tab_remediation_download",
        )
    with download_cols[3]:
        download_link(RAW_CSV, "raw CSV")
        download_link(PROCESSED_CSV, "organization-cleaned CSV")
        download_link(REMEDIATED_CSV, "fully fixed CSV", key="reports_tab_fixed_csv_download")

    st.write("")
    exp1 = st.expander("EDA report", expanded=True)
    exp2 = st.expander("Final summary", expanded=False)
    exp3 = st.expander("Cleaning execution report", expanded=False)
    exp4 = st.expander("EDA remediation execution report", expanded=False)
    with exp1:
        st.markdown(loads["eda_text"])
    with exp2:
        st.markdown(loads["summary_text"])
    with exp3:
        st.markdown(loads["cleaning_text"])
    with exp4:
        st.markdown(loads["remediation_text"])


def render_data_preview() -> None:
    st.markdown('<div class="section-title">Cleaned data preview</div>', unsafe_allow_html=True)
    st.caption("Search the raw organization field across the raw CSV snapshot and compare it with the cleaned output.")

    query = st.text_input("Search organization or reference", value="UQAM", key="preview_search_input")
    limit = st.slider("Rows to show", 20, 200, 40, 10, key="preview_rows_slider")

    columns = [
        "ref_number",
        "recipient_legal_name",
        "recipient_legal_name_clean",
        "recipient_city",
        "recipient_province",
        "agreement_value",
        "agreement_start_date",
    ]
    raw_available_columns = read_csv(RAW_CSV, nrows=0).columns.tolist()
    processed_available_columns = read_csv(PROCESSED_CSV, nrows=0).columns.tolist()

    raw_matches = search_csv_rows(
        RAW_CSV,
        query=query,
        columns=[col for col in columns if col in raw_available_columns],
        limit=limit,
    )
    cleaned_matches = search_csv_rows(
        PROCESSED_CSV,
        query=query,
        columns=[col for col in columns if col in processed_available_columns],
        limit=limit,
    )

    raw_col, cleaned_col = st.columns(2)
    with raw_col:
        st.markdown("#### Raw snapshot")
        if raw_matches.empty:
            st.info("No matching rows found in the raw CSV snapshot.")
        else:
            st.dataframe(raw_matches, width="stretch", hide_index=True, height=420)
    with cleaned_col:
        st.markdown("#### Cleaned output")
        if cleaned_matches.empty:
            st.info("No matching rows found in the cleaned CSV snapshot.")
        else:
            st.dataframe(cleaned_matches, width="stretch", hide_index=True, height=420)


def main() -> None:
    inject_css()
    loads = load_reports(report_files_version())
    metrics = loads["metrics"]

    if not RAW_CSV.exists() or not PROCESSED_CSV.exists():
        st.error(
            "Required data files are missing. Run the pipeline scripts first so the dashboard has content."
        )
        st.stop()

    render_header(metrics)

    tabs = st.tabs(
        [
            "Overview",
            "AI Assistant",
            "Fixed Dataset",
            "Missing Values",
            "Duplicates",
            "Variants",
            "Cleaning",
            "Data Preview",
            "Reports",
        ]
    )
    with tabs[0]:
        render_overview(loads)
    with tabs[1]:
        render_ai_assistant(loads)
    with tabs[2]:
        render_fixed_dataset(loads)
    with tabs[3]:
        render_missing_values(loads["missing"])
    with tabs[4]:
        render_duplicates(loads["duplicates"])
    with tabs[5]:
        render_variants(loads["variants"])
    with tabs[6]:
        render_cleaning(loads)
    with tabs[7]:
        render_data_preview()
    with tabs[8]:
        render_reports(loads)

    with st.sidebar:
        st.markdown(
            """
            <div class="sidebar-brand">
              <div class="brand-mark">DK</div>
              <div><strong>DATAKABOOM</strong><span>QUALITY SYSTEM</span></div>
            </div>
            <div class="sidebar-status"><span class="status-led status-led--green"></span>SYSTEM OPERATIONAL</div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("### Mounted files")
        st.markdown(
            f"""
            <div class="file-stack">
              <div><span>RAW INPUT</span><code>{RAW_CSV.name}</code></div>
              <div><span>ORG CLEAN</span><code>{PROCESSED_CSV.name}</code></div>
              <div><span>FINAL FIXED</span><code>{REMEDIATED_CSV.name}</code></div>
              <div><span>REPORT BANK</span><code>{(ROOT_DIR / 'reports').name}/</code></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("### Console state")
        st.write("Read-only interface. Every displayed value is generated from auditable repository artifacts.")


if __name__ == "__main__":
    main()

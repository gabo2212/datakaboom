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
    SUMMARY_PATH,
    VARIANTS_REPORT_PATH,
    assignment_checklist,
    load_summary_metrics,
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
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(65, 105, 225, 0.18), transparent 28%),
                radial-gradient(circle at top right, rgba(46, 139, 87, 0.16), transparent 26%),
                linear-gradient(180deg, #0f172a 0%, #111827 46%, #0b1220 100%);
            color: #e5eefb;
        }
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0b1020 0%, #10192d 100%);
            border-right: 1px solid rgba(255, 255, 255, 0.08);
        }
        section[data-testid="stSidebar"] * {
            color: #e5eefb;
        }
        .block-container {
            padding-top: 1.1rem;
            padding-bottom: 2rem;
        }
        .hero {
            padding: 1.3rem 1.4rem;
            border-radius: 22px;
            background: linear-gradient(135deg, rgba(18, 27, 54, 0.94), rgba(11, 18, 32, 0.92));
            border: 1px solid rgba(148, 163, 184, 0.2);
            box-shadow: 0 24px 80px rgba(0, 0, 0, 0.28);
            margin-bottom: 1rem;
        }
        .eyebrow {
            text-transform: uppercase;
            letter-spacing: 0.18em;
            font-size: 0.72rem;
            color: #93c5fd;
            margin-bottom: 0.5rem;
        }
        .hero h1 {
            font-size: 2.2rem;
            line-height: 1.05;
            margin: 0 0 0.55rem 0;
            color: #f8fbff;
        }
        .hero p {
            margin: 0;
            color: #c7d2fe;
            max-width: 960px;
        }
        .soft-card {
            background: rgba(15, 23, 42, 0.72);
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 18px;
            padding: 1rem 1rem 0.75rem 1rem;
            box-shadow: 0 10px 35px rgba(0, 0, 0, 0.16);
        }
        .section-title {
            font-size: 1.05rem;
            font-weight: 700;
            margin-bottom: 0.4rem;
            color: #f8fafc;
        }
        .subtle {
            color: #9fb1cf;
            font-size: 0.92rem;
        }
        div[data-testid="metric-container"] {
            background: rgba(15, 23, 42, 0.72);
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 18px;
            padding: 0.8rem 0.9rem;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.12);
        }
        div[data-testid="metric-container"] label {
            color: #9fb1cf !important;
        }
        div[data-testid="metric-container"] [data-testid="stMetricValue"] {
            color: #f8fafc !important;
        }
        .status-good {
            color: #86efac;
            font-weight: 700;
        }
        .status-warn {
            color: #fbbf24;
            font-weight: 700;
        }
        .status-bad {
            color: #fca5a5;
            font-weight: 700;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


REPORT_INPUT_PATHS = (
    SUMMARY_PATH,
    EDA_REPORT_PATH,
    CLEANING_EXECUTION_REPORT_PATH,
    MISSING_REPORT_PATH,
    DUPLICATES_REPORT_PATH,
    VARIANTS_REPORT_PATH,
    MAPPING_REPORT_PATH,
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
    }


def file_size_label(path: Path) -> str:
    if not path.exists():
        return "Missing"
    return pretty_bytes(path.stat().st_size)


def download_link(path: Path, label: str) -> None:
    if not path.exists():
        st.caption(f"{label}: missing")
        return
    st.download_button(
        label=f"Download {label}",
        data=path.read_bytes(),
        file_name=path.name,
        mime="text/csv" if path.suffix == ".csv" else "text/markdown",
        width="stretch",
    )


def render_header(metrics: dict[str, int]) -> None:
    st.markdown(
        """
        <div class="hero">
          <div class="eyebrow">Assignment dashboard</div>
          <h1>Big File EDA and Cleaning</h1>
          <p>
            Review the raw workbook, the EDA outputs, the accepted cleaning decisions,
            and the cleaned dataset in one place. This dashboard is read-only and built
            from the generated reports.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Rows", f"{metrics.get('raw_rows', 0):,}")
    c2.metric("Columns", f"{metrics.get('columns', 0):,}")
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
            <p class="subtle">Processed dataset</p>
            <p>{PROCESSED_CSV.name} ({file_size_label(PROCESSED_CSV)})</p>
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
        "duplicates, text variants, accepted cleaning mapping, cleaned output, and a final summary."
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
            Efficient retrieval: all seven generated reports are indexed, context is capped at
            {MAX_CONTEXT_CHARS:,} characters, and the 209 MB cleaned CSV is scanned only when an
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
              <p>`recipient_legal_name_clean` contains the accepted cleaned value.</p>
              <p class="subtle">What was skipped</p>
              <p>Rows marked `review` were not applied automatically.</p>
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

    catalog = loads["catalog"]
    st.dataframe(catalog, width="stretch", hide_index=True, height=240)

    download_cols = st.columns(3)
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
        download_link(RAW_CSV, RAW_CSV.name)
        download_link(PROCESSED_CSV, PROCESSED_CSV.name)

    st.write("")
    exp1 = st.expander("EDA report", expanded=True)
    exp2 = st.expander("Final summary", expanded=False)
    exp3 = st.expander("Cleaning execution report", expanded=False)
    with exp1:
        st.markdown(loads["eda_text"])
    with exp2:
        st.markdown(loads["summary_text"])
    with exp3:
        st.markdown(loads["cleaning_text"])


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
        render_missing_values(loads["missing"])
    with tabs[3]:
        render_duplicates(loads["duplicates"])
    with tabs[4]:
        render_variants(loads["variants"])
    with tabs[5]:
        render_cleaning(loads)
    with tabs[6]:
        render_data_preview()
    with tabs[7]:
        render_reports(loads)

    with st.sidebar:
        st.markdown("### Quick facts")
        st.markdown(f"- Raw CSV: `{RAW_CSV.name}`")
        st.markdown(f"- Processed CSV: `{PROCESSED_CSV.name}`")
        st.markdown(f"- Reports folder: `{(ROOT_DIR / 'reports').name}/`")
        st.markdown("### Status")
        st.write("Everything shown here is read-only and generated from the reports in this repository.")


if __name__ == "__main__":
    main()

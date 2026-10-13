import io
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Personal Loan Approval Analytics",
    page_icon="📊",
    layout="wide",
)

# ---------- Styling ----------
st.markdown(
    """
    <style>
    .main-header {font-size: 2rem; font-weight: 750; margin-bottom: .2rem;}
    .sub-header {color: #64748b; margin-bottom: 1.2rem;}
    div[data-testid="stMetric"] {
        background: #f8fafc; border: 1px solid #e2e8f0;
        padding: 14px; border-radius: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="main-header">Personal Loan Approval Analytics</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Explore application patterns, applicant profiles, credit risk indicators, and data-driven recommendations.</div>',
    unsafe_allow_html=True,
)

# ---------- Data loading ----------
DEFAULT_FILES = [
    Path("loan_approval_data.csv"),
    Path("Loan_approval_data_2025.csv.xlsx"),
    Path("Loan approval data 2025.csv.xlsx"),
    Path("loan_approval_data.xlsx"),
]

@st.cache_data(show_spinner=False)
def load_uploaded_file(file_bytes: bytes, file_name: str) -> pd.DataFrame:
    """Load CSV or Excel data from uploaded bytes."""
    name = file_name.lower()
    buffer = io.BytesIO(file_bytes)
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(buffer)
    if name.endswith(".csv"):
        try:
            return pd.read_csv(buffer)
        except UnicodeDecodeError:
            buffer.seek(0)
            return pd.read_csv(buffer, encoding="latin-1")
    raise ValueError("Unsupported file format. Upload a CSV or Excel file.")

def normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame.columns = (
        frame.columns.astype(str).str.strip().str.lower()
        .str.replace(r"\s+", "_", regex=True)
    )
    return frame

def money(value):
    if pd.isna(value):
        return "N/A"
    return f"{value:,.0f}"

def safe_mean(frame, col):
    return pd.to_numeric(frame[col], errors="coerce").mean() if col in frame.columns else float("nan")

uploaded = st.sidebar.file_uploader(
    "Upload loan application data",
    type=["csv", "xlsx", "xls"],
    help="Upload the dataset used in your notebook. CSV and Excel are supported.",
)

df = None
if uploaded is not None:
    try:
        df = load_uploaded_file(uploaded.getvalue(), uploaded.name)
    except Exception as exc:
        st.error(f"Could not read the uploaded file: {exc}")
        st.stop()
else:
    for candidate in DEFAULT_FILES:
        if candidate.exists():
            try:
                if candidate.suffix.lower() in (".xlsx", ".xls"):
                    df = pd.read_excel(candidate)
                else:
                    df = pd.read_csv(candidate)
                st.sidebar.success(f"Using local file: {candidate.name}")
                break
            except Exception:
                continue

if df is None:
    st.info(
        "Upload your loan dataset using the sidebar to begin. "
        "The app accepts CSV, XLSX, and XLS files."
    )
    st.markdown("### Expected columns")
    st.write(
        "The analysis works best with `loan_status`, `credit_score`, `annual_income`, "
        "`loan_amount`, `loan_intent`, `occupation_status`, `product_type`, "
        "`age`, `current_debt`, and `debt_to_income_ratio`."
    )
    st.stop()

df = normalize_columns(df)
original_rows = len(df)

# Numeric conversion for common analytics columns
numeric_candidates = [
    "age", "years_employed", "annual_income", "credit_score",
    "credit_history_years", "savings_assets", "current_debt",
    "defaults_on_file", "delinquencies_last_2yrs", "derogatory_marks",
    "loan_amount", "interest_rate", "debt_to_income_ratio",
    "loan_to_income_ratio", "payment_to_income_ratio", "loan_status",
]
for col in numeric_candidates:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

st.sidebar.header("Filters")
filtered = df.copy()

def add_multiselect_filter(column, label):
    global filtered
    if column in filtered.columns:
        values = sorted(filtered[column].dropna().astype(str).unique().tolist())
        selected = st.sidebar.multiselect(label, values, default=values)
        filtered = filtered[filtered[column].astype(str).isin(selected)]

add_multiselect_filter("occupation_status", "Occupation")
add_multiselect_filter("product_type", "Product type")
add_multiselect_filter("loan_intent", "Loan purpose")

if "credit_score" in filtered.columns and filtered["credit_score"].notna().any():
    minimum = int(filtered["credit_score"].min())
    maximum = int(filtered["credit_score"].max())
    if minimum < maximum:
        score_range = st.sidebar.slider(
            "Credit score range", minimum, maximum, (minimum, maximum)
        )
        filtered = filtered[
            filtered["credit_score"].between(score_range[0], score_range[1])
        ]

if filtered.empty:
    st.warning("No records match the selected filters. Adjust the filters in the sidebar.")
    st.stop()

# ---------- Status mapping ----------
status_col = "loan_status" if "loan_status" in filtered.columns else None
status_labels = {}
if status_col:
    codes = sorted(df[status_col].dropna().unique().tolist())
    if len(codes) == 2:
        st.sidebar.header("Status interpretation")
        st.sidebar.caption("Confirm these labels against your dataset's data dictionary.")
        code_options = {str(code): code for code in codes}
        approved_code_text = st.sidebar.selectbox(
            "Which code means Approved?",
            options=list(code_options.keys()),
            index=(list(code_options.keys()).index("0") if "0" in code_options else 0),
        )
        approved_code = code_options[approved_code_text]
        rejected_code = next(code for code in codes if code != approved_code)
        status_labels = {
            approved_code: "Approved",
            rejected_code: "Rejected",
        }
    else:
        st.sidebar.warning("Expected two distinct loan_status codes; displaying recorded codes.")
        status_labels = {code: f"Status {code}" for code in codes}

if status_col:
    filtered["loan_status_label"] = filtered[status_col].map(status_labels).fillna("Unknown")
    df["loan_status_label"] = df[status_col].map(status_labels).fillna("Unknown")

# ---------- Overview ----------
st.subheader("Executive overview")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Applications", f"{len(filtered):,}")
if status_col and status_labels:
    approved_count = int((filtered["loan_status_label"] == "Approved").sum())
    rejected_count = int((filtered["loan_status_label"] == "Rejected").sum())
    approval_rate = approved_count / len(filtered) * 100 if len(filtered) else 0
    rejection_rate = rejected_count / len(filtered) * 100 if len(filtered) else 0
    m2.metric("Approval rate", f"{approval_rate:.1f}%")
    m3.metric("Rejection rate", f"{rejection_rate:.1f}%")
else:
    m2.metric("Approval rate", "N/A")
    m3.metric("Rejection rate", "N/A")
m4.metric(
    "Average credit score",
    f"{safe_mean(filtered, 'credit_score'):.1f}"
    if "credit_score" in filtered.columns and pd.notna(safe_mean(filtered, "credit_score"))
    else "N/A",
)

if status_col and status_labels:
    st.caption(
        "Status mapping currently used: "
        + ", ".join(f"{code} = {label}" for code, label in status_labels.items())
        + ". Verify this mapping with the dataset documentation before presenting results."
    )

# ---------- Tabs ----------
tab_overview, tab_applicants, tab_risk, tab_recommendations, tab_data = st.tabs(
    ["Overview", "Applicant analysis", "Credit & risk", "Recommendations", "Data quality"]
)

with tab_overview:
    left, right = st.columns(2)
    with left:
        if status_col:
            status_summary = (
                filtered["loan_status_label"].value_counts(dropna=False)
                .rename_axis("Loan status").reset_index(name="Applications")
            )
            fig = px.pie(
                status_summary, names="Loan status", values="Applications",
                hole=0.48, title="Application outcome distribution",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No `loan_status` column was found.")
    with right:
        if "loan_intent" in filtered.columns:
            purpose = filtered["loan_intent"].value_counts().reset_index()
            purpose.columns = ["Loan purpose", "Applications"]
            fig = px.bar(
                purpose.sort_values("Applications", ascending=True),
                x="Applications", y="Loan purpose", orientation="h",
                title="Applications by loan purpose", text="Applications",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No `loan_intent` column was found.")

    left, right = st.columns(2)
    with left:
        if "age" in filtered.columns:
            age_data = filtered.dropna(subset=["age"]).copy()
            if not age_data.empty:
                bins = [0, 17, 25, 35, 45, 60, float("inf")]
                labels = ["Under 18", "18–25", "26–35", "36–45", "46–60", "61+"]
                age_data["Age group"] = pd.cut(
                    age_data["age"], bins=bins, labels=labels, include_lowest=True
                )
                age_counts = (
                    age_data["Age group"].value_counts(sort=False)
                    .reindex(labels, fill_value=0).rename_axis("Age group")
                    .reset_index(name="Applications")
                )
                fig = px.bar(
                    age_counts, x="Age group", y="Applications",
                    title="Applications by age group", text="Applications",
                )
                st.plotly_chart(fig, use_container_width=True)
    with right:
        if {"annual_income", "loan_amount"}.issubset(filtered.columns):
            plot_data = filtered.dropna(subset=["annual_income", "loan_amount"])
            if not plot_data.empty:
                fig = px.scatter(
                    plot_data, x="annual_income", y="loan_amount",
                    color="loan_status_label" if "loan_status_label" in plot_data.columns else None,
                    hover_data=[c for c in ["loan_intent", "credit_score", "occupation_status"] if c in plot_data.columns],
                    title="Annual income vs requested loan amount",
                    labels={"annual_income": "Annual income", "loan_amount": "Requested loan amount"},
                    opacity=0.65,
                )
                st.plotly_chart(fig, use_container_width=True)

with tab_applicants:
    st.subheader("Applicant profile")
    profile_cols = [c for c in [
        "age", "occupation_status", "years_employed", "annual_income",
        "credit_score", "credit_history_years", "savings_assets",
        "current_debt", "product_type", "loan_intent", "loan_amount",
    ] if c in filtered.columns]
    if profile_cols:
        st.dataframe(filtered[profile_cols].head(1000), use_container_width=True, hide_index=True)
        st.caption("Showing up to 1,000 filtered records for responsiveness.")
    else:
        st.info("No recognized applicant profile columns were found.")

    if {"loan_intent", "loan_status_label"}.issubset(filtered.columns):
        purpose_status = (
            filtered.groupby(["loan_intent", "loan_status_label"], dropna=False)
            .size().reset_index(name="Applications")
        )
        fig = px.bar(
            purpose_status, x="loan_intent", y="Applications",
            color="loan_status_label", barmode="group",
            title="Application outcomes by loan purpose",
            labels={"loan_intent": "Loan purpose", "loan_status_label": "Loan status"},
        )
        fig.update_layout(xaxis_tickangle=-25)
        st.plotly_chart(fig, use_container_width=True)

with tab_risk:
    st.subheader("Credit and affordability indicators")
    if {"credit_score", "loan_status_label"}.issubset(filtered.columns):
        credit_summary = (
            filtered.groupby("loan_status_label")["credit_score"]
            .agg(Applications="count", Mean="mean", Median="median", Minimum="min", Maximum="max")
            .round(2).reset_index()
        )
        st.dataframe(credit_summary, use_container_width=True, hide_index=True)
        fig = px.box(
            filtered.dropna(subset=["credit_score"]),
            x="loan_status_label", y="credit_score", points="outliers",
            title="Credit score distribution by outcome",
            labels={"loan_status_label": "Loan status", "credit_score": "Credit score"},
        )
        st.plotly_chart(fig, use_container_width=True)

    risk_metrics = [
        ("debt_to_income_ratio", "Debt-to-income ratio"),
        ("loan_to_income_ratio", "Loan-to-income ratio"),
        ("payment_to_income_ratio", "Payment-to-income ratio"),
        ("current_debt", "Current debt"),
        ("loan_amount", "Loan amount"),
        ("interest_rate", "Interest rate"),
    ]
    available_risk = [(c, label) for c, label in risk_metrics if c in filtered.columns]
    if available_risk:
        selected_metric = st.selectbox(
            "Select a risk indicator", options=[x[0] for x in available_risk],
            format_func=lambda x: dict(available_risk)[x],
        )
        if "loan_status_label" in filtered.columns:
            fig = px.box(
                filtered.dropna(subset=[selected_metric]),
                x="loan_status_label", y=selected_metric, points="outliers",
                title=f"{dict(available_risk)[selected_metric]} by loan outcome",
            )
        else:
            fig = px.histogram(
                filtered.dropna(subset=[selected_metric]), x=selected_metric,
                title=f"Distribution of {dict(available_risk)[selected_metric]}",
            )
        st.plotly_chart(fig, use_container_width=True)

    st.warning(
        "These charts are descriptive analytics, not a validated credit-scoring model. "
        "Do not use a single variable or this dashboard alone to make lending decisions."
    )

with tab_recommendations:
    st.subheader("Data-driven business recommendations")
    st.write("Recommendations below are analytical prompts based on patterns in the filtered data. Validate them against policy, regulation, and additional evidence before acting.")

    recommendations = []
    if status_col and status_labels:
        outcome_counts = filtered["loan_status_label"].value_counts()
        if "Rejected" in outcome_counts and len(filtered):
            rate = outcome_counts.get("Rejected", 0) / len(filtered) * 100
            recommendations.append(
                f"**Monitor rejected applications:** {rate:.1f}% of filtered records are labelled Rejected. "
                "Review rejection reasons and check whether applicants are being assessed consistently."
            )

    if {"loan_intent", "loan_status_label"}.issubset(filtered.columns):
        purpose_rates = pd.crosstab(
            filtered["loan_intent"], filtered["loan_status_label"], normalize="index"
        ).mul(100)
        if "Rejected" in purpose_rates.columns and not purpose_rates.empty:
            purpose_rates = purpose_rates.sort_values("Rejected", ascending=False)
            highest = purpose_rates.index[0]
            highest_rate = purpose_rates.iloc[0]["Rejected"]
            recommendations.append(
                f"**Review outcomes by loan purpose:** `{highest}` has the highest observed rejection share "
                f"({highest_rate:.1f}%) among filtered purposes. Examine the underlying reasons and applicant mix "
                "before changing product rules."
            )

    if {"credit_score", "loan_status_label"}.issubset(filtered.columns):
        score_means = filtered.groupby("loan_status_label")["credit_score"].mean()
        if "Approved" in score_means.index and "Rejected" in score_means.index:
            delta = score_means["Approved"] - score_means["Rejected"]
            recommendations.append(
                f"**Validate credit-score patterns:** the mean credit-score difference "
                f"(Approved minus Rejected) is {delta:.1f} points. Check that status codes are mapped correctly "
                "and assess credit score alongside debt burden, income stability, and repayment history."
            )

    if {"debt_to_income_ratio", "loan_status_label"}.issubset(filtered.columns):
        dti_means = filtered.groupby("loan_status_label")["debt_to_income_ratio"].mean()
        if "Approved" in dti_means.index and "Rejected" in dti_means.index:
            recommendations.append(
                f"**Review affordability indicators:** mean debt-to-income ratio is "
                f"{dti_means['Approved']:.3f} for Approved records and {dti_means['Rejected']:.3f} for Rejected records. "
                "Confirm the ratio definition and investigate outliers; establish thresholds only through validated policy."
            )

    if {"annual_income", "loan_amount"}.issubset(filtered.columns):
        valid = filtered.dropna(subset=["annual_income", "loan_amount"])
        if not valid.empty:
            median_income = valid["annual_income"].median()
            median_loan = valid["loan_amount"].median()
            recommendations.append(
                f"**Assess requested loan size against income:** median annual income is {money(median_income)} "
                f"and median requested loan amount is {money(median_loan)} in the filtered sample. "
                "Segment applications by loan-to-income ratio and test whether repayment capacity differs across segments."
            )

    if "defaults_on_file" in filtered.columns:
        default_share = (filtered["defaults_on_file"].fillna(0) > 0).mean() * 100
        recommendations.append(
            f"**Strengthen repayment-history review:** {default_share:.1f}% of filtered records have a positive "
            "`defaults_on_file` value. Verify how this field is encoded and compare outcomes for applicants with and without recorded defaults."
        )

    if recommendations:
        for i, recommendation in enumerate(recommendations, 1):
            st.markdown(f"{i}. {recommendation}")
    else:
        st.info("Upload or select data containing the expected loan and outcome fields to generate more specific recommendations.")

    st.markdown("#### Recommended next steps")
    st.markdown(
        """
        - Confirm the meaning of `loan_status` using the dataset's data dictionary.
        - Add documented rejection reasons and monitor approval/rejection trends over time.
        - Validate affordability and credit indicators against actual repayment outcomes.
        - Test for inconsistent outcomes across relevant applicant segments and review fairness and regulatory obligations.
        - Treat this dashboard as decision support; do not automate lending decisions from descriptive patterns alone.
        """
    )

with tab_data:
    st.subheader("Data quality checks")
    quality = pd.DataFrame({
        "Data type": df.dtypes.astype(str),
        "Missing values": df.isna().sum(),
        "Missing (%)": (df.isna().mean() * 100).round(2),
        "Unique values": df.nunique(dropna=True),
    })
    q1, q2, q3 = st.columns(3)
    q1.metric("Rows", f"{len(df):,}")
    q2.metric("Columns", f"{len(df.columns):,}")
    q3.metric("Duplicate rows", f"{int(df.duplicated().sum()):,}")
    st.dataframe(quality, use_container_width=True)

    missing = quality[quality["Missing values"] > 0]
    if missing.empty:
        st.success("No missing values detected in the loaded dataset.")
    else:
        st.warning(f"{len(missing)} column(s) contain missing values.")
        st.dataframe(missing, use_container_width=True)

    checks = []

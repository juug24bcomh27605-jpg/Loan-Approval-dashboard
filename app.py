import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Loan Approval Analysis Dashboard", page_icon="💳", layout="wide")
st.title("💳 Loan Approval Analysis Dashboard")
st.caption("Explore application patterns, customer profiles, and recorded loan outcomes.")

STATUS_LABELS = {0: "Approved", 1: "Default"}

@st.cache_data
def read_uploaded_file(file):
    if file.name.lower().endswith((".xlsx", ".xls")):
        data = pd.read_excel(file)
    else:
        data = pd.read_csv(file)
    data.columns = data.columns.astype(str).str.strip()
    for col in ["occupation_status", "product_type", "loan_intent"]:
        if col in data.columns:
            data[col] = data[col].astype("string").str.strip()
    if "loan_status" in data.columns:
        data["Loan Status Label"] = data["loan_status"].map(STATUS_LABELS).fillna("Unknown status")
    return data

uploaded = st.sidebar.file_uploader("Upload your loan dataset", type=["csv", "xlsx", "xls"])
if uploaded is None:
    st.info("Upload your loan dataset in the sidebar to start exploring the dashboard.")
    st.stop()

df = read_uploaded_file(uploaded)
required = ["loan_status", "age", "annual_income", "credit_score", "loan_amount"]
missing = [col for col in required if col not in df.columns]
if missing:
    st.error("Required columns missing: " + ", ".join(missing))
    st.write("Columns found in your file:", df.columns.tolist())
    st.stop()

st.sidebar.header("Filters")
filtered = df.copy()

for column, label in [
    ("loan_intent", "Loan purpose"),
    ("product_type", "Product type"),
    ("occupation_status", "Occupation status"),
]:
    if column in filtered.columns:
        options = sorted(filtered[column].dropna().astype(str).unique().tolist())
        selected = st.sidebar.multiselect(label, options, default=options)
        if selected:
            filtered = filtered[filtered[column].astype(str).isin(selected)]
        else:
            filtered = filtered.iloc[0:0]

if "Loan Status Label" in filtered.columns:
    options = sorted(filtered["Loan Status Label"].dropna().unique().tolist())
    selected = st.sidebar.multiselect("Recorded outcome", options, default=options)
    if selected:
        filtered = filtered[filtered["Loan Status Label"].isin(selected)]
    else:
        filtered = filtered.iloc[0:0]

if filtered.empty:
    st.warning("No records match your filters. Please change the selections.")
    st.stop()

total = len(filtered)
approved = int((filtered["loan_status"] == 0).sum())
defaults = int((filtered["loan_status"] == 1).sum())

c1, c2, c3, c4 = st.columns(4)
c1.metric("Applications", f"{total:,}")
c2.metric("Approved (code 0)", f"{approved:,}", f"{approved / total * 100:.1f}% of filtered")
c3.metric("Default (code 1)", f"{defaults:,}", f"{defaults / total * 100:.1f}% of filtered")
c4.metric("Average credit score", f"{filtered['credit_score'].mean():.1f}")

st.divider()
left, right = st.columns(2)

with left:
    status_counts = filtered["Loan Status Label"].value_counts().rename_axis("Outcome").reset_index(name="Applications")
    fig = px.pie(status_counts, names="Outcome", values="Applications", hole=0.5,
                 title="Distribution of Recorded Outcomes")
    st.plotly_chart(fig, use_container_width=True)

with right:
    if "loan_intent" in filtered.columns:
        purpose_counts = filtered.groupby(["loan_intent", "Loan Status Label"]).size().reset_index(name="Applications")
        fig = px.bar(purpose_counts, x="loan_intent", y="Applications", color="Loan Status Label",
                     barmode="group", title="Applications by Loan Purpose and Outcome",
                     labels={"loan_intent": "Loan purpose"})
        fig.update_layout(xaxis_tickangle=-25)
        st.plotly_chart(fig, use_container_width=True)

left, right = st.columns(2)
with left:
    fig = px.histogram(filtered, x="credit_score", color="Loan Status Label", barmode="overlay",
                       opacity=0.65, nbins=30, title="Credit Score Distribution by Outcome")
    st.plotly_chart(fig, use_container_width=True)

with right:
    if "debt_to_income_ratio" in filtered.columns:
        fig = px.scatter(filtered, x="debt_to_income_ratio", y="credit_score",
                         color="Loan Status Label", opacity=0.65,
                         hover_data=[c for c in ["annual_income", "current_debt", "loan_amount"] if c in filtered.columns],
                         title="Credit Score vs Debt-to-Income Ratio",
                         labels={"debt_to_income_ratio": "Debt-to-income ratio", "credit_score": "Credit score"})
        st.plotly_chart(fig, use_container_width=True)

left, right = st.columns(2)
with left:
    fig = px.box(filtered, x="Loan Status Label", y="annual_income", color="Loan Status Label",
                 title="Annual Income by Recorded Outcome")
    st.plotly_chart(fig, use_container_width=True)
with right:
    fig = px.histogram(filtered, x="loan_amount", color="Loan Status Label", barmode="overlay",
                       opacity=0.6, nbins=30, title="Loan Amount Distribution by Outcome")
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Filtered application records")
st.caption("Showing up to 500 rows.")
st.dataframe(filtered.head(500), use_container_width=True, hide_index=True)
st.download_button("Download filtered records as CSV",
                   data=filtered.to_csv(index=False).encode("utf-8"),
                   file_name="filtered_loan_applications.csv", mime="text/csv")

with st.expander("About this dashboard"):
    st.write("This dashboard supports exploratory analysis of the supplied dataset. The current labels are code 0 = Approved and code 1 = Default; verify this mapping against the original dataset documentation. Charts show patterns and associations, not causation.")

# run using streamlit run zip_choropleth.py

import streamlit as st
st.set_page_config(layout="wide", menu_items={"Report a bug" : "https://github.com/MaxObes/econ-570-final-project", "About" : "Andrew VanDerKolk and Max Oberbrunner's Econ 570 Final Project."})

import pandas as pd
import zipfile
import pyarrow as pa
import pyarrow.csv
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib.ticker as ticker
import matplotlib as mpl
import plotly.express as px

# --- Cached Data Loading ---
@st.cache_data(show_spinner=False)
def load_data():
    with zipfile.ZipFile("P00000001-ALL.zip", "r") as zip_ref:
        csv_data = zip_ref.read("P00000001-ALL.csv")
    df = pa.csv.read_csv(pa.BufferReader(csv_data)).to_pandas()
    state_codes = ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"]
    df = df[df["contbr_st"].isin(state_codes)]
    df["contb_receipt_dt"] = pd.to_datetime(df["contb_receipt_dt"], format="%d-%b-%y")
    return df

with st.spinner("Loading data..."):
    cf_df = load_data()

# --- Cached Grouped Data ---
@st.cache_data(show_spinner=False)
def get_monthly_grouped(df):
    df = df.copy()
    df["month"] = df["contb_receipt_dt"].dt.to_period("M").astype(str)
    return df.groupby(["month", "cand_nm"])["contb_receipt_amt"].sum().reset_index()

with st.spinner("Processing data..."):
    monthly_grouped = get_monthly_grouped(cf_df)

st.title("Campaign Finance Trends (2024 Presidential Election)")

# --- Tabs ---
tab1, tab2 = st.tabs(["Campaign Donations By State", "Campaign Donations Over Time"])

with tab1:
    col1, col2, col3 = st.columns([0.15, 0.7, 0.15], border=False)
    with col2:
        with st.container(border=True, ):
            st.subheader("Campaign Contributions by Candidate and State")
            sort_by = st.radio("Sort bars by:", ["Total Contributions", "State (Alphabetical)"], horizontal=True)

            grouped = cf_df.groupby(["contbr_st", "contbr_zip", "cand_nm"])["contb_receipt_amt"].sum().reset_index()
            state_cand_sums = grouped.groupby(["contbr_st", "cand_nm"])["contb_receipt_amt"].sum().reset_index()
            if sort_by == "Total Contributions":
                state_cand_sums = state_cand_sums.sort_values(by="contb_receipt_amt", ascending=False)
            else:
                state_cand_sums = state_cand_sums.sort_values(by="contbr_st")

            fig = px.bar(
                state_cand_sums,
                x="contbr_st",
                y="contb_receipt_amt",
                color="cand_nm",
                labels={
                    "contbr_st": "State",
                    "contb_receipt_amt": "Total Contributions ($)",
                    "cand_nm": "Candidate"
                },
                title="Campaign Contributions by Candidate and State",
                hover_data={"contb_receipt_amt": ":,.0f"},
                
            )

            fig.update_layout(
                            xaxis_title="State",
                yaxis_title="Total Contributions ($ Millions)",
                yaxis_tickformat=".2s",
                legend_title="Candidate",
                bargap=0.15,
                height=700
            )
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        col1, col2, col3 = st.columns([0.15, 0.7, 0.15], border=True)

        with col1:
            with st.container(height=700):
                cand_totals = monthly_grouped.groupby("cand_nm")["contb_receipt_amt"].sum().sort_values(ascending=False)
                all_candidates_sorted = cand_totals.index.tolist()

                st.markdown("**Select candidates to display:**")
                select_all = st.button("Select All")
                deselect_all = st.button("Deselect All")

                # Session state to hold selected candidates
                if "selected_candidates" not in st.session_state:
                    st.session_state.selected_candidates = [cand for cand in all_candidates_sorted if cand in ["Trump, Donald J.", "Harris, Kamala"]]

                if select_all:
                    st.session_state.selected_candidates = all_candidates_sorted
                if deselect_all:
                    st.session_state.selected_candidates = []

                selected_candidates = []
                for cand in all_candidates_sorted:
                    if st.checkbox(label=cand, value=(cand in st.session_state.selected_candidates), key=f"checkbox_{cand}"):
                        selected_candidates.append(cand)
                st.session_state.selected_candidates = selected_candidates

        with col2:
            st.title("Monthly Donation Trends (2024 Election)")
            st.subheader("Donation Totals by Month and Candidate")

            filtered_data = monthly_grouped[monthly_grouped["cand_nm"].isin(selected_candidates)]

            # Sort candidates in legend by total contributions
            legend_order = filtered_data.groupby("cand_nm")["contb_receipt_amt"].sum().sort_values(ascending=False).index.tolist()
            filtered_data["cand_nm"] = pd.Categorical(filtered_data["cand_nm"], categories=legend_order, ordered=True)

            fig, ax = plt.subplots(figsize=(12, 5))
            sns.lineplot(data=filtered_data, x="month", y="contb_receipt_amt", hue="cand_nm", ax=ax)
            ax.set_title("Monthly Donation Totals by Candidate", fontsize=12)
            ax.set_xlabel("Month", fontsize=10)
            ax.set_ylabel("Total Contributions ($ Millions)", fontsize=10)
            ax.legend(title="Candidate", loc='upper left', bbox_to_anchor=(1.05, 1))
            ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f'{int(x / 1e6)}'))
            plt.xticks(rotation=45, fontsize=8)
            plt.yticks(fontsize=8)
            plt.tight_layout()
            st.pyplot(fig)
        
        col3.border = False
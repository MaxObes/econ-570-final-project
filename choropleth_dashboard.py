# run using streamlit run choropleth_dashboard.py

# --- Streamlit Page Setup ---
import streamlit as st
st.set_page_config(
    page_title="Group 25 Econ 570",
    layout="wide", 
    menu_items={
        "Report a bug" : "https://github.com/MaxObes/econ-570-final-project", 
        "About" : "Andrew VanDerKolk and Max Oberbrunner's Econ 570 Final Project."
    }
)

# --- Imports ---
import pandas as pd
import geopandas as gpd
import zipfile
import pyarrow as pa
import pyarrow.csv
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib.ticker as ticker
import json
import numpy as np
import requests
import plotly.express as px

# --- Cached FEC Contribution Data Loading ---
@st.cache_data(show_spinner=False)
def load_data():
    # Read and decompress raw FEC CSV donation data
    with zipfile.ZipFile("P00000001-ALL.zip", "r") as zip_ref:
        csv_data = zip_ref.read("P00000001-ALL.csv")
    df = pa.csv.read_csv(pa.BufferReader(csv_data)).to_pandas()

    # Filter to 50 U.S. states only
    state_codes = [
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA",
        "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT",
        "VA", "WA", "WV", "WI", "WY"
        ]
    df = df[df["contbr_st"].isin(state_codes)]

    # Convert date field and filter to positive donations only (remove outflows)
    df["contb_receipt_dt"] = pd.to_datetime(df["contb_receipt_dt"], format="%d-%b-%y")
    df = df[df["contb_receipt_amt"] > 0] 
    return df

# --- Load raw data once and reuse ---
with st.spinner("Loading data..."):
    cf_df = load_data()

# --- Aggregate Donations by Candidate and Month ---
@st.cache_data(show_spinner=False)
def get_monthly_grouped(df):
    df = df.copy()
    df["month"] = df["contb_receipt_dt"].dt.to_period("M").astype(str)
    return df.groupby(["month", "cand_nm"])["contb_receipt_amt"].sum().reset_index()

with st.spinner("Processing data..."):
    monthly_grouped = get_monthly_grouped(cf_df)

# --- Main Title ---
st.title("Campaign Finance Trends (2024 Presidential Election)")

# --- Load ZIP to County Crosswalk from HUD API ---
@st.cache_data(show_spinner=False)
def load_zip_to_county_crosswalk():
    API_KEY = st.secrets["hud_api_key"]
    headers = {"Authorization": f"Bearer {API_KEY}"}
    url = "https://www.huduser.gov/hudapi/public/usps?type=2&query=All"
    response = requests.get(url, headers=headers)
    df = pd.DataFrame(response.json()["data"]["results"])

    # Ensure proper ZIP and GEOID formatting
    df["zip"] = df["zip"].astype(str)
    df["geoid"] = df["geoid"].astype(str)

    # Retain highest ratio match per ZIP code
    df = df.sort_values("tot_ratio", ascending=False)
    df = df.drop_duplicates("zip")
    return df

# --- Tab Setup ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Campaign Donations by State", 
    "Campaign Donations Over Time", 
    "Campaign Donations by County Choropleth", 
    "Source Code", 
    "Project Report"
])

# --- Tab 1: Bar Chart of Contributions by State and Candidate ---
with tab1:
    # Define layout columns
    col1, col2, col3 = st.columns([0.15, 0.7, 0.15], border=False)

    # Center column: contains main visualization
    with col2:
        with st.container(border=True, ):
            st.subheader("Campaign Contributions by Candidate and State")

            # User chooses how to sort bars: alphabetically by state or by total contributions
            sort_by = st.radio("Sort bars by:", ["Total Contributions", "State"], horizontal=True)

            # Aggregate donations first by ZIP then by candidate and state
            grouped = cf_df.groupby(["contbr_st", "contbr_zip", "cand_nm"])["contb_receipt_amt"].sum().reset_index()
            state_cand_sums = grouped.groupby(["contbr_st", "cand_nm"])["contb_receipt_amt"].sum().reset_index()
            
            # Apply selected sort method
            if sort_by == "Total Contributions":
                state_cand_sums = state_cand_sums.sort_values(by="contb_receipt_amt", ascending=False)
            else:
                state_cand_sums = state_cand_sums.sort_values(by="contbr_st")

            # Create interactive bar plot using Plotly Express
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

            # Adjust layout and formatting
            fig.update_layout(
                            xaxis_title="State",
                yaxis_title="Total Contributions ($ Millions)",
                yaxis_tickformat=".2s",
                legend_title="Candidate",
                bargap=0.15,
                height=700
            )

            # Display plot in container
            st.plotly_chart(fig, use_container_width=True)

            # Display underlying data used in bar chart
            with st.expander("Show data used in bar chart"):
                df_to_display = state_cand_sums.copy()
                df_to_display["contb_receipt_amt"] = df_to_display["contb_receipt_amt"].round(2) # round data to be cleaner
                df_to_display = df_to_display.sort_values(["contbr_st", "cand_nm"]) # sort data
                st.dataframe(df_to_display)

                # Download button for bar chart data
                csv = df_to_display.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download bar chart data as CSV",
                    data=csv,
                    file_name="bar_chart_data.csv",
                    mime="text/csv"
                )

    
    # Right column: Explanation of chart methodology
    with col3:
        with st.container():
            st.markdown("""
                        **Methodology:**

                        This chart shows total monthly itemized contributions, grouped by candidate.
                        The data is sourced from the Federal Election Commission (FEC) 2024 campaign donation filings.

                        - Only positive (incoming) contributions are shown.
                        - Candidate names are taken directly from the filing metadata.
                        - Donations are grouped by the `contb_receipt_dt` field (contribution receipt date).
                        """)

# --- Tab 2: Time Series of Donationas by Candidate ---
with tab2:
    # Layout for line chart view
    col1, col2, col3 = st.columns([0.15, 0.7, 0.15], border=True)

    # Left Column holds candidate checkboxes
    with col1:
        with st.container(height=700):
            # Sidebar: Candidate selector checkboxes
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


    # Main panel: Time series line plot
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
        ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f'{int(x / 1e6)}')) # Set y axis to be in millions
        plt.xticks(rotation=45, fontsize=8)
        plt.yticks(fontsize=8)
        plt.tight_layout()
        st.pyplot(fig)

        # Display underlying data used in line chart
        with st.expander("Show data used in line chart"):
            df_to_display = filtered_data.copy()
            df_to_display["contb_receipt_amt"] = df_to_display["contb_receipt_amt"].round(2) # round data to be cleaner
            df_to_display = df_to_display.sort_values(["month", "cand_nm"]) # sort data
            st.dataframe(df_to_display)

            # Download button for line chart data
            csv = df_to_display.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download line chart data as CSV",
                data=csv,
                file_name="line_chart_data.csv",
                mime="text/csv"
            )
    
    # Right Column holds explanation of methodology
    with col3:
        with st.container():
            st.markdown("""
                        **Methodology:**

                        Contributions are summed by candidate within each state using cleaned FEC donation data.

                        - Only positive (incoming) donations are included.
                        - The data is filtered to the 50 U.S. states (DC and territories excluded).
                        - Hovering over each bar shows exact donation totals per candidate per state.
                        - Only Kamala Harris and Donald Trump are shown to focus on the leading candidates.
                        - Additional candidates may be selected, but the chart with take a few seconds to load.
                        """)

# --- Tab 3: Choropleth County-Level Donation Mapping ---
with st.spinner("Loading data..."):
    # Load donation and crosswalk data, format ZIP codes properly (multiple donations per zipcode counts as XXXXX0001, XXXXX0002, etc)
    cf_df = load_data()
    cf_df["contbr_zip"] = cf_df["contbr_zip"].astype(str).str[:5].str.zfill(5)
    crosswalk_df = load_zip_to_county_crosswalk()
    crosswalk_df["zip"] = crosswalk_df["zip"].astype(str).str[:5].str.zfill(5)

    with tab3:
        st.subheader("County-Level Campaign Donations")

        # Toggle between total donations or Kamala vs Trump share
        mode = st.radio("View Mode", ["Total", "Kamala vs Trump"], horizontal=True, index=1)

        # Merge ZIP-level donations with HUD ZIP-county crosswalk
        merged_df = cf_df.copy()
        merged_df["contbr_zip"] = merged_df["contbr_zip"].astype(str)
        merged_df = merged_df.merge(crosswalk_df[["zip", "geoid"]], left_on="contbr_zip", right_on="zip", how="left")
        merged_df = merged_df.rename(columns={"geoid": "GEOID"})

        # Load county shapefiles for plotting
        counties = gpd.read_file("county_shapefile_data/counties_simplified.geojson")
        counties = counties[["GEOID", "NAMELSAD", "geometry"]].copy()
        counties["GEOID"] = counties["GEOID"].astype(str)

        # Add state name based on first two digits of GEOID (prevent ambiguity about county names)
        state_fips_map = {
            "01": "Alabama", "02": "Alaska", "04": "Arizona", "05": "Arkansas", "06": "California", "08": "Colorado",
            "09": "Connecticut", "10": "Delaware", "11": "District of Columbia", "12": "Florida", "13": "Georgia",
            "15": "Hawaii", "16": "Idaho", "17": "Illinois", "18": "Indiana", "19": "Iowa", "20": "Kansas",
            "21": "Kentucky", "22": "Louisiana", "23": "Maine", "24": "Maryland", "25": "Massachusetts", "26": "Michigan",
            "27": "Minnesota", "28": "Mississippi", "29": "Missouri", "30": "Montana", "31": "Nebraska", "32": "Nevada",
            "33": "New Hampshire", "34": "New Jersey", "35": "New Mexico", "36": "New York", "37": "North Carolina",
            "38": "North Dakota", "39": "Ohio", "40": "Oklahoma", "41": "Oregon", "42": "Pennsylvania", "44": "Rhode Island",
            "45": "South Carolina", "46": "South Dakota", "47": "Tennessee", "48": "Texas", "49": "Utah", "50": "Vermont",
            "51": "Virginia", "53": "Washington", "54": "West Virginia", "55": "Wisconsin", "56": "Wyoming"
        }

        counties["STATE"] = counties["GEOID"].str[:2].map(state_fips_map)

        if mode == "Total":
            # Total donations by county
            county_donations = merged_df.groupby("GEOID")["contb_receipt_amt"].sum().reset_index()
            choropleth_df = counties.merge(county_donations, on="GEOID", how="left").fillna(0)

            # Log-transform donation amounts for color scale
            choropleth_df["log_donations"] = np.where(
                choropleth_df["contb_receipt_amt"] > 0,
                np.log10(choropleth_df["contb_receipt_amt"] + 1),
                0
            )
            color_col = "log_donations"
            color_scale = "Viridis"
            color_title = "Donations ($)"
        else:
            # Kamala vs Trump donation share per county, aggregate and sum over zipcode per candidate
            pivot = merged_df[merged_df["cand_nm"].isin(["Trump, Donald J.", "Harris, Kamala"])]
            pivot = pivot.groupby(["GEOID", "cand_nm"])["contb_receipt_amt"].sum().unstack(fill_value=0).reset_index()
            pivot["kamala_ratio"] = pivot["Harris, Kamala"] / (pivot["Harris, Kamala"] + pivot["Trump, Donald J."])
            pivot["kamala_ratio"] = pivot["kamala_ratio"].fillna(0.5)  # Neutral purple for 0/0 cases
            choropleth_df = counties.merge(pivot, on="GEOID", how="left")
            color_col = "kamala_ratio"
            color_scale = [(0.0, "red"), (0.5, "purple"), (1.0, "blue")]  # red = Trump > Kamala, blue = Kamala > Trump
            color_title = "Kamala Share of Donations" # Blue is kamala, red is trump.

        # Create choropleth figure
        fig = px.choropleth_map(
            choropleth_df,
            geojson=json.loads(choropleth_df.to_json()),
            locations="GEOID",
            featureidkey="properties.GEOID",
            color=color_col,
            hover_data=["NAMELSAD", "contb_receipt_amt"] if mode == "Total" else ["NAMELSAD", "Harris, Kamala", "Trump, Donald J."],
            color_continuous_scale=color_scale,
            center={"lat": 37.8, "lon": -96},
            zoom=3,
            height=600
        )

        # Adjust layout based on mode
        fig.update_layout(
            margin={"r": 0, "t": 0, "l": 0, "b": 0},
            coloraxis_colorbar_title=color_title,
            coloraxis_colorbar_tickformat=".2f"
        )
        
        if mode == "Total":
            fig.update_traces(marker_line_width=1.0, marker_line_color="black")
        else:
            fig.update_traces(marker_line_width=0.35, marker_line_color="gray")

        st.plotly_chart(fig, use_container_width=True)

        # Spacer to prevent chart and data overlap
        with st.container():
            st.write("")
            st.write("")
            st.markdown("---")

        # Display underlying data used in choropleth
        with st.expander("Show data used in choropleth"):
            df_to_display = choropleth_df.copy()

            # Reorder and clean up based on view mode
            if mode == "Total":
                df_to_display["contb_receipt_amt"] = df_to_display["contb_receipt_amt"].round(2)
                df_to_display = df_to_display[["NAMELSAD", "STATE", "GEOID", "contb_receipt_amt", "log_donations"] + [col for col in df_to_display.columns if col not in ["NAMELSAD", "STATE", "GEOID", "contb_receipt_amt", "log_donations"]]]
                df_to_display = df_to_display.sort_values(["NAMELSAD"])
            else:
                df_to_display["Harris, Kamala"] = df_to_display["Harris, Kamala"].round(2)
                df_to_display["Trump, Donald J."] = df_to_display["Trump, Donald J."].round(2)
                df_to_display["kamala_ratio"] = df_to_display["kamala_ratio"].round(3)
                df_to_display = df_to_display[["NAMELSAD", "STATE", "GEOID", "Harris, Kamala", "Trump, Donald J.", "kamala_ratio"] + [col for col in df_to_display.columns if col not in ["NAMELSAD", "STATE", "GEOID", "Harris, Kamala", "Trump, Donald J.", "kamala_ratio"]]]
                df_to_display = df_to_display.sort_values(["NAMELSAD"])

            st.dataframe(df_to_display)

            # Download button for choropleth data
            csv = df_to_display.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download choropleth data as CSV",
                data=csv,
                file_name="choropleth_data.csv",
                mime="text/csv"
            )

            # Download button for choropleth GeoJSON
            geojson = choropleth_df.to_json()
            st.download_button(
                label="Download choropleth data as GeoJSON",
                data=geojson,
                file_name="choropleth_data.geojson",
                mime="application/geo+json"
            )


        # Methodology container below choropleth
        with st.container():
            st.write("")
            st.write("")
            st.markdown("---")
            st.markdown("""
                        **Methodology:**
                        
                        ZIP codes from FEC donation records were mapped to counties using the HUD USPS ZIP-County Crosswalk. 
                        For ZIPs linked to multiple counties, we kept the county with the highest USPS residential delivery ratio.
                        
                        - **Total view** uses log-transformed donation sums per county.
                        - **Kamala vs Trump view** shows the proportion of donations going to each candidate. 
                        - Blue = Kamala-heavy counties
                        - Red = Trump-heavy counties
                        - Purple = roughly even
                        - White = zero donations
                        
                        Negative contributions (refunds/outflows) were removed. All values reflect **total itemized contributions**.

                        For more information on using the HUD USPS ZIP-County Crosswalk API, view the readme on GitHub (link in source code).
                        """)

# --- Tab 4: Source Code Viewer ---
with tab4:
    with open("choropleth_dashboard.py", "r") as f:
        source = f.read()
    st.subheader("Project Source Code")
    st.code(source, language="python")

# --- Tab 5: Project Report ---
with tab5:
    st.subheader("Project Report Group 25")
    st.write("")
    st.markdown("---")
    st.markdown("""
                **Report Here:**
                
                Body\
  
                Figures\
                """)
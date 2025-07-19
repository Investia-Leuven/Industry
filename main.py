import streamlit as st
from logic import get_available_sectors, get_industries_for_sector, combine_industry_dataframes
import pandas as pd

# --- Fixed Header ---
st.markdown("""
    <style>
    .header {
        position: sticky;
        top: 0;
        left: 0;
        width: 100%;
        background-color: white;
        padding: 10px 0;
        z-index: 1000;
        border-bottom: 1px solid #ddd;
        text-align: center;
    }
    .header span {
        font-size: 20px;
        font-weight: bold;
        color: #333;
        vertical-align: middle;
    }
    .block-container {
        padding-top: 45px;
    }
    </style>
    <div class="header">
        <span>Investia - Sector screening (bèta)</span>
    </div>
""", unsafe_allow_html=True)

st.set_page_config(page_title="Investia Sector", layout="wide")
#st.markdown("## Industry screening - Bèta version")

# Fetch sector list as name-key dictionary
sectors_dict = get_available_sectors()
sector_names = list(sectors_dict.keys())

# Sector selection
selected_sector_name = st.radio(
    "### Select a sector:",
    options=sector_names,
    horizontal=True,
    key="sector_radio",
    index=None
)

if selected_sector_name:
    selected_sector_key = sectors_dict[selected_sector_name]

    # Fetch industries for the selected sector
    industries_dict = get_industries_for_sector(selected_sector_key)
    industry_names = list(industries_dict.keys())

    if industry_names:
        industry_names_with_all = ["All"] + industry_names
        selected_industry_names = st.multiselect("Select one or more industries:", industry_names_with_all)

        # Expand to all if 'All' is selected
        if "All" in selected_industry_names:
            selected_industry_names = industry_names
        selected_industry_keys = [industries_dict[name] for name in selected_industry_names]

        # Display selected industries
        if selected_industry_names:
            st.success(f"Selected industries: {', '.join(selected_industry_names)}")

            # Choice of data type for companies
            data_choices = {
                'Top Companies': 'top_companies',
                'Top Growth': 'top_growth_companies',
                'Top Performers': 'top_performing_companies'
            }

            selected_data_label = st.radio(
                "### Select data type to display:",
                options=list(data_choices.keys()),
                horizontal=True,
                key="data_choice_radio",
                index=None
            )

            if selected_data_label:
                selected_data_method = data_choices[selected_data_label]

                # Get the final enriched dataframe
                final_df = combine_industry_dataframes(selected_industry_names, selected_industry_keys, selected_data_method)

                if not final_df.empty:
                    # Round all numeric columns to 2 decimals
                    final_df = final_df.round(2)

                    # --- Filtering Section ---
                    st.markdown("#### Filter Data")

                    with st.expander("Apply Filters", expanded=False):
                        if "Market Cap (M USD)" in final_df.columns:
                            cap_series = pd.to_numeric(final_df["Market Cap (M USD)"], errors="coerce").dropna()
                            if not cap_series.empty:
                                min_cap = float(cap_series.min())
                                max_cap = float(cap_series.max())
                                cap_col, _ = st.columns([2, 5])
                                with cap_col:
                                    selected_cap_range = st.slider(
                                        "Market Cap (in million $):",
                                        min_value=min_cap,
                                        max_value=max_cap,
                                        value=(min_cap, max_cap)
                                    )
                                final_df = final_df[
                                    (pd.to_numeric(final_df["Market Cap (M USD)"], errors="coerce") >= selected_cap_range[0]) &
                                    (pd.to_numeric(final_df["Market Cap (M USD)"], errors="coerce") <= selected_cap_range[1])
                                ]
                            else:
                                st.info("Market Cap column found but contains no numeric values.")
                        else:
                            st.info("Market Cap (M USD) column not found in data.")

                        # Checkbox for top 20 by Market Cap
                        show_top_20 = st.checkbox("Show only top 20 by Market Cap")
                        if show_top_20 and "Market Cap (M USD)" in final_df.columns:
                            final_df = final_df.sort_values(by="Market Cap (M USD)", ascending=False).head(20)

                        # Checkboxes for each unique rating
                        if "Rating" in final_df.columns:
                            st.markdown("**Filter by Rating:**")
                            ratings = sorted(final_df["Rating"].dropna().unique())
                            rating_cols = st.columns(len(ratings))
                            selected_ratings = []
                            for col, rating in zip(rating_cols, ratings):
                                if col.checkbox(str(rating), value=True):
                                    selected_ratings.append(rating)
                            if selected_ratings:
                                final_df = final_df[final_df["Rating"].isin(selected_ratings)]

                    st.subheader("Company Data")

                    # Columns to apply background gradient
                    gradient_columns = ["Gross Margin (%)", "EBIT Margin (%)", "EBITDA Margin (%)"]
                    inverse_gradient_columns = ["P/E", "EV/EBITDA", "EV/Sales", "P/FCF"]

                    # Function to create a gmap with clipping and normalisation, ensuring numeric input
                    def normalise_for_gradient(series, reverse=False):
                        numeric_series = pd.to_numeric(series, errors='coerce').dropna()
                        lower = numeric_series.quantile(0.05)
                        upper = numeric_series.quantile(0.95)
                        clipped = numeric_series.clip(lower, upper)
                        normalised = (clipped - lower) / (upper - lower)
                        if reverse:
                            normalised = 1 - normalised
                        return normalised.reindex(series.index, fill_value=None)

                    # Create a Styler object
                    styler = final_df.style.set_na_rep("").highlight_null(null_color="#d3d3d3").format(precision=2)

                    # Apply background gradients using continuous normalised gmap
                    for col in gradient_columns:
                        if col in final_df.columns:
                            gmap = normalise_for_gradient(final_df[col])
                            styler = styler.background_gradient(cmap="RdYlGn", subset=[col], gmap=gmap)
                    for col in inverse_gradient_columns:
                        if col in final_df.columns:
                            gmap = normalise_for_gradient(final_df[col], reverse=True)
                            styler = styler.background_gradient(cmap="RdYlGn", subset=[col], gmap=gmap)

                    st.dataframe(styler)

                    # --- Export options for styled and plain Excel files ---
                    import io
                    col1, col2, _ = st.columns([2, 2, 14])

                    # Export styled Excel
                    styled_buffer = io.BytesIO()
                    with pd.ExcelWriter(styled_buffer, engine='openpyxl') as writer:
                        styler.to_excel(writer, sheet_name="Companies")
                    styled_buffer.seek(0)
                    with col1:
                        st.download_button(
                            label="Formatted Excel",
                            data=styled_buffer,
                            file_name="industry_companies_styled.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )

                    # Export plain Excel
                    plain_buffer = io.BytesIO()
                    final_df.to_excel(plain_buffer, index=False, engine='openpyxl')
                    plain_buffer.seek(0)
                    with col2:
                        st.download_button(
                            label="Plain Excel",
                            data=plain_buffer,
                            file_name="industry_companies_plain.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )

                else:
                    st.warning("No data available for the selected industries and data method.")
    else:
        st.warning("No industries found for this sector. Might be due to an error in fetching data.")

# --- Fixed Footer ---
st.markdown("""
    <style>
    .footer {
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        text-align: center;
        background-color: white;
        padding: 10px;
        font-size: 0.85em;
        color: grey;
        z-index: 100;
        border-top: 1px solid #ddd;
    }
    </style>
    <div class="footer">
        <i>This is a bèta version. All rights reserved by Investia. Suggestions or errors can be reported to Vince Coppens.</i>
    </div>
""", unsafe_allow_html=True)
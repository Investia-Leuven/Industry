import streamlit as st
import pandas as pd
from logic import get_available_sectors, get_industries_for_sector, combine_industry_dataframes, apply_final_sorting_and_formatting, fetch_additional_company_data, apply_filters, normalise_for_gradient, create_styler, generate_styled_excel, generate_plain_excel, render_download_buttons

import io

def main():
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
    st.markdown("")

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

    if not selected_sector_name:
        st.stop()

    selected_sector_key = sectors_dict[selected_sector_name]

    # Fetch industries for the selected sector
    industries_dict = get_industries_for_sector(selected_sector_key)
    industry_names = list(industries_dict.keys())

    if not industry_names:
        st.warning("No industries found for this sector. Might be due to an error in fetching data.")
        st.stop()

    industry_names_with_all = ["All"] + industry_names
    selected_industry_names = st.multiselect("Select one or more industries:", industry_names_with_all)

    # Expand to all if 'All' is selected
    if "All" in selected_industry_names:
        selected_industry_names = industry_names
    selected_industry_keys = [industries_dict[name] for name in selected_industry_names]

    # Display selected industries
    if not selected_industry_names:
        st.stop()

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

    if not selected_data_label:
        st.stop()

    selected_data_method = data_choices[selected_data_label]

    # Get the final enriched dataframe
    final_df = combine_industry_dataframes(selected_industry_names, selected_industry_keys, selected_data_method)

    if final_df.empty:
        st.warning("No data available for the selected industries and data method.")
        st.stop()

    with st.expander("Apply Filters", expanded=False):
        cap_range = None
        top_n = None
        selected_ratings = None

        if "Market Cap (M USD)" in final_df.columns:
            cap_series = pd.to_numeric(final_df["Market Cap (M USD)"], errors="coerce").dropna()
            if not cap_series.empty:
                min_cap = int(cap_series.min()) - 1
                max_cap = int(cap_series.max()) + 1
                cap_col, _ = st.columns([2, 5])
                with cap_col:
                    cap_range = st.slider(
                        "Market Cap (in million $):",
                        min_value=min_cap,
                        max_value=max_cap,
                        value=(min_cap, max_cap)
                    )
            else:
                st.info("Market Cap column found but contains no numeric values.")
        else:
            st.info("Market Cap (M USD) column not found in data.")

        show_top_20 = st.checkbox("Show only top 20 by Market Cap")
        if show_top_20:
            top_n = 20

        if "Rating" in final_df.columns:
            st.markdown("**Filter by Rating:**")
            ratings = sorted(final_df["Rating"].dropna().unique())
            rating_cols = st.columns(len(ratings))
            selected_ratings = [
                rating for col, rating in zip(rating_cols, ratings)
                if col.checkbox(str(rating), value=True)
            ]

        final_df = apply_filters(final_df, cap_range=cap_range, top_n=top_n, selected_ratings=selected_ratings)

    final_df = apply_final_sorting_and_formatting(final_df)
    
    st.subheader("Company Data")

    # Columns to apply background gradient
    gradient_columns = ["Gross Margin (%)", "EBIT Margin (%)", "EBITDA Margin (%)"]
    inverse_gradient_columns = ["P/E", "EV/EBITDA", "EV/Sales", "P/FCF"]

    # Use create_styler from logic.py
    styler = create_styler(final_df, gradient_columns, inverse_gradient_columns)

    # --- Filtering Section ---
    st.markdown("#### Filter Data")

    st.dataframe(styler)

    # --- Export options for styled and plain Excel files ---
    styled_buffer = generate_styled_excel(final_df, gradient_columns, inverse_gradient_columns, sheet_name="Companies")
    plain_buffer = generate_plain_excel(final_df, sheet_name="Companies")

    render_download_buttons(
        styled_buffer, "industry_companies_styled.xlsx",
        plain_buffer, "industry_companies_plain.xlsx"
    )

    # --- Optional Upload of Custom Ticker List ---
    uploaded_file = st.file_uploader("Optional: Upload custom ticker list (Excel with 1 ticker per row)", type=["xlsx"])

    if uploaded_file:
        try:
            # Read the file
            custom_df = pd.read_excel(uploaded_file, header=None)

            tickers = custom_df.iloc[:, 0].dropna().astype(str).unique().tolist()

            if tickers:
                st.success(f"{len(tickers)} custom tickers uploaded.")

                # Fetch additional data using your logic function
                uploaded_data_df = fetch_additional_company_data(pd.DataFrame({"symbol": tickers}))

                # Combine with final_df if present
                if not final_df.empty:
                    combined_df = pd.concat([final_df, uploaded_data_df], ignore_index=True)
                else:
                    combined_df = uploaded_data_df

                combined_df = apply_final_sorting_and_formatting(combined_df)
                # Drop specified columns before styling/export
                combined_df.drop(columns=["Market Weight (%)", "Industry", "Rating"], inplace=True, errors="ignore")
                styler_combined = create_styler(combined_df, gradient_columns, inverse_gradient_columns)

                st.subheader("Combined Data")
                st.dataframe(styler_combined)

                # --- Export options for combined dataframe ---
                styled_combined_buffer = generate_styled_excel(combined_df, gradient_columns, inverse_gradient_columns, sheet_name="Combined")
                plain_combined_buffer = generate_plain_excel(combined_df, sheet_name="Combined")

                render_download_buttons(
                    styled_combined_buffer, "combined_companies_styled.xlsx",
                    plain_combined_buffer, "combined_companies_plain.xlsx"
                )
        except Exception as e:
            st.error(f"Error processing uploaded file: {e}")

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

if __name__ == "__main__":
    main()
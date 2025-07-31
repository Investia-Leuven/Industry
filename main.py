import streamlit as st
import pandas as pd
from logic import (
    get_available_sectors,
    get_industries_for_sector,
    combine_industry_dataframes,
    apply_final_sorting_and_formatting,
    fetch_additional_company_data,
    apply_filters,
    normalise_for_gradient,
    create_styler,
    render_download_buttons,
    process_uploaded_tickers,
    get_gradient_columns
)

st.set_page_config(page_title="Investia Sector", layout="wide")

def display_and_export_df(df, title, styled_filename, plain_filename, sheet_name):
    """Sort, style, display, and render download buttons for a DataFrame."""
    df = apply_final_sorting_and_formatting(df)
    gradient_columns, inverse_gradient_columns = get_gradient_columns()
    styler = create_styler(df, gradient_columns, inverse_gradient_columns)
    st.subheader(title)
    st.dataframe(styler)
    render_download_buttons(
        df,
        styled_filename=styled_filename,
        plain_filename=plain_filename,
        gradient_columns=gradient_columns,
        inverse_gradient_columns=inverse_gradient_columns,
        sheet_name=sheet_name
    )

def main():
    def display_header():
        """Display the app header with logo and title."""
        st.markdown(
            """
            <style>
            .header-container {
                display: flex;
                align-items: center;
                position: sticky;
                top: 0;
                background-color: white;
                padding: 10px 0;
                border-bottom: 1px solid #ddd;
                z-index: 1000;
            }
            .header-title {
                font-size: 20px;
                font-weight: bold;
                color: #333;
                text-align: center;
                flex-grow: 1;
                margin-right: 60px;
            }
            .block-container {
                padding-top: 60px;
            }
            </style>
            """,
            unsafe_allow_html=True
        )

        col1, col2, col3 = st.columns([1, 6, 1])
        with col1:
            st.image("logoinvestia.png", width=80)
        with col2:
            st.markdown(
                "<div class='header-title'>Investia - Sector screening (bèta)</div>",
                unsafe_allow_html=True
            )
        with col3:
            st.empty()
    def display_footer():
        """Display sticky footer."""
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
                <i>This is a bèta version. All rights reserved by Investia. 
                Suggestions or errors can be reported to Vince Coppens.</i>
            </div>
        """, unsafe_allow_html=True)

    display_header()
    display_footer()

    st.set_page_config(page_title="Investia Sector", layout="wide")
    #st.markdown("## Industry screening - Bèta version")
    st.markdown("")

    # Fetch sector list as name-key dictionary
    sectors_dict = get_available_sectors()
    sector_names = list(sectors_dict.keys())

    # Sector selection
    selected_sector_name = st.radio(
        "### Select a sector:",
        options=["None"] + sector_names,
        horizontal=True,
        key="sector_radio",
        index=None
    )

    if not selected_sector_name:
        st.stop()

    # Case 1: No sector selected
    if selected_sector_name == "None":
        st.info("No sector selected. You can upload an Excel file to display custom tickers.")

        # Only allow optional upload and skip all filter/dataframe logic
        uploaded_file = st.file_uploader("Optional: Upload custom ticker list (Excel with 1 ticker per row)", type=["xlsx"])

        if uploaded_file:
            combined_df, error_msg = process_uploaded_tickers(uploaded_file, pd.DataFrame())
            if error_msg:
                st.error(error_msg)
                st.stop()

            st.success(f"{len(combined_df)} tickers successfully processed from upload.")

            combined_df.drop(columns=["Market Weight (%)", "Industry", "Rating"], inplace=True, errors="ignore")
            display_and_export_df(
                combined_df,
                title="Uploaded Data",
                styled_filename="uploaded_companies_styled.xlsx",
                plain_filename="uploaded_companies_plain.xlsx",
                sheet_name="Uploaded"
            )

        # Skip the rest of the logic for filters and company data
        return

    # Case 2: A sector is selected -> full logic
    final_df = pd.DataFrame()  # initialise

    selected_sector_key = sectors_dict[selected_sector_name]
    industries_dict = get_industries_for_sector(selected_sector_key)
    industry_names = list(industries_dict.keys())

    if not industry_names:
        st.warning("No industries found for this sector. Might be due to an error in fetching data.")
        st.stop()

    industry_names_with_all = ["All"] + industry_names
    selected_industry_names = st.multiselect("Select one or more industries:", industry_names_with_all)

    if "All" in selected_industry_names:
        selected_industry_names = industry_names
    selected_industry_keys = [industries_dict[name] for name in selected_industry_names]

    if not selected_industry_names:
        st.stop()

    st.success(f"Selected industries: {', '.join(selected_industry_names)}")

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

    display_and_export_df(
        final_df,
        title="Company Data",
        styled_filename="industry_companies_styled.xlsx",
        plain_filename="industry_companies_plain.xlsx",
        sheet_name="Companies"
    )

    # --- Optional Upload of Custom Ticker List ---
    uploaded_file = st.file_uploader("Optional: Upload custom ticker list (Excel with 1 ticker per row)", type=["xlsx"])

    if uploaded_file:
        # Use process_uploaded_tickers to handle upload and validation
        combined_df, error_msg = process_uploaded_tickers(uploaded_file, final_df)
        if error_msg:
            st.error(error_msg)
            st.stop()
        uploaded_count = len(combined_df) - len(final_df)
        st.success(f"{uploaded_count} tickers successfully processed from upload.")

        combined_df.drop(columns=["Market Weight (%)", "Industry", "Rating"], inplace=True, errors="ignore")
        display_and_export_df(
            combined_df,
            title="Combined Data",
            styled_filename="combined_companies_styled.xlsx",
            plain_filename="combined_companies_plain.xlsx",
            sheet_name="Combined"
        )



if __name__ == "__main__":
    main()

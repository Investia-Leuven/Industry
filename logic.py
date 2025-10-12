"""Core logic for the Investia Sector app.

Provides functions to fetch, enrich, filter, and style financial data related to sectors, industries, and companies.
"""

# Standard library imports
from io import BytesIO

# Third-party imports
import pandas as pd
import yfinance as yf
import streamlit as st

# Global warning suppression for cleaner terminal
import warnings
import logging
warnings.filterwarnings("ignore")
logging.getLogger("yfinance").setLevel(logging.ERROR)
logging.getLogger("streamlit").setLevel(logging.ERROR)

# Local imports

from functools import lru_cache


# Helper function to fetch live exchange rates for a set of currencies
@st.cache_data(show_spinner=False)
def get_live_exchange_rates(currencies):
    """
    Fetches live exchange rates to USD for the given set of currency codes using Yahoo Finance.
    Returns a dictionary mapping each currency to its USD conversion rate.
    Falls back to 1.0 if fetching fails.
    """
    exchange_rates = {"USD": 1.0}
    non_usd_currencies = [cur for cur in currencies if cur != "USD"]

    if not non_usd_currencies:
        return exchange_rates

    try:
        # Fetch all rates in a single batch, e.g. "EURUSD=X GBPUSD=X"
        fx_tickers_str = " ".join(f"{cur}USD=X" for cur in non_usd_currencies)
        fx_tickers = yf.Tickers(fx_tickers_str).tickers
        print("[DEBUG] Fetched tickers:", fx_tickers.keys())

        for cur in non_usd_currencies:
            ticker_key = f"{cur}USD=X"
            try:
                hist = fx_tickers[ticker_key].history(period="1d")
                if not hist.empty:
                    exchange_rates[cur] = float(hist["Close"].iloc[-1])
                else:
                    exchange_rates[cur] = 1.0
            except Exception:
                exchange_rates[cur] = 1.0

    except Exception:
        # In case of total failure, use all as 1.0
        for cur in non_usd_currencies:
            exchange_rates[cur] = 1.0

    return exchange_rates


@st.cache_data(show_spinner=False)
def get_available_sectors():
    """
    Returns a dictionary mapping sector display names to their keys used in yfinance.
    Provides the list of available sectors for selection.
    """
    return {
        "Basic Materials": "basic-materials",
        "Communication Services": "communication-services",
        "Consumer Cyclical": "consumer-cyclical",
        "Consumer Defensive": "consumer-defensive",
        "Energy": "energy",
        "Financial Services": "financial-services",
        "Healthcare": "healthcare",
        "Industrials": "industrials",
        "Real Estate": "real-estate",
        "Technology": "technology",
        "Utilities": "utilities"
    }


@st.cache_data(show_spinner=False)
def get_industries_for_sector(sector_key):
    """
    Given a sector key, returns a dictionary mapping industry names to their keys.
    Used to retrieve industries within a selected sector.
    """
    try:
        sector = yf.Sector(sector_key)
        df = sector.industries  # This returns a DataFrame
        return dict(zip(df["name"], df.index))
    except Exception:
        return {}


@st.cache_data(show_spinner=False)
def get_companies_for_industry(industry_key, data_method):
    """
    Given an industry key and data method name, returns a DataFrame of companies.
    Used to fetch company data for a selected industry.
    """
    try:
        industry = yf.Industry(industry_key)
        df = getattr(industry, data_method)
        return df
    except Exception:
        return None


"""
Combines data from multiple industries into one DataFrame and enriches it with additional financial metrics.
"""
def combine_industry_dataframes(industry_names, industry_keys, data_method):
    """
    Returns a single enriched DataFrame for selected industries using the specified data method.
    """
    combined_list = []
    for industry_name, industry_key in zip(industry_names, industry_keys):
        # Retrieve company data for the industry
        df = get_companies_for_industry(industry_key, data_method)
        if df is not None and not df.empty:
            # Ensure 'symbol' column exists, resetting index if necessary
            if 'symbol' not in df.columns and df.index.name == 'symbol':
                df = df.reset_index()
            df = df.copy()
            # Tag the DataFrame with the industry name
            df["Industry"] = industry_name
            combined_list.append(df)
    if not combined_list:
        return pd.DataFrame()
    # Concatenate all industry DataFrames into one
    full_df = pd.concat(combined_list, ignore_index=True)
    # Enrich combined DataFrame with additional financial data
    enriched_df = fetch_additional_company_data(full_df)
    return enriched_df

"""
Fetches extended financial data from Yahoo Finance for a list of company tickers.
Converts currencies to USD, scales to millions, and calculates financial ratios.
"""
@st.cache_data(show_spinner=False)
def fetch_additional_company_data(df_with_symbols):
    """
    Extends the given DataFrame of companies with additional financial metrics from yfinance.
    Enriches data by converting currencies to USD using exchange rates, scaling revenue and market cap to millions,
    and calculating financial ratios such as P/FCF.
    Returns a DataFrame with columns in the specified order.
    """

    # Prepare tickers and fetch info for all
    tickers = df_with_symbols["symbol"].tolist()
    yf_tickers = yf.Tickers(" ".join(tickers)).tickers
    try:
        info_dict = {symbol: yf_tickers[symbol].info for symbol in tickers if symbol in yf_tickers}
    except Exception as e:
        print(f"[WARNING] Some tickers failed to fetch: {e}")
        info_dict = {}

    # Detect all currencies used by the fetched companies
    used_currencies = {
        info.get("currency", "USD")
        for info in info_dict.values()
        if isinstance(info, dict)
    }
    # Get live exchange rates dynamically
    exchange_rates = get_live_exchange_rates(used_currencies)

    rows = []
    # Iterate over each company row to enrich data
    for symbol, company_name, industry, market_weight, rating in zip(
            df_with_symbols["symbol"],
            df_with_symbols.get("name", pd.Series([None]*len(df_with_symbols))),
            df_with_symbols.get("Industry", pd.Series([""]*len(df_with_symbols))),
            df_with_symbols.get("market weight", pd.Series([None]*len(df_with_symbols))),
            df_with_symbols.get("rating", pd.Series([""]*len(df_with_symbols)))):
        
        info = info_dict.get(symbol, {})
        # Debug log to inspect currency returned by Yahoo Finance
        print(f"[DEBUG] {symbol}: currency={info.get('currency')}")
        # Use yfinance shortName if company_name missing
        if not company_name:
            company_name = info.get("shortName", None)

        currency = info.get("currency", "USD")
        rate = exchange_rates.get(currency, 1.0)

        # Convert market weight to percentage if present
        market_weight = market_weight*100 if market_weight is not None else None

        # Extract margin metrics, fallback to operatingMargins if ebitMargins missing
        ebit_margin = info.get("ebitMargins") or info.get("operatingMargins")
        gross_margin = info.get("grossMargins")
        ebitda_margin = info.get("ebitdaMargins")

        # Convert margins to percentages
        gross_margin = gross_margin*100 if gross_margin is not None else None
        ebit_margin = ebit_margin*100 if ebit_margin is not None else None
        ebitda_margin = ebitda_margin*100 if ebitda_margin is not None else None

        # Extract financial metrics
        revenue = info.get("totalRevenue")
        market_cap = info.get("marketCap")
        free_cashflow = info.get("freeCashflow")
        enterprise_to_ebitda = info.get("enterpriseToEbitda")
        enterprise_to_revenue = info.get("enterpriseToRevenue")

        # Convert revenue, market cap, free cashflow to millions USD
        revenue = (revenue*rate/1_000_000) if revenue is not None else None
        market_cap = (market_cap*rate/1_000_000) if market_cap is not None else None
        free_cashflow = (free_cashflow*rate/1_000_000) if free_cashflow is not None else None
        # Calculate Price to Free Cash Flow ratio
        p_fcf_ratio = (market_cap/free_cashflow) if market_cap and free_cashflow else None

        # Build row dictionary with enriched data
        rows.append({
            "Name": company_name,
            "Ticker": symbol,
            "Revenue (M USD)": revenue,
            "Market Cap (M USD)": market_cap,
            "Gross Margin (%)": gross_margin,
            "EBIT Margin (%)": ebit_margin,
            "EBITDA Margin (%)": ebitda_margin,
            "P/E": info.get("trailingPE"),
            "EV/EBITDA": enterprise_to_ebitda,
            "EV/Sales": enterprise_to_revenue,
            "P/FCF": p_fcf_ratio,
            "Market Weight (%)": market_weight,
            "Industry": industry,
            "Rating": rating
        })

    columns = [
        "Name", "Ticker", "Revenue (M USD)", "Market Cap (M USD)", "Gross Margin (%)",
        "EBIT Margin (%)", "EBITDA Margin (%)", "P/E", "EV/EBITDA", "EV/Sales",
        "P/FCF", "Market Weight (%)", "Industry", "Rating"
    ]
    df = pd.DataFrame(rows, columns=columns)
    return df.round(2)

def apply_final_sorting_and_formatting(df):
    """
    Sorts the DataFrame by Market Cap in descending order if present,
    resets the index starting at 1, and rounds numeric values to 2 decimals.
    """
    if "Market Cap (M USD)" in df.columns:
        df["Market Cap (M USD)"] = pd.to_numeric(df["Market Cap (M USD)"], errors="coerce")
        df = df.sort_values(by="Market Cap (M USD)", ascending=False)

    # Reset index starting at 1
    df = df.reset_index(drop=True)
    df.index = df.index + 1
    return df.round(2)

def apply_filters(df, cap_range=None, top_n=None, selected_ratings=None):
    """
    Applies filters on the DataFrame:
    - cap_range: tuple of (min, max) market cap in millions USD
    - top_n: integer to limit to top N companies by market cap
    - selected_ratings: list of ratings to filter by
    Returns the filtered DataFrame.
    """
    if "Market Cap (M USD)" in df.columns:
        df["Market Cap (M USD)"] = pd.to_numeric(df["Market Cap (M USD)"], errors="coerce")
        if cap_range:
            df = df[(df["Market Cap (M USD)"] >= cap_range[0]) & (df["Market Cap (M USD)"] <= cap_range[1])]
        if top_n:
            df = df.nlargest(top_n, "Market Cap (M USD)")
    if selected_ratings and "Rating" in df.columns:
        df = df[df["Rating"].isin(selected_ratings)]
    return df

def normalise_for_gradient(series, reverse=False):
    """
    Normalises a numeric pandas Series for gradient coloring.
    Clips values between 5th and 95th percentiles to reduce outlier impact,
    then scales to 0-1 range. Optionally reverses the scale.
    """
    numeric_series = pd.to_numeric(series, errors='coerce').dropna()
    lower = numeric_series.quantile(0.05)
    upper = numeric_series.quantile(0.95)
    # Clip values to the 5th and 95th percentile range to reduce outlier effect
    clipped = numeric_series.clip(lower, upper)
    # Scale clipped values to 0-1 range
    normalised = (clipped - lower) / (upper - lower)
    if reverse:
        normalised = 1 - normalised
    # Reindex to original series index, filling missing with None
    return normalised.reindex(series.index, fill_value=None)

def create_styler(df, gradient_columns=None, inverse_gradient_columns=None):
    """
    Creates a pandas Styler object for the DataFrame with background gradients applied
    to specified columns for visual emphasis. Supports normal and inverse gradients.
    """
    if gradient_columns is None:
        gradient_columns = []
    if inverse_gradient_columns is None:
        inverse_gradient_columns = []

    styler = df.style.format(precision=2)  
      
    for col in gradient_columns:
        if col in df.columns:
            gmap = normalise_for_gradient(df[col])
            styler = styler.background_gradient(cmap="RdYlGn", subset=[col], gmap=gmap)

    for col in inverse_gradient_columns:
        if col in df.columns:
            gmap = normalise_for_gradient(df[col], reverse=True)
            styler = styler.background_gradient(cmap="RdYlGn", subset=[col], gmap=gmap)

    return styler

def process_uploaded_tickers(uploaded_file, existing_df):
    """
    Read an uploaded Excel file containing tickers (first column),
    fetch additional company data, and combine with an existing DataFrame.
    Returns (combined_df, error_msg).  If error_msg is not None, the DataFrame is None.
    """
    try:
        # Read Excel file without header
        custom_df = pd.read_excel(uploaded_file, header=None)
    except Exception as e:
        return None, f"Error reading uploaded file: {e}"

    # Assume tickers are in the first column
    tickers = custom_df.iloc[:, 0]

    # Drop NaN, strip whitespace, convert to string and uppercase
    tickers = tickers[~tickers.isna()].astype(str).str.strip().str.upper()

    # Remove empty rows
    tickers = tickers[tickers != ""]

    # Ensure one ticker per row: if extra columns contain non-null values, return error
    if custom_df.shape[1] > 1 and custom_df.iloc[:, 1:].notna().any().any():
        return None, "Excel file must contain exactly 1 ticker per row (extra columns detected)."

    # Remove duplicates
    tickers = tickers.drop_duplicates()

    # Convert to list
    tickers = tickers.tolist()

    # Final check
    if not tickers:
        return None, "No valid tickers found in uploaded file. Ensure 1 ticker per row."

    # Build names list using yfinance shortName for each ticker
    names = []
    yf_tickers = yf.Tickers(" ".join(tickers)).tickers
    for ticker in tickers:
        info = yf_tickers.get(ticker, {}).info if ticker in yf_tickers else {}
        name = info.get("shortName", None)
        names.append(name)

    df_symbols = pd.DataFrame({"symbol": tickers, "name": names})
    # Fetch enriched data for uploaded tickers
    uploaded_data_df = fetch_additional_company_data(df_symbols)

    # Combine with existing data if present, filtering out empty DataFrames
    frames = [df for df in [existing_df, uploaded_data_df] if df is not None and not df.empty]
    if frames:
        combined_df = pd.concat(frames, ignore_index=True)
    else:
        combined_df = pd.DataFrame()

    return combined_df, None

def generate_styled_excel(df, gradient_columns=None, inverse_gradient_columns=None, sheet_name="Sheet1"):
    """
    Generates an in-memory styled Excel file with background gradients applied.
    Returns a BytesIO buffer containing the Excel file.
    """
    buffer = BytesIO()
    styler = create_styler(df, gradient_columns, inverse_gradient_columns)
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        styler.to_excel(writer, sheet_name=sheet_name)
    buffer.seek(0)
    return buffer

def generate_plain_excel(df, sheet_name="Sheet1"):
    """
    Generates an in-memory plain Excel file without styling.
    Returns a BytesIO buffer containing the Excel file.
    """
    buffer = BytesIO()
    df.to_excel(buffer, index=False, sheet_name=sheet_name, engine="openpyxl")
    buffer.seek(0)
    return buffer

def render_download_buttons(
    df,
    styled_filename,
    plain_filename,
    gradient_columns=None,
    inverse_gradient_columns=None,
    sheet_name="Sheet1"
):
    """
    Lazily generate and render download buttons for styled and plain Excel files.
    Provides two options: a formatted Excel with gradients and a plain Excel without styling.
    """
    col1, col2, _ = st.columns([1, 1, 7])
    with col1:
        st.download_button(
            label="Formatted Excel",
            data=generate_styled_excel(df, gradient_columns, inverse_gradient_columns, sheet_name=sheet_name),
            file_name=styled_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    with col2:
        st.download_button(
            label="Plain Excel",
            data=generate_plain_excel(df, sheet_name=sheet_name),
            file_name=plain_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

def get_gradient_columns():
    """Return gradient and inverse gradient column lists for styling."""
    gradient_columns = ["Gross Margin (%)", "EBIT Margin (%)", "EBITDA Margin (%)"]
    inverse_gradient_columns = ["P/E", "EV/EBITDA", "EV/Sales", "P/FCF"]
    return gradient_columns, inverse_gradient_columns

def render_filter_ui(df, label_suffix=""):
    """Render cap, top N, and rating filters and return user-selected values."""
    cap_range = None
    top_n = None
    selected_ratings = None

    with st.expander(f"Apply Filters{label_suffix}", expanded=False):
        # Render market cap slider if column exists and has numeric data
        if "Market Cap (M USD)" in df.columns:
            cap_series = pd.to_numeric(df["Market Cap (M USD)"], errors="coerce").dropna()
            if not cap_series.empty:
                min_cap = int(cap_series.min()) - 1
                max_cap = int(cap_series.max()) + 1
                cap_col, _ = st.columns([2, 5])
                with cap_col:
                    cap_range = st.slider(
                        f"Market Cap (in million $){label_suffix}:",
                        min_value=min_cap,
                        max_value=max_cap,
                        value=(min_cap, max_cap)
                    )
            else:
                st.info("Market Cap column found but contains no numeric values.")
        else:
            st.info("Market Cap (M USD) column not found in data.")

        # Checkbox to show only top 20 by market cap
        show_top_20 = st.checkbox(f"Show only top 20 by Market Cap{label_suffix}")
        if show_top_20:
            top_n = 20

        # Render rating filter checkboxes if Rating column exists
        if "Rating" in df.columns:
            st.markdown(f"**Filter by Rating{label_suffix}:**")
            ratings = sorted(df["Rating"].dropna().unique())
            rating_cols = st.columns(len(ratings))
            selected_ratings = [
                rating for col, rating in zip(rating_cols, ratings)
                if col.checkbox(
                    (str(rating) if rating else "Unknown"),
                    value=True,
                    key=f"{label_suffix}_rating_{str(rating) if rating else 'Unknown'}"
                )
            ]

    return cap_range, top_n, selected_ratings
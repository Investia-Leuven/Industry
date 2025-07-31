import yfinance as yf
def get_available_sectors():
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


import streamlit as st

def get_industries_for_sector(sector_key):
    try:
        sector = yf.Sector(sector_key)
        df = sector.industries  # This returns a DataFrame
        return dict(zip(df["name"], df.index))
    except Exception:
        return {}


# Get companies for an industry using the selected data method
def get_companies_for_industry(industry_key, data_method):
    try:
        industry = yf.Industry(industry_key)
        df = getattr(industry, data_method)
        return df
    except Exception:
        return None

import pandas as pd

"""
Combines data from multiple industries into one DataFrame and enriches it with additional financial metrics.
"""
def combine_industry_dataframes(industry_names, industry_keys, data_method):
    """
    Returns a single enriched DataFrame for selected industries using the specified data method.
    """
    combined_list = []
    for industry_name, industry_key in zip(industry_names, industry_keys):
        df = get_companies_for_industry(industry_key, data_method)
        if df is not None and not df.empty:
            if 'symbol' not in df.columns and df.index.name == 'symbol':
                df = df.reset_index()
            df = df.copy()
            df["Industry"] = industry_name
            combined_list.append(df)
    if not combined_list:
        return pd.DataFrame()
    full_df = pd.concat(combined_list, ignore_index=True)
    enriched_df = fetch_additional_company_data(full_df)
    return enriched_df

"""
Fetches extended financial data from Yahoo Finance for a list of company tickers.
Converts currencies to USD, scales to millions, and calculates financial ratios.
"""
def fetch_additional_company_data(df_with_symbols):
    """
    Extends the given DataFrame of companies with additional financial metrics from yfinance.
    Returns a DataFrame with columns in the specified order.
    """
    import pandas as pd
    tickers = df_with_symbols["symbol"].tolist()
    yf_tickers = yf.Tickers(" ".join(tickers)).tickers

    enriched_data = []

    for _, row in df_with_symbols.iterrows():
        symbol = row["symbol"]
        company_name = row.get("name")
        # If company_name is None or empty, try to get from yf_tickers info shortName
        if not company_name:
            info_temp = yf_tickers.get(symbol, {}).info if symbol in yf_tickers else {}
            company_name = info_temp.get("shortName", None)
        industry = row.get("Industry", "")
        market_weight = row.get("market weight", None)
        rating = row.get("rating", "")

        info = yf_tickers.get(symbol, {}).info if symbol in yf_tickers else {}
        currency = info.get("currency", "USD")

        # Example exchange rates (mock)
        exchange_rates = {
            "USD": 1.0,
            "EUR": 1.1,
            "GBP": 1.3,
            "JPY": 0.007,
            "CAD": 0.75
        }
        rate = exchange_rates.get(currency, 1.0)

        # Convert market_weight to percentage if available
        if market_weight is not None:
            market_weight *= 100  # convert to percentage

        # Use ebitMargins, fallback to operatingMargins if not available
        ebit_margin = info.get("ebitMargins")
        if ebit_margin is None:
            ebit_margin = info.get("operatingMargins")

        # Convert margin fields to percentage
        gross_margin = info.get("grossMargins")
        if gross_margin is not None:
            gross_margin *= 100

        if ebit_margin is not None:
            ebit_margin *= 100

        ebitda_margin = info.get("ebitdaMargins")
        if ebitda_margin is not None:
            ebitda_margin *= 100

        revenue = info.get("totalRevenue")
        market_cap = info.get("marketCap")
        free_cashflow = info.get("freeCashflow")
        enterprise_to_ebitda = info.get("enterpriseToEbitda")
        enterprise_to_revenue = info.get("enterpriseToRevenue")

        # Convert financial values to USD and to millions
        revenue = (revenue * rate / 1_000_000) if revenue is not None else None
        market_cap = (market_cap * rate / 1_000_000) if market_cap is not None else None
        free_cashflow = (free_cashflow * rate / 1_000_000) if free_cashflow is not None else None

        p_fcf_ratio = (market_cap / free_cashflow) if market_cap and free_cashflow else None

        enriched_data.append({
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

    # Specify the column order
    columns = [
        "Name", "Ticker", "Revenue (M USD)", "Market Cap (M USD)", "Gross Margin (%)",
        "EBIT Margin (%)", "EBITDA Margin (%)", "P/E", "EV/EBITDA", "EV/Sales",
        "P/FCF", "Market Weight (%)", "Industry", "Rating"
    ]
    df = pd.DataFrame(enriched_data, columns=columns)
    return df.round(2)

def apply_final_sorting_and_formatting(df):
    import pandas as pd
    if "Market Cap (M USD)" in df.columns:
        df["Market Cap (M USD)"] = pd.to_numeric(df["Market Cap (M USD)"], errors="coerce")
        df = df.sort_values(by="Market Cap (M USD)", ascending=False)
    return df.reset_index(drop=True).round(2)

def apply_filters(df, cap_range=None, top_n=None, selected_ratings=None):
    import pandas as pd
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
    import pandas as pd
    numeric_series = pd.to_numeric(series, errors='coerce').dropna()
    lower = numeric_series.quantile(0.05)
    upper = numeric_series.quantile(0.95)
    clipped = numeric_series.clip(lower, upper)
    normalised = (clipped - lower) / (upper - lower)
    if reverse:
        normalised = 1 - normalised
    return normalised.reindex(series.index, fill_value=None)

def create_styler(df, gradient_columns=None, inverse_gradient_columns=None):
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
    import pandas as pd
    try:
        custom_df = pd.read_excel(uploaded_file, header=None)
    except Exception as e:
        return None, f"Error reading uploaded file: {e}"

    # Assume tickers are in the first column
    tickers = custom_df.iloc[:, 0]
    tickers = tickers[~tickers.isna()].astype(str).str.strip()
    tickers = tickers[tickers != ""].tolist()
    if not tickers:
        return None, "No tickers found in uploaded file."

    # Build names list using yfinance shortName for each ticker
    names = []
    yf_tickers = yf.Tickers(" ".join(tickers)).tickers
    for ticker in tickers:
        info = yf_tickers.get(ticker, {}).info if ticker in yf_tickers else {}
        name = info.get("shortName", None)
        names.append(name)

    df_symbols = pd.DataFrame({"symbol": tickers, "name": names})
    uploaded_data_df = fetch_additional_company_data(df_symbols)

    if existing_df is not None and not existing_df.empty:
        combined_df = pd.concat([existing_df, uploaded_data_df], ignore_index=True)
    else:
        combined_df = uploaded_data_df

    return combined_df, None

def generate_styled_excel(df, gradient_columns=None, inverse_gradient_columns=None, sheet_name="Sheet1"):
    from io import BytesIO
    buffer = BytesIO()
    styler = create_styler(df, gradient_columns, inverse_gradient_columns)
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        styler.to_excel(writer, sheet_name=sheet_name)
    buffer.seek(0)
    return buffer

def generate_plain_excel(df, sheet_name="Sheet1"):
    from io import BytesIO
    buffer = BytesIO()
    df.to_excel(buffer, index=False, sheet_name=sheet_name, engine="openpyxl")
    buffer.seek(0)
    return buffer

def render_download_buttons(styled_buffer, styled_filename, plain_buffer, plain_filename):
    import streamlit as st
    col1, col2, _ = st.columns([2, 2, 14])
    with col1:
        st.download_button(
            label="Formatted Excel",
            data=styled_buffer,
            file_name=styled_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    with col2:
        st.download_button(
            label="Plain Excel",
            data=plain_buffer,
            file_name=plain_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
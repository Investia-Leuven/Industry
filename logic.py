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
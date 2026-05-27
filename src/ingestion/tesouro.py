"""
src/ingestion/tesouro.py
 
Pulls historical bond prices from the Tesouro Transparente open data CSV.
 
Source: https://www.tesourotransparente.gov.br/ckan/dataset/taxas-dos-titulos-ofertados-pelo-tesouro-direto
 
Bonds used:
    NTN-B  — IPCA-linked, pays real coupon.   Input for real yield curve.
    NTN-F  — Prefixed, pays nominal coupon.   Long end of nominal curve.
    LTN    — Prefixed zero-coupon.            Short-to-medium nominal curve.
"""

import logging
from datetime import date, timedelta
from io import StringIO
from typing import Optional
 
import pandas as pd
import requests
 
logger = logging.getLogger(__name__)

# Constants

TESOURO_CSV_URL = (
    "https://www.tesourotransparente.gov.br/ckan/dataset/"
    "df56aa42-484a-4a59-8184-7676580c81e3/resource/"
    "796d2059-14e9-44e3-80c9-2d9e30b405c1/download/"
    "PrecoTaxaTesouroDireto.csv"
)

# CSV bond name
BOND_TYPE_MAP = {
    "Tesouro IPCA+ com Juros Semestrais": "ntnb_coupon", 
    "Tesouro IPCA+": "ntnb_zero",
    "Tesouro Prefixado com Juros Semestrais": "ntnf",
    "Tesouro Prefixado": "ltn",
}

RATE_BOUNDS = {
    "ntnb_zero": (0.0, 30.0),
    "ntnb_coupon": (0.0, 30.0),
    "ntnf": (0.0, 50.0),
    "ltn": (0.0, 50.0),
}


# Fetch

def list_symbols() -> list[str]:
    """
    Return all available Tesouro Direto symbols from brapi.    
    """
    url = f"{BRAPI_BASE}/treasury"
    resp = requests.get(url, headers=_headers(), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return [item["symbol"] for item in data.get("treasuries", [])]


def fetch_historical(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    max_retries: int = 3,
) -> pd.DataFrame:
    """
    Download the Tesouro Transparente CSV and return a tidy DataFrame
    filtered to the bonds and date range relevant to this project.

    Returns columns:
        date, bond_type, bond_name, maturity, pu_buy, pu_sell, pu_base, rate_annual
    """
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=365 * 2)

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Fetching Tesouro Transparente CSV (attempt {attempt})")
            resp = requests.get(TESOURO_CSV_URL, timeout=60)
            resp.raise_for_status()
            break
        except requests.exceptions.RequestException as exc:
            logger.warning(f"Attempt {attempt} failed: {exc}")
            if attempt == max_retries:
                raise

    df_raw = pd.read_csv(
        StringIO(resp.content.decode("utf-8")),
        sep=";",
        decimal=",",
        thousands=".",
    )

    return _parse(df_raw, start_date, end_date)

# Parsing

def _parse(df_raw: pd.DataFrame, start_date: date, end_date: date) -> pd.DataFrame:
    """
    Rename columns, classify bond types, filter date range.
    Midpoint of buy/sell rates is used as rate_annual.
    """
    df = df_raw.rename(columns={
        "Tipo Titulo": "bond_name",
        "Data Vencimento": "maturity",
        "Data Base": "date",
        "Taxa Compra Manha": "rate_buy",
        "Taxa Venda Manha":"rate_sell",
        "PU Compra Manha": "pu_buy",
        "PU Venda Manha": "pu_sell",
        "PU Base Manha": "pu_base",
    }).copy()

    df["date"] = pd.to_datetime(df["date"],     dayfirst=True, errors="coerce")
    df["maturity"] = pd.to_datetime(df["maturity"], dayfirst=True, errors="coerce")

    df["bond_type"] = df["bond_name"].map(_classify)
    df = df[df["bond_type"].notna()].copy()

    df = df[
        (df["date"].dt.date >= start_date) &
        (df["date"].dt.date <= end_date)
    ]

    df["rate_annual"] = (df["rate_buy"] + df["rate_sell"]) / 2

    cols = ["date", "bond_type", "bond_name", "maturity", "pu_buy", "pu_sell", "pu_base", "rate_annual"]
    df = df[cols].sort_values(["bond_type", "maturity", "date"]).reset_index(drop=True)

    logger.info(f"Tesouro: {len(df)} records | {df['date'].min().date()} → {df['date'].max().date()}")
    return df


def _classify(bond_name: str) -> Optional[str]:
    """Map CSV bond name to internal bond_type."""
    for key, label in BOND_TYPE_MAP.items():
        if str(bond_name).startswith(key):
            return label
    return None

# Validation

# Plausible bounds

RATE_BOUNDS = {
    "ntnb": (0.0, 30.0),
    "ntnf": (0.0, 50.0),
    "ltn":  (0.0, 50.0),
}

def validate(df: pd.DataFrame) -> pd.DataFrame:
    """Add is_valid column flagging out-of-bounds or null rates."""
    df = df.copy()
    in_bounds = pd.Series(True, index=df.index)

    for bond_type, (lo, hi) in RATE_BOUNDS.items():
        mask = df["bond_type"] == bond_type
        in_bounds &= ~(mask & ~df["rate_annual"].between(lo, hi))

    df["is_valid"] = in_bounds & df["rate_annual"].notna() & df["pu_base"].notna()

    n = (~df["is_valid"]).sum()
    if n:
        logger.warning(f"{n} invalid rows flagged.")
    return df



# Fetching

def fetch_all(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> dict[str, pd.DataFrame]:
    """
    Fetch, parse, and validate Tesouro data.
    Returns dict keyed by bond_type: 'ntnb', 'ntnf', 'ltn'.
    """
    df = fetch_historical(start_date=start_date, end_date=end_date)
    df = validate(df)

    return {
        bt: df[df["bond_type"] == bt].reset_index(drop=True)
        for bt in ("ntnb_zero", "ntnb_coupon", "ntnf", "ltn")
    }
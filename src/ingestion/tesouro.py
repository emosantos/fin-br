"""
src/ingestion/tesouro.py

Pulls historical bond prices from the Tesouro Direto public API.

Docs: https://www.tesourodireto.com.br/dados-abertos.htm

Bonds:
    NTN-B  — IPCA-linked, pays real coupon. Input for real yield curve.
    NTN-F  — Prefixed, pays nominal coupon. Input for long nominal curve.
    LTN    — Prefixed zero-coupon. Input for short nominal curve.

Returns per bond per day:
    - maturity date
    - buy price (PU compra)
    - sell price (PU venda)
    - theoretical price (PU base — mid, used for curve fitting)
    - annual yield (taxa)
"""

import logging
from datetime import date, timedelta
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# Constants

TESOURO_URL = (
    "https://www.tesourodireto.com.br/json/br/com/b3/tesourodireto/"
    "pontodevenda/dados/historico"
)

BONDS_OF_INTEREST = ("Tesouro IPCA+", "Tesouro Prefixado 2", "Tesouro Prefixado")

BOND_TYPE_MAP = {
    "Tesouro IPCA+":         "ntnb",
    "Tesouro Prefixado 2":   "ntnf",   # NTN-F has semiannual coupons
    "Tesouro Prefixado":     "ltn",    # LTN is zero-coupon
}

# Fetch

def fetch_historical(
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        max_retries: int = 3,
    ) -> pd.DataFrame:
    """
    Fetch historical bond prices from Tesouro Direto API.

    Args:
        start_date: First date to fetch. Defaults to 2 years ago.
        end_date:   Last date to fetch. Defaults to today.
        max_retries: HTTP retry attempts

    Returns:
        DataFrame with columns:
            date, bond_type, maturity, pu_buy, pu_sell, rate_annual (Later validated)
    """
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=365 * 2)

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Fetching Tesouro Direto historical data from {start_date} to {end_date} (attempt {attempt})")
            response = requests.get(
                TESOURO_URL,
                timeout=60,
                headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}
                )
            response.raise_for_status()
            break
        except requests.exceptions.RequestException as exc:
            logger.warning(f"Attempt {attempt} failed: {exc}")
            if attempt==max_retries:
                raise
    raw = response.json()
    records = _parse(raw, start_date=start_date, end_date=end_date)

    df = df.sort_values(['bond_type', 'maturity', 'date']).reset_index(drop=True)
    logger.info(f"Tesouro: {len(df)} records from {df['date'].min().date()} to {df['date'].max().date()}")

    return df

# Parsing

def _parse(
    raw: dict,
    start_date: date,
    end_date: date,
) -> list[dict]:

    """
    Extract relevant fields from Tesouro's nested JSON response.
    """
    records = []

    try:
        bond_list = raw["response"]["TituloPUsTaxasList"]
    except (KeyError, TypeError) as exc:
        logger.error(f"Unexpected Tesouro response structure: {exc}")
        return records

    for bond_entry in bond_list:
        bond_name = bond_entry.get("nm_titulo", "")
        bond_type = _classify(bond_name)
        if bond_type is None:
            continue  # skip bonds not relevant

        maturity_str = bond_entry.get("dt_vencimento", "")
        try:
            maturity = pd.to_datetime(maturity_str, dayfirst=True).date()
        except Exception:
            logger.warning(f"Could not parse maturity date '{maturity_str}' for {bond_name}")
            continue

        for price_entry in bond_entry.get("titulos", []):
            date_str = price_entry.get("dt_referencia", "")
            try:
                ref_date = pd.to_datetime(date_str, dayfirst=True).date()
            except Exception:
                continue

            if not (start_date <= ref_date <= end_date):
                continue

            records.append({
                "date":        pd.Timestamp(ref_date),
                "bond_type":   bond_type,
                "bond_name":   bond_name,
                "maturity":    pd.Timestamp(maturity),
                "pu_buy":      _to_float(price_entry.get("vl_pu_compra")),
                "pu_sell":     _to_float(price_entry.get("vl_pu_venda")),
                "pu_base":     _to_float(price_entry.get("vl_pu_base")),
                "rate_annual": _to_float(price_entry.get("tx_taxa")),
            })

    return records

def _classify(bond_name: str) -> Optional[str]:
    """Map a bond name to the internal bond_type label."""
    # check NTN-F ("Prefixado 2") before LTN ("Prefixado")
    for key, label in BOND_TYPE_MAP.items():
        if bond_name.startswith(key):
            return label
    return None


def _to_float(value) -> Optional[float]:
    """Convert Tesouro's string/numeric values to float ."""
    try:
        return float(str(value).replace(",", "."))
    except (ValueError, TypeError):
        return None

# Validation

# Plausible annual yield ranges per bond type
RATE_BOUNDS: dict[str, tuple[float, float]] = {
    "ntnb": (0.0, 30.0),   # real yield 
    "ntnf": (0.0, 50.0),   # nominal prefixed
    "ltn":  (0.0, 50.0),   # nominal prefixed zero-coupon
}

PU_BOUNDS = (100.0, 20_000.0)  


def validate(df: pd.DataFrame) -> pd.DataFrame:
    """
    Flag rows where yields or PU prices fall outside plausible bounds.
    Adds `is_valid` boolean column.
    """
    df = df.copy()
    valid = pd.Series(True, index=df.index)

    for bond_type, (lo, hi) in RATE_BOUNDS.items():
        mask = df["bond_type"] == bond_type
        valid &= ~(mask & df["rate_annual"].between(lo, hi) == False)

    pu_ok  = df["pu_base"].between(*PU_BOUNDS) | df["pu_base"].isna()
    null_rate = df["rate_annual"].isna()

    df["is_valid"] = valid & pu_ok & ~null_rate

    n_invalid = (~df["is_valid"]).sum()
    if n_invalid:
        logger.warning(f"Tesouro: {n_invalid} invalid rows flagged.")

    return df

# Fetching

def fetch_all(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> dict[str, pd.DataFrame]:
    """
    Fetch, parse, and validate Tesouro data.
    Returns a dict with one DataFrame per bond type.

    Keys: 'ntnb', 'ntnf', 'ltn'
    """
    df = fetch_historical(start_date=start_date, end_date=end_date)
    df = validate(df)

    return {
        bond_type: df[df["bond_type"] == bond_type].reset_index(drop=True)
        for bond_type in ("ntnb", "ntnf", "ltn")
    }
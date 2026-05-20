"""
Pulls time series from Banco Central SGS API
Docs:https://www.bcb.gov.br/estatisticas/sgspub

Series used in this project: # PPP Confirm after over
    12   — CDI diário (% a.d.)
    433  — IPCA mensal (% a.m.)
    226  — TR diária (% a.d.)
    432  — SELIC meta (% a.a.)
    11   — SELIC diária efetiva (% a.d.) 
"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional

import boto3
import pandas as pd
import requests

# Logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Constants

BCB_SGS_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{series_id}/dados"

SERIES = {
    "cdi_daily": 12,
    "ipca_monthly": 433,
    "tr_daily": 226,
    "selic_target": 432,
    "selic_daily": 11,
}

DATE_FORMAT = "%d/%m/%Y"

# Fetch

def fetch_series(
    series_id: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    max_retries: int = 3,
) -> pd.DataFrame:
    """
    Fetch a single BCB SGS series and return a DataFrame
    Args:
        series_id:   BCB SGS numeric series code.
        start_date:  First date to fetch. Defaults to 2 years ago.
        end_date:    Last date to fetch. Defaults to today.
        max_retries: Number of HTTP retry attempts on transient errors.
    Retunrs:
        DataFrame with columns [date, value, series_id].
    """
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=730)

    params = {
        "formato": "json",
        "dataInicial": start_date.strftime(DATE_FORMAT),
        "dataFinal":   end_date.strftime(DATE_FORMAT),
    }
    url = BCB_SGS_URL.format(series_id=series_id)

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Fetching series {series_id} | {start_date} → {end_date} (attempt {attempt})")
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            break
        except requests.exceptions.HTTPError as exc:
            logger.warning(f"HTTP error on attempt {attempt}: {exc}")
            if attempt == max_retries:
                raise
        except requests.exceptions.RequestException as exc:
            logger.warning(f"Request error on attempt {attempt}: {exc}")
            if attempt == max_retries:
                raise

    raw = response.json()
    if not raw:
        logger.warning(f"Series {series_id} returned empty data for the requested period.")
        return pd.DataFrame(columns=["date", "value", "series_id"])

    df = pd.DataFrame(raw)
    df["date"]      = pd.to_datetime(df["data"], format=DATE_FORMAT)
    df["value"]     = pd.to_numeric(df["valor"], errors="coerce")
    df["series_id"] = series_id
    df = df[["date", "value", "series_id"]].sort_values("date").reset_index(drop=True)

    logger.info(f"Series {series_id}: {len(df)} records fetched.")
    return df

# Validation

BOUNDS: dict[int, tuple[float,float]] = {
    12:  (0.0, 5.0),     # CDI daily
    433: (-5.0, 10.0),   # IPCA monthly
    226: (0.0, 5.0),     # TR daily
    432: (0.0, 100.0),   # SELIC target annual %
    11:  (0.0, 5.0),     # SELIC daily
}
    
def validate(df: pd.DataFrame) -> pd.DataFrame:
    """
    Flag rows with null values or out-of-bounds rates.
    Adds a boolean column `is_valid` and logs any anomalies found.
    """
    series_id = df["series_id"].iloc[0] if not df.empty else None
    lo, hi = BOUNDS.get(series_id, (-1e9, 1e9))

    df = df.copy()
    null_mask  = df["value"].isna()
    range_mask = ~df["value"].between(lo, hi)
    df["is_valid"] = ~(null_mask | range_mask)

    n_invalid = (~df["is_valid"]).sum()
    if n_invalid:
        logger.warning(f"Series {series_id}: {n_invalid} invalid rows flagged.")
        logger.warning(df[~df["is_valid"]])

    return df
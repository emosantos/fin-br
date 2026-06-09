"""
src/curves/bootstrap.py
Functions to extract zero-coupon yields from Tesouro Direto bonds.
Focus: NTN-B Principal (Real Curve) and LTN (Nominal Curve).
"""

import pandas as pd
import numpy as np
from src.curves.utils import count_bus_days, to_annual_rate


def bootstrap_ntnb_principal(df_tesouro: pd.DataFrame, df_vna: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates the real yield for NTN-B Principal (zero coupon).
    
    1. Merge bond prices with the VNA of the reference date.
    2. Calculate DU (Business Days) between trade date and maturity.
    3. Solve for the annual yield.
    """
    # Filter only for NTN-B Principal (Zero Coupon)

    df = df_tesouro[df_tesouro["bond_type"] == "ntnb_zero"].copy()
    
    # Merge with VNA data from BCB

    df = pd.merge(df, df_vna[['date', 'value']], on='date', how='left')
    df = df.rename(columns={'value': 'vna'})

    # Calculate Business Days (DU)
    df['du'] = df.apply(lambda x: count_bus_days(x['date'].date(), x['maturity'].date()), axis=1)
    
    # Calculate the implied Yield
    # Formula: (VNA / PU) ^ (252 / DU) - 1

    df['yield_calculated'] = (df['vna'] / df['pu_base'])**(252 / df['du']) - 1
    
    return df[['date', 'maturity', 'du', 'pu_base', 'vna', 'yield_calculated']]

def bootstrap_ltn(df_tesouro: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates the nominal yield for LTN (Letra do Tesouro Nacional).
    LTNs have a fixed face value of 1000 BRL at maturity.
    """
    df = df_tesouro[df_tesouro["bond_type"] == "ltn"].copy()
    
    FACE_VALUE = 1000.0
    
    df['du'] = df.apply(lambda x: x.count_bus_days(x['date'].date(), x['maturity'].date()), axis=1)
    
    # Formula: (1000 / PU) ^ (252 / DU) - 1
    df['yield_calculated'] = (FACE_VALUE / df['pu_base'])**(252 / df['du']) - 1
    
    return df[['date', 'maturity', 'du', 'pu_base', 'yield_calculated']]
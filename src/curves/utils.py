"""
src/curves/utils.py
Core financial utilities for the Brazilian fixed-income market.
Convention: Business Days / 252.
"""

import pandas as pd
import numpy as np
from datetime import date, timedelta
from typing import Union, List

# Holidays

def get_easter_date(year: int) -> date:
    """
    Calculate Easter Sunday using the Anonymous Gregorian algorithm.
    All movable Brazilian holidays are offsets of this date.
    """
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    L = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * L) // 451
    month = (h + L - 7 * m + 114) // 31
    day = ((h + L - 7 * m + 114) % 31) + 1
    return date(year, month, day)

def get_br_holidays(year: int) -> List[date]:
    """
    Returns a list of official Brazilian national holidays (ANBIMA standard).
    Includes fixed dates and movable dates (Carnival, Good Friday, Corpus Christi).
    """
    # Fixed-date holidays
    holidays = [
        date(year, 1, 1), # Confraternização Universal
        date(year, 4, 21), # Tiradentes
        date(year, 5, 1), # Dia do Trabalho
        date(year, 9, 7), # Independência
        date(year, 10, 12), # Nossa Senhora Aparecida
        date(year, 11, 2), # Finados
        date(year, 11, 15), # Proclamação da República
        date(year, 11, 20), # Consciência Negra (New national holiday)
        date(year, 12, 25), # Natal
    ]
    
    # Movable holidays (Offsets from Easter)
    easter = get_easter_date(year)
    holidays.append(easter - timedelta(days=48)) # Carnival Monday
    holidays.append(easter - timedelta(days=47)) # Carnival Tuesday
    holidays.append(easter - timedelta(days=2))  # Passion of Christ (Friday)
    holidays.append(easter + timedelta(days=60)) # Corpus Christi
    
    return sorted(holidays)

# Calendar Logic

def count_bus_days(start: date, end: date) -> int:
    """
    Calculates Dias Úteis (DU) between two dates inclusive of start, exclusive of end.
    Standard convention for Brazilian financial contracts.
    """
    if start >= end:
        return 0
    
    # Generate holiday list for all years in range
    years = range(start.year, end.year + 1)
    all_holidays = []
    for y in years:
        all_holidays.extend(get_br_holidays(y))
    
    # Using pandas to calculate business days excluding weekends and custom holidays
    # Note: 'B' frequency in pandas is Mon-Fri
    bus_days = pd.bdate_range(start=start, end=end, holidays=all_holidays, freq='C', weekmask='Mon Tue Wed Thu Fri')
    
    # Counting intervals (end date is the payment/settlement day)
    return len(bus_days) - 1

# Rate conversion


def to_daily_rate(annual_rate: float) -> float:
    """
    Converts % a.a. to a decimal daily rate.
    Formula: (1 + r_annual)^(1/252) - 1
    """
    return (1 + annual_rate)**(1/252) - 1

def to_annual_rate(daily_rate: float) -> float:
    """
    Converts decimal daily rate to % a.a.
    Formula: (1 + r_daily)^252 - 1
    """
    return (1 + daily_rate)**252 - 1
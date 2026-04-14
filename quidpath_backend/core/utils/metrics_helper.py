"""
Metrics Helper Utilities
Provides reusable functions for calculating period-over-period comparisons
"""
from decimal import Decimal
from typing import Tuple


def calculate_percentage_change(current: Decimal, previous: Decimal) -> float:
    """
    Calculate percentage change between current and previous values.
    
    Args:
        current: Current period value
        previous: Previous period value
        
    Returns:
        Percentage change as float (e.g., 12.5 for 12.5% increase)
    """
    if previous > 0:
        return float(((current - previous) / previous) * 100)
    return 0.0


def get_trend_direction(change: float) -> str:
    """
    Determine trend direction based on percentage change.
    
    Args:
        change: Percentage change value
        
    Returns:
        "up", "down", or "neutral"
    """
    if change > 0:
        return "up"
    elif change < 0:
        return "down"
    return "neutral"


def calculate_metric_comparison(
    current: Decimal, 
    previous: Decimal
) -> Tuple[float, float, str]:
    """
    Calculate full comparison metrics for a value.
    
    Args:
        current: Current period value
        previous: Previous period value
        
    Returns:
        Tuple of (current_float, previous_float, change_percent, trend)
    """
    change = calculate_percentage_change(current, previous)
    trend = get_trend_direction(change)
    return float(current), float(previous), round(change, 1), trend


def add_comparison_to_response(
    data: dict,
    metric_name: str,
    current: Decimal,
    previous: Decimal
) -> None:
    """
    Add comparison metrics to response dictionary in-place.
    
    Args:
        data: Response dictionary to update
        metric_name: Base name of the metric (e.g., "total_revenue")
        current: Current period value
        previous: Previous period value
    """
    current_val, prev_val, change, trend = calculate_metric_comparison(current, previous)
    data[metric_name] = current_val
    data[f"{metric_name}_previous"] = prev_val
    data[f"{metric_name}_change"] = change
    data[f"{metric_name}_trend"] = trend

"""
Position sizing calculator.
"""

from typing import Dict, Optional


def calculate_position(
    capital: float,
    risk_pct: float,
    entry: float,
    stop_loss: float,
    lot_size: int = 1,
) -> Dict:
    """
    Classic risk-based position sizing.

    Returns:
        quantity, capital_required, risk_amount, r_multiple etc.
    """
    if entry <= 0 or stop_loss >= entry or capital <= 0 or risk_pct <= 0:
        return {
            "quantity": 0,
            "capital_required": 0,
            "risk_amount": 0,
            "risk_per_share": 0,
            "max_loss": 0,
            "message": "Invalid inputs",
        }

    risk_amount = capital * (risk_pct / 100.0)
    risk_per_share = entry - stop_loss
    if risk_per_share <= 0:
        return {
            "quantity": 0,
            "capital_required": 0,
            "risk_amount": risk_amount,
            "risk_per_share": 0,
            "max_loss": 0,
            "message": "Stop loss must be below entry",
        }

    raw_qty = risk_amount / risk_per_share
    # Round down to nearest lot
    quantity = int(raw_qty // lot_size) * lot_size
    if quantity < lot_size:
        quantity = 0

    capital_required = quantity * entry
    max_loss = quantity * risk_per_share

    return {
        "quantity": quantity,
        "capital_required": round(capital_required, 2),
        "risk_amount": round(risk_amount, 2),
        "risk_per_share": round(risk_per_share, 2),
        "max_loss": round(max_loss, 2),
        "message": "OK" if quantity > 0 else "Risk too small for even 1 lot",
    }

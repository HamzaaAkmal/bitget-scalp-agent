"""Deterministic opportunity score calculation engine."""

from __future__ import annotations

import math
from typing import Any, Dict
from src.scalp.models.scalp_candidate import ScoreComponents


class OpportunityScoreEngine:
    @staticmethod
    def calculate_score(candidate_data: Dict[str, Any], indicators: Dict[str, Any], research_data: Dict[str, Any] | None = None) -> tuple[float, ScoreComponents]:
        # Extract raw metrics
        vol_24h = float(candidate_data.get("volume_24h_usdt", 50000000.0))
        spread_bps = float(candidate_data.get("bid_ask_spread_bps", 3.0))
        vol_ratio = float(indicators.get("volume_ratio_30", 1.0))
        atr = float(indicators.get("atr14", 0.0))
        close = float(indicators.get("close", 1.0))
        atr_pct = (atr / close) * 100 if close > 0 else 1.0
        adx = float(indicators.get("adx14", 25.0))
        oi_delta = float(candidate_data.get("open_interest_delta_pct", 1.5))
        has_catalyst = bool(research_data and research_data.get("bullish_catalysts"))

        # 1. Liquidity Quality (25%): high 24h volume (>50M = 100, <5M = 20)
        liquidity = min(100.0, max(20.0, (math.log10(max(vol_24h, 100000.0)) - 6.0) * 35.0))

        # 2. Volume Anomaly (20%): volume ratio relative to 30-bar mean (1.0 = 50, 2.5+ = 100)
        vol_anomaly = min(100.0, max(20.0, vol_ratio * 40.0))

        # 3. Spread Quality (15%): low spread (1 bps = 100, 10 bps = 30)
        spread_qual = min(100.0, max(10.0, 100.0 - (spread_bps * 7.0)))

        # 4. Volatility Suitability (15%): ATR 0.5% - 3.0% is optimal for scalping
        if 0.5 <= atr_pct <= 3.5:
            vol_suitability = 90.0
        elif atr_pct > 3.5:
            vol_suitability = 70.0  # slightly high risk
        else:
            vol_suitability = 50.0  # low volatility

        # 5. Open Interest Change (10%): rising OI confirms momentum
        oi_score = min(100.0, max(30.0, 50.0 + (oi_delta * 10.0)))

        # 6. Market Structure Quality (10%): ADX strength & trend alignment
        structure_score = min(100.0, max(30.0, adx * 2.2))

        # 7. Catalyst Context (5%): breaking news or research catalyst
        catalyst_score = 90.0 if has_catalyst else 60.0

        # Weighted sum
        total_score = (
            (liquidity * 0.25)
            + (vol_anomaly * 0.20)
            + (spread_qual * 0.15)
            + (vol_suitability * 0.15)
            + (oi_score * 0.10)
            + (structure_score * 0.10)
            + (catalyst_score * 0.05)
        )

        total_score = round(min(99.0, max(10.0, total_score)), 1)

        components = ScoreComponents(
            liquidity_quality=round(liquidity, 1),
            volume_anomaly=round(vol_anomaly, 1),
            spread_quality=round(spread_qual, 1),
            volatility_suitability=round(vol_suitability, 1),
            open_interest_change=round(oi_score, 1),
            market_structure_quality=round(structure_score, 1),
            catalyst_context=round(catalyst_score, 1),
            raw_metrics={
                "volume_24h_usdt": vol_24h,
                "bid_ask_spread_bps": spread_bps,
                "volume_ratio_30": vol_ratio,
                "atr_pct": round(atr_pct, 2),
                "adx_14": adx,
            },
        )

        return total_score, components

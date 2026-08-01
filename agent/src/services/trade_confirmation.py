"""Persistent Bitget trade proposal and confirmation records."""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from src.config.paths import get_runtime_root

_STORE_PATH = get_runtime_root() / "bitget" / "trade-confirmations.json"
_CONFIRM_WORDS = {"yes", "confirm", "confirmed", "execute", "place", "approved", "approve"}


def create_trade_proposal(
    *,
    prompt: str,
    intent: dict[str, Any],
    signal: dict[str, Any],
    risk: dict[str, Any],
) -> dict[str, Any]:
    """Persist and return a trade proposal that still requires confirmation."""
    proposal_id = f"btg_{uuid.uuid4().hex[:16]}"
    now = _now_ms()
    symbol = signal.get("symbol") if isinstance(signal.get("symbol"), dict) else {}
    proposal = {
        "proposal_id": proposal_id,
        "status": "proposed",
        "created_at": now,
        "updated_at": now,
        "expires_at": now + 30 * 60 * 1000,
        "prompt": prompt,
        "symbol": symbol,
        "category": intent.get("category"),
        "timeframe": intent.get("timeframe"),
        "direction": risk.get("direction") or signal.get("direction"),
        "confidence": signal.get("confidence"),
        "reasoning": signal.get("reasoning") or [],
        "entry": risk.get("entry"),
        "stop_loss": risk.get("stop_loss"),
        "take_profit": risk.get("take_profit"),
        "risk_reward": risk.get("risk_reward"),
        "expected_duration": risk.get("expected_duration"),
        "suggested_leverage": risk.get("suggested_leverage"),
        "suggested_margin_usdt": risk.get("suggested_margin_usdt"),
        "suggested_notional_usdt": risk.get("suggested_notional_usdt"),
        "suggested_qty": risk.get("suggested_qty"),
        "margin_mode": risk.get("margin_mode"),
        "warnings": risk.get("warnings") or [],
        "signal": signal,
        "risk": risk,
    }
    store = _read_store()
    store[proposal_id] = proposal
    _write_store(store)
    return proposal


def get_trade_proposal(proposal_id: str) -> dict[str, Any] | None:
    return _read_store().get(str(proposal_id or "").strip())


def mark_trade_executed(proposal_id: str, execution: dict[str, Any]) -> dict[str, Any]:
    store = _read_store()
    proposal = store.get(proposal_id)
    if proposal is None:
        raise KeyError(f"unknown trade proposal: {proposal_id}")
    proposal["status"] = "executed" if str(execution.get("status", "")).lower() == "ok" else "execution_error"
    proposal["execution"] = execution
    proposal["updated_at"] = _now_ms()
    store[proposal_id] = proposal
    _write_store(store)
    return proposal


def explicit_confirmation(text: str) -> bool:
    normalized = {token.strip().casefold() for token in str(text or "").replace(",", " ").split()}
    return bool(normalized & _CONFIRM_WORDS)


def proposal_is_expired(proposal: dict[str, Any]) -> bool:
    return int(proposal.get("expires_at") or 0) < _now_ms()


def _read_store() -> dict[str, dict[str, Any]]:
    if not _STORE_PATH.exists():
        return {}
    try:
        payload = json.loads(_STORE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_store(store: dict[str, dict[str, Any]]) -> None:
    _STORE_PATH.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = _STORE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(store, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        tmp.chmod(0o600)
    except OSError:
        pass
    os.replace(tmp, _STORE_PATH)


def _now_ms() -> int:
    return int(time.time() * 1000)


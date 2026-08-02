import sys, json
from src.services.bitget_mcp import call_bitget_tool
res = call_bitget_tool("order", {
    "action": "place",
    "category": "USDT-FUTURES",
    "symbol": "BTCUSDT",
    "side": "sell",
    "posSide": "long",
    "qty": "0.001",
    "orderType": "market",
    "reduceOnly": "yes",
    "confirm": True
})
print(json.dumps(res, indent=2))

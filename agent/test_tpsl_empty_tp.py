import sys, json
from src.services.bitget_mcp import call_bitget_tool
res = call_bitget_tool("strategy_order", {
    "action": "place",
    "category": "USDT-FUTURES",
    "symbol": "BTCUSDT",
    "posSide": "long",
    "planType": "position_tpsl",
    "tpslMode": "full",
    "stopLoss": "62740.1",
    "takeProfit": "",
    "marginCoin": "USDT",
    "marginMode": "isolated"
})
print(json.dumps(res, indent=2))

import sys, json
from src.services.bitget_mcp import call_bitget_tool
res = call_bitget_tool("strategy_order", {
    "action": "place",
    "category": "USDT-FUTURES",
    "symbol": "BTCUSDT",
    "posSide": "long",
    "type": "tpsl",
    "tpslMode": "full",
    "tpTriggerBy": "market",
    "slTriggerBy": "market",
    "tpOrderType": "market",
    "slOrderType": "market",
    "stopLoss": "62740.1",
    "planType": "position_tpsl"
})
print(json.dumps(res, indent=2))

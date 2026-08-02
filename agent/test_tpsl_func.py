import sys, json
from src.services.bitget_management import modify_tpsl
res = modify_tpsl(
    category="USDT-FUTURES",
    symbol="BTCUSDT",
    pos_side="long",
    stop_loss=62740.1,
    confirmation_text="I confirm this action."
)
print(json.dumps(res, indent=2))

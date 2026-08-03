import { memo } from "react";
import { Flame } from "lucide-react";

interface CoinGlassHeatmapCardProps {
  symbol: string;
}

export const CoinGlassHeatmapCard = memo(function CoinGlassHeatmapCard({ symbol }: CoinGlassHeatmapCardProps) {
  const cleanSymbol = symbol ? symbol.replace("USDT", "") : "BTC";

  return (
    <div className="p-6 rounded-2xl bg-card border-2 border-primary/30 space-y-4 shadow-md">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-primary/15 text-primary">
              <Flame className="h-5 w-5 text-amber-500 animate-pulse" />
            </div>
            <h3 className="font-extrabold text-base">🔥 CoinGlass Crypto Futures Liquidation Heatmap</h3>
            <span className="px-2.5 py-0.5 text-[10px] font-bold rounded-full bg-amber-500/15 text-amber-400 border border-amber-500/30">
              LIVE LIQUIDITY CLUSTERS
            </span>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Real-time leverage liquidation intensity map across major exchanges. High-density clusters indicate key liquidity sweep target zones.
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs font-semibold">
          <span className="text-muted-foreground font-mono">Market Feed:</span>
          <span className="px-3 py-1 rounded-lg bg-primary/20 text-primary border border-primary/40 font-bold">
            {cleanSymbol}/USDT Futures
          </span>
        </div>
      </div>

      <div className="relative h-[520px] w-full rounded-2xl border border-zinc-800/90 overflow-hidden shadow-inner bg-zinc-950">
        <iframe
          title={`CoinGlass Liquidation Heatmap for ${cleanSymbol}`}
          src={`https://www.coinglass.com/pro/futures/LiquidationHeatMap?symbol=${cleanSymbol}`}
          className="absolute -left-[280px] -top-[560px] w-[calc(100%+290px)] h-[calc(100%+600px)] border-0 pointer-events-auto"
          loading="lazy"
        />
      </div>
    </div>
  );
});

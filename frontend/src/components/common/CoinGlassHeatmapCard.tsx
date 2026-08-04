import { memo, useState } from "react";
import { Flame, ExternalLink, Play } from "lucide-react";

interface CoinGlassHeatmapCardProps {
  symbol: string;
}

export const CoinGlassHeatmapCard = memo(function CoinGlassHeatmapCard({ symbol }: CoinGlassHeatmapCardProps) {
  const [isLoaded, setIsLoaded] = useState(false);
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

      <div className="relative h-[520px] w-full rounded-2xl border border-zinc-800/90 overflow-hidden shadow-inner bg-zinc-950 flex flex-col items-center justify-center">
        {!isLoaded ? (
          <div className="flex flex-col items-center gap-4 p-6 text-center max-w-sm">
            <div className="p-4 rounded-full bg-amber-500/10 border border-amber-500/20">
              <Flame className="h-8 w-8 text-amber-500" />
            </div>
            <h4 className="font-bold text-foreground">Live Liquidity Heatmap</h4>
            <p className="text-xs text-muted-foreground">
              Loading the live Coinglass iframe can be resource-intensive and may cause browser freezing. Click below to load it on demand.
            </p>
            <button
              onClick={() => setIsLoaded(true)}
              className="mt-2 px-6 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-600 text-zinc-950 font-extrabold text-sm transition-all shadow-md flex items-center gap-2"
            >
              <Play className="h-4 w-4" fill="currentColor" />
              Load Interactive Heatmap
            </button>
            <a 
              href={`https://www.coinglass.com/pro/futures/LiquidationHeatMap?symbol=${cleanSymbol}`}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-amber-500/80 hover:text-amber-500 underline underline-offset-2 flex items-center gap-1 mt-2"
            >
              Open in new tab <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        ) : (
          <iframe
            title={`CoinGlass Liquidation Heatmap for ${cleanSymbol}`}
            src={`https://www.coinglass.com/pro/futures/LiquidationHeatMap?symbol=${cleanSymbol}`}
            className="absolute -left-[280px] -top-[560px] w-[calc(100%+290px)] h-[calc(100%+600px)] border-0 pointer-events-auto"
            loading="lazy"
          />
        )}
      </div>
    </div>
  );
});

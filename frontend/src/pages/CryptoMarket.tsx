import { useEffect, useMemo, useRef, useState } from "react";
import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  createChart,
  type CandlestickData,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { Activity, Loader2, RefreshCw, Wifi, WifiOff } from "lucide-react";
import { toast } from "sonner";
import { api, type CryptoCandle } from "@/lib/api";

type Candle = CandlestickData<UTCTimestamp>;

const SYMBOLS = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "DOGE-USDT"];
const INTERVALS = [
  { value: "1m", label: "1m", seconds: 60 },
  { value: "5m", label: "5m", seconds: 300 },
  { value: "15m", label: "15m", seconds: 900 },
  { value: "1h", label: "1h", seconds: 3600 },
  { value: "6h", label: "6h", seconds: 21600 },
  { value: "1d", label: "1d", seconds: 86400 },
];

function toProductId(symbol: string): string {
  const normalized = symbol.trim().toUpperCase().replace("/", "-");
  return normalized.endsWith("-USDT")
    ? `${normalized.slice(0, -5)}-USD`
    : normalized;
}

function toTimestamp(value: string): UTCTimestamp {
  const parsed = Date.parse(value);
  if (Number.isFinite(parsed)) {
    return Math.floor(parsed / 1000) as UTCTimestamp;
  }
  const numeric = Number(value);
  return Math.floor(numeric > 1_000_000_000_000 ? numeric / 1000 : numeric) as UTCTimestamp;
}

function normalizeBar(bar: CryptoCandle): Candle | null {
  const candle = {
    time: toTimestamp(bar.time),
    open: Number(bar.open),
    high: Number(bar.high),
    low: Number(bar.low),
    close: Number(bar.close),
  };
  return Object.values(candle).every(Number.isFinite) ? candle : null;
}

function bucketTick(time: string, intervalSeconds: number): UTCTimestamp {
  const seconds = toTimestamp(time);
  return (Math.floor(seconds / intervalSeconds) * intervalSeconds) as UTCTimestamp;
}

export function CryptoMarket() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const latestCandleRef = useRef<Candle | null>(null);
  const [symbol, setSymbol] = useState("BTC-USDT");
  const [interval, setInterval] = useState("5m");
  const [bars, setBars] = useState<Candle[]>([]);
  const [loading, setLoading] = useState(true);
  const [wsState, setWsState] = useState<"connecting" | "live" | "offline">("connecting");
  const [lastPrice, setLastPrice] = useState<number | null>(null);
  const [lastTickAt, setLastTickAt] = useState<string>("");

  const intervalSpec = useMemo(
    () => INTERVALS.find((item) => item.value === interval) ?? INTERVALS[1],
    [interval],
  );
  const productId = useMemo(() => toProductId(symbol), [symbol]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = createChart(container, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "hsl(var(--muted-foreground))",
      },
      grid: {
        vertLines: { color: "hsl(var(--border))" },
        horzLines: { color: "hsl(var(--border))" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "hsl(var(--border))" },
      timeScale: {
        borderColor: "hsl(var(--border))",
        timeVisible: true,
        secondsVisible: false,
      },
    });
    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#16a34a",
      downColor: "#dc2626",
      borderUpColor: "#16a34a",
      borderDownColor: "#dc2626",
      wickUpColor: "#16a34a",
      wickDownColor: "#dc2626",
    });

    chartRef.current = chart;
    seriesRef.current = series;

    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!seriesRef.current) return;
    seriesRef.current.setData(bars);
    latestCandleRef.current = bars.length ? bars[bars.length - 1] : null;
    if (bars.length) chartRef.current?.timeScale().fitContent();
  }, [bars]);

  const loadHistory = async () => {
    setLoading(true);
    try {
      const response = await api.getCryptoCandles({ symbol, interval, lookback: 300 });
      const nextBars = response.bars
        .map(normalizeBar)
        .filter((bar): bar is Candle => Boolean(bar))
        .sort((a, b) => Number(a.time) - Number(b.time));
      setBars(nextBars);
      const latest = nextBars.length ? nextBars[nextBars.length - 1] : null;
      setLastPrice(latest?.close ?? null);
      latestCandleRef.current = latest;
    } catch (error) {
      toast.error(`Coinbase candles failed: ${error instanceof Error ? error.message : "unknown error"}`);
      setBars([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadHistory();
  }, [symbol, interval]);

  useEffect(() => {
    setWsState("connecting");
    const socket = new WebSocket("wss://ws-feed.exchange.coinbase.com");

    socket.addEventListener("open", () => {
      socket.send(JSON.stringify({
        type: "subscribe",
        product_ids: [productId],
        channels: ["ticker"],
      }));
      setWsState("live");
    });

    socket.addEventListener("message", (event) => {
      let payload: { type?: string; product_id?: string; price?: string; time?: string } = {};
      try {
        payload = JSON.parse(String(event.data));
      } catch {
        return;
      }
      if (payload.type !== "ticker" || payload.product_id !== productId || !payload.price || !payload.time) {
        return;
      }

      const price = Number(payload.price);
      if (!Number.isFinite(price)) return;

      const time = bucketTick(payload.time, intervalSpec.seconds);
      const current = latestCandleRef.current;
      const next: Candle = current && Number(current.time) === Number(time)
        ? {
            ...current,
            high: Math.max(current.high, price),
            low: Math.min(current.low, price),
            close: price,
          }
        : { time, open: price, high: price, low: price, close: price };

      latestCandleRef.current = next;
      seriesRef.current?.update(next);
      setLastPrice(price);
      setLastTickAt(new Date(payload.time).toLocaleTimeString());
    });

    socket.addEventListener("close", () => setWsState("offline"));
    socket.addEventListener("error", () => setWsState("offline"));

    return () => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({
          type: "unsubscribe",
          product_ids: [productId],
          channels: ["ticker"],
        }));
      }
      socket.close();
    };
  }, [productId, intervalSpec.seconds]);

  return (
    <main className="min-h-screen bg-background p-4 md:p-6" id="main">
      <div className="mx-auto flex max-w-7xl flex-col gap-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Activity className="h-4 w-4 text-primary" />
              Coinbase live market data
            </div>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight">Crypto Markets</h1>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <select
              value={symbol}
              onChange={(event) => setSymbol(event.target.value)}
              className="h-9 rounded-md border bg-background px-3 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
            >
              {SYMBOLS.map((item) => (
                <option key={item} value={item}>{item}</option>
              ))}
            </select>
            <div className="flex h-9 rounded-md border bg-background p-0.5">
              {INTERVALS.map((item) => (
                <button
                  key={item.value}
                  type="button"
                  onClick={() => setInterval(item.value)}
                  className={`min-w-10 rounded px-2 text-xs font-medium transition ${
                    item.value === interval
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => void loadHistory()}
              disabled={loading}
              className="inline-flex h-9 items-center justify-center gap-2 rounded-md border px-3 text-sm text-muted-foreground transition hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-60"
              title="Refresh Coinbase history"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              <span className="hidden sm:inline">Refresh</span>
            </button>
          </div>
        </div>

        <section className="grid gap-3 md:grid-cols-4">
          <div className="rounded-md border bg-card px-4 py-3">
            <div className="text-xs text-muted-foreground">Product</div>
            <div className="mt-1 text-sm font-medium">{productId}</div>
          </div>
          <div className="rounded-md border bg-card px-4 py-3">
            <div className="text-xs text-muted-foreground">Last price</div>
            <div className="mt-1 text-sm font-medium">
              {lastPrice === null ? "Loading" : `$${lastPrice.toLocaleString(undefined, { maximumFractionDigits: 2 })}`}
            </div>
          </div>
          <div className="rounded-md border bg-card px-4 py-3">
            <div className="text-xs text-muted-foreground">Feed</div>
            <div className="mt-1 flex items-center gap-2 text-sm font-medium">
              {wsState === "live" ? <Wifi className="h-4 w-4 text-success" /> : <WifiOff className="h-4 w-4 text-warning" />}
              {wsState === "connecting" ? "Connecting" : wsState === "live" ? "Live" : "Offline"}
            </div>
          </div>
          <div className="rounded-md border bg-card px-4 py-3">
            <div className="text-xs text-muted-foreground">Last tick</div>
            <div className="mt-1 text-sm font-medium">{lastTickAt || "Waiting"}</div>
          </div>
        </section>

        <section className="relative min-h-[560px] rounded-md border bg-card p-3">
          <div ref={containerRef} className="h-[540px] w-full" />
          {loading && !bars.length ? (
            <div className="absolute inset-3 flex items-center justify-center bg-card/80 text-sm text-muted-foreground">
              <Loader2 className="me-2 h-4 w-4 animate-spin" />
              Loading Coinbase candles
            </div>
          ) : null}
        </section>
      </div>
    </main>
  );
}

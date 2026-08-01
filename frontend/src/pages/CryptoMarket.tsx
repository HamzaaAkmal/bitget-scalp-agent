import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  HistogramSeries,
  LineStyle,
  LineSeries,
  createChart,
  type CandlestickData,
  type HistogramData,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type UTCTimestamp,
} from "lightweight-charts";
import {
  Activity,
  AlertTriangle,
  Bot,
  CheckCircle2,
  Loader2,
  RefreshCw,
  Send,
  ShieldCheck,
  Wifi,
  WifiOff,
} from "lucide-react";
import { toast } from "sonner";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { api, type BitgetMcpEnvelope, type BitgetTradeProposal, type CryptoCandle } from "@/lib/api";

type Candle = CandlestickData<UTCTimestamp>;
type CandleWithVolume = Candle & { volume: number };
type LinePoint = LineData<UTCTimestamp>;
type HistogramPoint = HistogramData<UTCTimestamp>;
type WsState = "connecting" | "live" | "offline";

const SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "PEPEUSDT"];
const CATEGORIES = [
  { value: "USDT-FUTURES", label: "Futures", instType: "usdt-futures" },
  { value: "SPOT", label: "Spot", instType: "spot" },
] as const;
const INTERVALS = [
  { value: "1m", label: "1m", seconds: 60 },
  { value: "3m", label: "3m", seconds: 180 },
  { value: "5m", label: "5m", seconds: 300 },
  { value: "15m", label: "15m", seconds: 900 },
  { value: "30m", label: "30m", seconds: 1800 },
  { value: "1H", label: "1H", seconds: 3600 },
  { value: "4H", label: "4H", seconds: 14400 },
  { value: "1D", label: "1D", seconds: 86400 },
  { value: "1W", label: "1W", seconds: 604800 },
];

function normalizeSymbol(value: string): string {
  const compact = value.trim().toUpperCase().replace(/[-/]/g, "");
  if (compact.endsWith("USD") && !compact.endsWith("USDT")) return `${compact.slice(0, -3)}USDT`;
  return compact || "BTCUSDT";
}

function toTimestamp(value: string | number): UTCTimestamp {
  const numeric = Number(value);
  if (Number.isFinite(numeric)) {
    return Math.floor(numeric > 1_000_000_000_000 ? numeric / 1000 : numeric) as UTCTimestamp;
  }
  const parsed = Date.parse(String(value));
  return Math.floor(parsed / 1000) as UTCTimestamp;
}

function normalizeBar(bar: CryptoCandle): CandleWithVolume | null {
  const candle = {
    time: toTimestamp(bar.time),
    open: Number(bar.open),
    high: Number(bar.high),
    low: Number(bar.low),
    close: Number(bar.close),
    volume: Number(bar.volume ?? 0),
  };
  return Object.values(candle).every(Number.isFinite) ? candle : null;
}

function bucketTick(timeMs: number, intervalSeconds: number): UTCTimestamp {
  const seconds = Math.floor(timeMs / 1000);
  return (Math.floor(seconds / intervalSeconds) * intervalSeconds) as UTCTimestamp;
}

function payloadRows(envelope: BitgetMcpEnvelope): Record<string, unknown>[] {
  const data = (envelope.structured_content as { data?: unknown } | undefined)?.data
    ?? (envelope.data as { data?: unknown } | undefined)?.data;
  return Array.isArray(data) ? data.filter((row): row is Record<string, unknown> => Boolean(row) && typeof row === "object") : [];
}

function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "Pending";
  return value >= 1
    ? value.toLocaleString(undefined, { maximumFractionDigits: 4 })
    : value.toLocaleString(undefined, { maximumFractionDigits: 8 });
}

function buildIndicators(bars: CandleWithVolume[]): {
  ema20: LinePoint[];
  ema50: LinePoint[];
  vwap: LinePoint[];
  volume: HistogramPoint[];
  rsi: LinePoint[];
  macd: LinePoint[];
  macdSignal: LinePoint[];
  macdHistogram: HistogramPoint[];
} {
  const closes = bars.map((bar) => bar.close);
  const ema12 = emaSeries(closes, 12);
  const ema26 = emaSeries(closes, 26);
  const macdValues = ema12.map((value, index) => value - ema26[index]);
  const signalValues = emaSeries(macdValues, 9);

  return {
    ema20: toLinePoints(bars, emaSeries(closes, 20)),
    ema50: toLinePoints(bars, emaSeries(closes, 50)),
    vwap: vwapPoints(bars),
    volume: bars.map((bar) => ({
      time: bar.time,
      value: bar.volume,
      color: bar.close >= bar.open ? "rgba(22, 163, 74, 0.45)" : "rgba(220, 38, 38, 0.45)",
    })),
    rsi: rsiPoints(bars, 14),
    macd: toLinePoints(bars, macdValues),
    macdSignal: toLinePoints(bars, signalValues),
    macdHistogram: macdValues.map((value, index) => {
      const histogram = value - signalValues[index];
      return {
        time: bars[index].time,
        value: histogram,
        color: histogram >= 0 ? "rgba(8, 145, 178, 0.55)" : "rgba(225, 29, 72, 0.55)",
      };
    }),
  };
}

function toLinePoints(bars: CandleWithVolume[], values: number[]): LinePoint[] {
  return values
    .map((value, index) => ({ time: bars[index]?.time, value }))
    .filter((point): point is LinePoint => point.time !== undefined && Number.isFinite(point.value));
}

function emaSeries(values: number[], period: number): number[] {
  if (!values.length) return [];
  const alpha = 2 / (period + 1);
  const result: number[] = [];
  let ema = values[0];
  for (const value of values) {
    ema = value * alpha + ema * (1 - alpha);
    result.push(ema);
  }
  return result;
}

function vwapPoints(bars: CandleWithVolume[]): LinePoint[] {
  let cumulativePriceVolume = 0;
  let cumulativeVolume = 0;
  return bars.map((bar) => {
    const typical = (bar.high + bar.low + bar.close) / 3;
    const volume = Math.max(bar.volume, 0);
    cumulativePriceVolume += typical * volume;
    cumulativeVolume += volume;
    return {
      time: bar.time,
      value: cumulativeVolume > 0 ? cumulativePriceVolume / cumulativeVolume : bar.close,
    };
  });
}

function rsiPoints(bars: CandleWithVolume[], period: number): LinePoint[] {
  if (bars.length <= period) return [];
  const points: LinePoint[] = [];
  for (let index = period; index < bars.length; index += 1) {
    const window = bars.slice(index - period, index + 1);
    let gains = 0;
    let losses = 0;
    for (let inner = 1; inner < window.length; inner += 1) {
      const delta = window[inner].close - window[inner - 1].close;
      if (delta >= 0) gains += delta;
      else losses += Math.abs(delta);
    }
    const averageGain = gains / period;
    const averageLoss = losses / period;
    const value = averageLoss === 0 ? 100 : 100 - (100 / (1 + averageGain / averageLoss));
    points.push({ time: bars[index].time, value });
  }
  return points;
}

export function CryptoMarket() {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const ema20Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const ema50Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const vwapRef = useRef<ISeriesApi<"Line"> | null>(null);
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const rsiRef = useRef<ISeriesApi<"Line"> | null>(null);
  const macdRef = useRef<ISeriesApi<"Line"> | null>(null);
  const macdSignalRef = useRef<ISeriesApi<"Line"> | null>(null);
  const macdHistogramRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const latestCandleRef = useRef<CandleWithVolume | null>(null);
  const [category, setCategory] = useState<(typeof CATEGORIES)[number]["value"]>("USDT-FUTURES");
  const [symbolInput, setSymbolInput] = useState("BTCUSDT");
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [interval, setInterval] = useState("5m");
  const [bars, setBars] = useState<CandleWithVolume[]>([]);
  const [loading, setLoading] = useState(true);
  const [wsState, setWsState] = useState<WsState>("connecting");
  const [lastPrice, setLastPrice] = useState<number | null>(null);
  const [lastTickAt, setLastTickAt] = useState("");
  const [statusText, setStatusText] = useState("Checking");
  const [accountRows, setAccountRows] = useState<Record<string, unknown>[]>([]);
  const [positionRows, setPositionRows] = useState<Record<string, unknown>[]>([]);
  const [orderRows, setOrderRows] = useState<Record<string, unknown>[]>([]);
  const [prompt, setPrompt] = useState("Research Bitcoin on the 15 minute futures chart with 3x leverage.");
  const [proposal, setProposal] = useState<BitgetTradeProposal | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [executionLoading, setExecutionLoading] = useState(false);
  const [executionResult, setExecutionResult] = useState<string>("");
  const [confirmOpen, setConfirmOpen] = useState(false);

  const intervalSpec = useMemo(
    () => INTERVALS.find((item) => item.value === interval) ?? INTERVALS[2],
    [interval],
  );
  const categorySpec = useMemo(
    () => CATEGORIES.find((item) => item.value === category) ?? CATEGORIES[0],
    [category],
  );

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
    const ema20 = chart.addSeries(LineSeries, {
      color: "#2563eb",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      title: "EMA20",
    });
    const ema50 = chart.addSeries(LineSeries, {
      color: "#f59e0b",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      title: "EMA50",
    });
    const vwap = chart.addSeries(LineSeries, {
      color: "#64748b",
      lineWidth: 1,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: false,
      lastValueVisible: false,
      title: "VWAP",
    });
    const volume = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceLineVisible: false,
      lastValueVisible: false,
      title: "Volume",
    }, 1);
    const rsi = chart.addSeries(LineSeries, {
      color: "#7c3aed",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      title: "RSI",
    }, 2);
    const macdHistogram = chart.addSeries(HistogramSeries, {
      priceLineVisible: false,
      lastValueVisible: false,
      title: "MACD",
    }, 3);
    const macd = chart.addSeries(LineSeries, {
      color: "#0891b2",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      title: "MACD",
    }, 3);
    const macdSignal = chart.addSeries(LineSeries, {
      color: "#e11d48",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      title: "Signal",
    }, 3);

    chart.panes()[0]?.setStretchFactor(6);
    chart.panes()[1]?.setStretchFactor(1);
    chart.panes()[2]?.setStretchFactor(1);
    chart.panes()[3]?.setStretchFactor(1);

    chartRef.current = chart;
    seriesRef.current = series;
    ema20Ref.current = ema20;
    ema50Ref.current = ema50;
    vwapRef.current = vwap;
    volumeRef.current = volume;
    rsiRef.current = rsi;
    macdRef.current = macd;
    macdSignalRef.current = macdSignal;
    macdHistogramRef.current = macdHistogram;

    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      ema20Ref.current = null;
      ema50Ref.current = null;
      vwapRef.current = null;
      volumeRef.current = null;
      rsiRef.current = null;
      macdRef.current = null;
      macdSignalRef.current = null;
      macdHistogramRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!seriesRef.current) return;
    seriesRef.current.setData(bars);
    const indicators = buildIndicators(bars);
    ema20Ref.current?.setData(indicators.ema20);
    ema50Ref.current?.setData(indicators.ema50);
    vwapRef.current?.setData(indicators.vwap);
    volumeRef.current?.setData(indicators.volume);
    rsiRef.current?.setData(indicators.rsi);
    macdRef.current?.setData(indicators.macd);
    macdSignalRef.current?.setData(indicators.macdSignal);
    macdHistogramRef.current?.setData(indicators.macdHistogram);
    latestCandleRef.current = bars.length ? bars[bars.length - 1] : null;
    if (bars.length) chartRef.current?.timeScale().fitContent();
  }, [bars]);

  const loadHistory = async () => {
    setLoading(true);
    try {
      const response = await api.getBitgetCandles({ symbol, category, interval, lookback: 300 });
      const nextBars = response.bars
        .map(normalizeBar)
        .filter((bar): bar is CandleWithVolume => Boolean(bar))
        .sort((a, b) => Number(a.time) - Number(b.time));
      setBars(nextBars);
      const latest = nextBars.length ? nextBars[nextBars.length - 1] : null;
      setLastPrice(latest?.close ?? null);
      latestCandleRef.current = latest;
    } catch (error) {
      toast.error(`Bitget candles failed: ${error instanceof Error ? error.message : "unknown error"}`);
      setBars([]);
    } finally {
      setLoading(false);
    }
  };

  const loadPrivateState = async () => {
    try {
      const [status, account, positions, orders] = await Promise.all([
        api.getBitgetStatus(),
        api.getBitgetAccount({ category, symbol }),
        api.getBitgetPositions({ category, symbol }),
        api.getBitgetOrders({ category, symbol }),
      ]);
      setStatusText(status.mcp_available ? (status.credentials_configured ? "MCP ready" : "Public only") : "MCP offline");
      setAccountRows(payloadRows(account).slice(0, 4));
      setPositionRows(payloadRows(positions).slice(0, 6));
      setOrderRows(payloadRows(orders).slice(0, 6));
    } catch {
      setStatusText("Private reads unavailable");
      setAccountRows([]);
      setPositionRows([]);
      setOrderRows([]);
    }
  };

  useEffect(() => {
    void loadHistory();
  }, [symbol, category, interval]);

  useEffect(() => {
    void loadPrivateState();
    const timer = window.setInterval(() => void loadPrivateState(), 20_000);
    return () => window.clearInterval(timer);
  }, [symbol, category]);

  useEffect(() => {
    setWsState("connecting");
    const socket = new WebSocket("wss://ws.bitget.com/v3/ws/public");
    const arg = { instType: categorySpec.instType, topic: "ticker", symbol };

    socket.addEventListener("open", () => {
      socket.send(JSON.stringify({ op: "subscribe", args: [arg] }));
    });

    socket.addEventListener("message", (event) => {
      let payload: { event?: string; data?: Array<{ lastPrice?: string }>; ts?: number } = {};
      try {
        payload = JSON.parse(String(event.data));
      } catch {
        return;
      }
      if (payload.event === "subscribe") {
        setWsState("live");
        return;
      }
      const row = payload.data?.[0];
      const price = Number(row?.lastPrice);
      const ts = Number(payload.ts || Date.now());
      if (!Number.isFinite(price)) return;

      const time = bucketTick(ts, intervalSpec.seconds);
      const current = latestCandleRef.current;
      const next: CandleWithVolume = current && Number(current.time) === Number(time)
        ? { ...current, high: Math.max(current.high, price), low: Math.min(current.low, price), close: price }
        : { time, open: price, high: price, low: price, close: price, volume: 0 };

      latestCandleRef.current = next;
      seriesRef.current?.update(next);
      setLastPrice(price);
      setLastTickAt(new Date(ts).toLocaleTimeString());
    });

    socket.addEventListener("close", () => setWsState("offline"));
    socket.addEventListener("error", () => setWsState("offline"));

    return () => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ op: "unsubscribe", args: [arg] }));
      }
      socket.close();
    };
  }, [symbol, categorySpec.instType, intervalSpec.seconds]);

  const applySymbol = () => {
    const next = normalizeSymbol(symbolInput);
    setSymbolInput(next);
    setSymbol(next);
  };

  const analyzePrompt = async () => {
    setAnalysisLoading(true);
    setExecutionResult("");
    try {
      const response = await api.createBitgetTradeProposal({ prompt, category, symbol });
      if (response.status !== "ok" || !response.proposal) {
        toast.error(response.message || "Bitget proposal needs clarification");
        setProposal(null);
        return;
      }
      setProposal(response.proposal);
      if (response.proposal.symbol?.symbol) {
        setSymbolInput(response.proposal.symbol.symbol);
        setSymbol(response.proposal.symbol.symbol);
      }
      toast.success("Trade proposal ready");
    } catch (error) {
      toast.error(`Bitget proposal failed: ${error instanceof Error ? error.message : "unknown error"}`);
      setProposal(null);
    } finally {
      setAnalysisLoading(false);
    }
  };

  const executeProposal = async () => {
    if (!proposal) return;
    setExecutionLoading(true);
    try {
      const response = await api.executeBitgetTradeProposal(proposal.proposal_id, {
        confirmation_text: "confirm execute",
      });
      if (response.status !== "ok") {
        setExecutionResult(response.error || "Execution rejected");
        toast.error(response.error || "Execution rejected");
        return;
      }
      setExecutionResult(`Order submitted for ${response.symbol} ${response.side} ${response.qty}`);
      toast.success("Bitget order submitted");
      void loadPrivateState();
    } catch (error) {
      const message = error instanceof Error ? error.message : "unknown error";
      setExecutionResult(message);
      toast.error(`Execution failed: ${message}`);
    } finally {
      setExecutionLoading(false);
      setConfirmOpen(false);
    }
  };

  return (
    <main className="min-h-screen bg-background p-4 md:p-6" id="main">
      <div className="mx-auto flex max-w-7xl flex-col gap-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Activity className="h-4 w-4 text-primary" />
              Official Bitget MCP
            </div>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight">Crypto Markets</h1>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="flex h-9 rounded-md border bg-background p-0.5">
              {CATEGORIES.map((item) => (
                <button
                  key={item.value}
                  type="button"
                  onClick={() => setCategory(item.value)}
                  className={`min-w-20 rounded px-3 text-xs font-medium transition ${
                    item.value === category
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
            <input
              list="bitget-symbols"
              value={symbolInput}
              onChange={(event) => setSymbolInput(event.target.value)}
              onBlur={applySymbol}
              onKeyDown={(event) => {
                if (event.key === "Enter") applySymbol();
              }}
              className="h-9 w-32 rounded-md border bg-background px-3 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
            />
            <datalist id="bitget-symbols">
              {SYMBOLS.map((item) => <option key={item} value={item} />)}
            </datalist>
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
              title="Refresh Bitget history"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              <span className="hidden sm:inline">Refresh</span>
            </button>
          </div>
        </div>

        <section className="grid gap-3 md:grid-cols-4">
          <Metric label="Symbol" value={`${symbol} ${category === "SPOT" ? "Spot" : "Perp"}`} />
          <Metric label="Last price" value={lastPrice === null ? "Loading" : `$${formatPrice(lastPrice)}`} />
          <Metric
            label="Feed"
            value={wsState === "connecting" ? "Connecting" : wsState === "live" ? `Live ${lastTickAt || ""}` : "Offline"}
            icon={wsState === "live" ? <Wifi className="h-4 w-4 text-success" /> : <WifiOff className="h-4 w-4 text-warning" />}
          />
          <Metric label="MCP" value={statusText} icon={<ShieldCheck className="h-4 w-4 text-info" />} />
        </section>

        <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_380px]">
          <div className="relative min-h-[560px] rounded-md border bg-card p-3">
            <div ref={containerRef} className="h-[540px] w-full" />
            {loading && !bars.length ? (
              <div className="absolute inset-3 flex items-center justify-center bg-card/80 text-sm text-muted-foreground">
                <Loader2 className="me-2 h-4 w-4 animate-spin" />
                Loading Bitget candles
              </div>
            ) : null}
          </div>

          <aside className="flex flex-col gap-4">
            <section className="rounded-md border bg-card p-4">
              <div className="flex items-center gap-2 text-sm font-semibold">
                <Bot className="h-4 w-4 text-primary" />
                Trade Proposal
              </div>
              <textarea
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                rows={5}
                className="mt-3 w-full resize-none rounded-md border bg-background p-3 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
              />
              <button
                type="button"
                onClick={() => void analyzePrompt()}
                disabled={analysisLoading}
                className="mt-3 inline-flex h-9 w-full items-center justify-center gap-2 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {analysisLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                Analyze
              </button>
            </section>

            {proposal ? (
              <ProposalCard
                proposal={proposal}
                executionResult={executionResult}
                executionLoading={executionLoading}
                onExecute={() => setConfirmOpen(true)}
              />
            ) : (
              <section className="rounded-md border border-dashed bg-card p-4 text-sm text-muted-foreground">
                No active proposal
              </section>
            )}
          </aside>
        </section>

        <section className="grid gap-4 lg:grid-cols-3">
          <DataPanel title="Account Snapshot" rows={accountRows} empty="No private account snapshot" />
          <DataPanel title="Live Positions" rows={positionRows} empty="No open futures positions" />
          <DataPanel title="Open Orders" rows={orderRows} empty="No open orders" />
        </section>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        title="Execute Bitget Trade"
        description="This sends the confirmed proposal to the official Bitget MCP server."
        confirmLabel={executionLoading ? "Executing" : "Execute"}
        cancelLabel="Cancel"
        tone="destructive"
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => void executeProposal()}
      >
        {proposal ? (
          <div className="space-y-1 rounded-md border bg-muted/30 p-3 text-xs">
            <div className="font-medium">{proposal.direction} {proposal.symbol?.symbol}</div>
            <div>Qty {proposal.suggested_qty ?? "Pending"} · {proposal.suggested_leverage ?? 1}x · {proposal.margin_mode}</div>
            <div>SL {formatPrice(proposal.stop_loss)} · TP {formatPrice(proposal.take_profit)}</div>
          </div>
        ) : null}
      </ConfirmDialog>
    </main>
  );
}

function Metric({ label, value, icon }: { label: string; value: string; icon?: ReactNode }) {
  return (
    <div className="rounded-md border bg-card px-4 py-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 flex items-center gap-2 text-sm font-medium">
        {icon}
        {value}
      </div>
    </div>
  );
}

function ProposalCard({
  proposal,
  executionResult,
  executionLoading,
  onExecute,
}: {
  proposal: BitgetTradeProposal;
  executionResult: string;
  executionLoading: boolean;
  onExecute: () => void;
}) {
  const canExecute = proposal.direction !== "WAIT";
  return (
    <section className="rounded-md border bg-card p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-xs text-muted-foreground">{proposal.symbol?.symbol} · {proposal.timeframe}</div>
          <div className="mt-1 text-lg font-semibold">{proposal.direction}</div>
        </div>
        <div className="rounded-md border px-3 py-2 text-center">
          <div className="text-[11px] text-muted-foreground">Confidence</div>
          <div className="text-sm font-semibold">{proposal.confidence}%</div>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
        <MiniStat label="Entry" value={formatPrice(proposal.entry)} />
        <MiniStat label="Risk/Reward" value={proposal.risk_reward ? `${proposal.risk_reward}:1` : "Pending"} />
        <MiniStat label="Stop Loss" value={formatPrice(proposal.stop_loss)} />
        <MiniStat label="Take Profit" value={formatPrice(proposal.take_profit)} />
        <MiniStat label="Leverage" value={`${proposal.suggested_leverage ?? 1}x`} />
        <MiniStat label="Margin" value={`${proposal.suggested_margin_usdt ?? 0} USDT`} />
      </div>

      <div className="mt-4 space-y-2 text-xs text-muted-foreground">
        {proposal.reasoning.slice(0, 3).map((item) => (
          <div key={item} className="flex gap-2">
            <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success" />
            <span>{item}</span>
          </div>
        ))}
        {(proposal.warnings || []).map((item) => (
          <div key={item} className="flex gap-2 text-warning">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>{item}</span>
          </div>
        ))}
      </div>

      <button
        type="button"
        onClick={onExecute}
        disabled={!canExecute || executionLoading}
        className="mt-4 inline-flex h-9 w-full items-center justify-center gap-2 rounded-md border border-destructive/40 bg-destructive px-3 text-sm font-medium text-destructive-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {executionLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
        Execute
      </button>
      {executionResult ? <div className="mt-3 text-xs text-muted-foreground">{executionResult}</div> : null}
    </section>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border bg-background px-3 py-2">
      <div className="text-[11px] text-muted-foreground">{label}</div>
      <div className="mt-1 break-words font-medium">{value}</div>
    </div>
  );
}

function DataPanel({ title, rows, empty }: { title: string; rows: Record<string, unknown>[]; empty: string }) {
  return (
    <section className="rounded-md border bg-card p-4">
      <div className="text-sm font-semibold">{title}</div>
      {rows.length ? (
        <div className="mt-3 max-h-64 overflow-auto rounded-md border">
          <table className="w-full text-left text-xs">
            <tbody>
              {rows.map((row, index) => (
                <tr key={index} className="border-b last:border-0">
                  <td className="w-28 px-3 py-2 font-medium text-muted-foreground">
                    {String(row.symbol || row.coin || row.category || row.orderId || `Row ${index + 1}`)}
                  </td>
                  <td className="px-3 py-2">
                    {Object.entries(row).slice(0, 5).map(([key, value]) => (
                      <span key={key} className="mr-3 inline-block">
                        <span className="text-muted-foreground">{key}: </span>
                        {String(value)}
                      </span>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="mt-3 rounded-md border border-dashed p-4 text-sm text-muted-foreground">{empty}</div>
      )}
    </section>
  );
}

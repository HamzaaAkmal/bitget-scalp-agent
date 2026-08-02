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
  Bell,
  Bot,
  CheckCircle2,
  Gauge,
  History,
  Layers,
  Loader2,
  RefreshCw,
  Send,
  ShieldCheck,
  Target,
  TrendingUp,
  Wifi,
  WifiOff,
} from "lucide-react";
import { toast } from "sonner";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import {
  api,
  type BitgetAlert,
  type BitgetMcpEnvelope,
  type BitgetRiskDashboard,
  type BitgetSymbolCandidate,
  type BitgetTradeProposal,
  type BitgetTrailingStopProposal,
  type CryptoCandle,
} from "@/lib/api";
import { withAuthTicket } from "@/lib/apiAuth";

type Candle = CandlestickData<UTCTimestamp>;
type CandleWithVolume = Candle & { volume: number };
type LinePoint = LineData<UTCTimestamp>;
type HistogramPoint = HistogramData<UTCTimestamp>;
type WsState = "connecting" | "live" | "offline";

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

function payloadRows(envelope: BitgetMcpEnvelope | null | undefined): Record<string, unknown>[] {
  if (!envelope) return [];
  const data = (envelope.structured_content as { data?: unknown } | undefined)?.data
    ?? (envelope.data as { data?: unknown } | undefined)?.data;
  return Array.isArray(data) ? data.filter((row): row is Record<string, unknown> => Boolean(row) && typeof row === "object") : [];
}

function rowValue(row: Record<string, unknown>, ...keys: string[]): unknown {
  for (const key of keys) {
    if (row[key] !== undefined && row[key] !== null && row[key] !== "") return row[key];
  }
  return undefined;
}

function rowNumber(row: Record<string, unknown>, ...keys: string[]): number | null {
  const value = rowValue(row, ...keys);
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function sumRows(rows: Record<string, unknown>[], ...keys: string[]): number {
  return rows.reduce((total, row) => total + (rowNumber(row, ...keys) ?? 0), 0);
}

function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "Pending";
  return value >= 1
    ? value.toLocaleString(undefined, { maximumFractionDigits: 4 })
    : value.toLocaleString(undefined, { maximumFractionDigits: 8 });
}

function formatMoney(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "Pending";
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(value);
}

function formatSignedMoney(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "Pending";
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    signDisplay: "exceptZero",
    maximumFractionDigits: 2,
  }).format(value);
}

function formatCompactNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "Pending";
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 4 }).format(value);
}

function numberFromInput(value: string): number | undefined {
  if (!value.trim()) return undefined;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : undefined;
}

function envelopeMessage(envelope: BitgetMcpEnvelope): string {
  const structured = envelope.structured_content as Record<string, unknown> | undefined;
  const data = envelope.data as Record<string, unknown> | undefined;
  const error = envelope.error ?? structured?.error ?? structured?.msg ?? structured?.message ?? data?.error ?? data?.msg ?? data?.message;
  if (error) return String(error);
  return String(envelope.status || structured?.status || data?.status || "ok");
}

function alertToneClass(severity: string): string {
  const tone = severity.toLowerCase();
  if (tone === "high" || tone === "critical") return "border-destructive/40 bg-destructive/10 text-destructive";
  if (tone === "medium" || tone === "warning") return "border-warning/40 bg-warning/10 text-warning";
  return "border-info/40 bg-info/10 text-info";
}

function bitgetPositionWsUrl(symbol: string, category: string): string {
  const q = new URLSearchParams();
  q.set("symbol", symbol);
  q.set("category", category);
  q.set("interval_ms", "5000");
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/bitget/ws/positions?${q.toString()}`;
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
  const [symbolResults, setSymbolResults] = useState<BitgetSymbolCandidate[]>([]);
  const [symbolFocused, setSymbolFocused] = useState(false);
  const [symbolSearchLoading, setSymbolSearchLoading] = useState(false);
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
  const [fillRows, setFillRows] = useState<Record<string, unknown>[]>([]);
  const [strategyRows, setStrategyRows] = useState<Record<string, unknown>[]>([]);
  const [riskDashboard, setRiskDashboard] = useState<BitgetRiskDashboard | null>(null);
  const [alerts, setAlerts] = useState<BitgetAlert[]>([]);
  const [positionStreamState, setPositionStreamState] = useState<WsState>("connecting");
  const [prompt, setPrompt] = useState("Research Bitcoin on the Bitget 15 minute futures chart with 3x leverage.");
  const [proposal, setProposal] = useState<BitgetTradeProposal | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [executionLoading, setExecutionLoading] = useState(false);
  const [executionResult, setExecutionResult] = useState<string>("");
  const [confirmOpen, setConfirmOpen] = useState(false);

  const livePnl = useMemo(
    () => sumRows(positionRows, "unrealizedPL", "upl", "pnl", "unrealizedPnl"),
    [positionRows],
  );
  const estimatedExposure = riskDashboard?.summary?.estimated_notional_usdt ?? sumRows(positionRows, "notional", "marginSize", "total");

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
      const [status, account, positions, orders, fills, strategyOrders, risk, alertPayload] = await Promise.all([
        api.getBitgetStatus(),
        api.getBitgetAccount({ category, symbol }),
        api.getBitgetPositions({ category, symbol }),
        api.getBitgetOrders({ category, symbol }),
        api.getBitgetFills({ category, symbol, limit: 30 }),
        api.getBitgetStrategyOrders({ category, symbol, limit: 30 }),
        api.getBitgetRiskDashboard({ category, symbol }),
        api.getBitgetAlerts({ category, symbol }),
      ]);
      setStatusText(status.mcp_available ? (status.credentials_configured ? "MCP ready" : "Public only") : "MCP offline");
      setAccountRows(payloadRows(account).slice(0, 4));
      setPositionRows(payloadRows(positions).slice(0, 6));
      setOrderRows(payloadRows(orders).slice(0, 6));
      setFillRows(payloadRows(fills).slice(0, 8));
      setStrategyRows(payloadRows(strategyOrders).slice(0, 8));
      setRiskDashboard(risk);
      setAlerts(alertPayload.alerts || []);
    } catch {
      setStatusText("Private reads unavailable");
      setAccountRows([]);
      setPositionRows([]);
      setOrderRows([]);
      setFillRows([]);
      setStrategyRows([]);
      setRiskDashboard(null);
      setAlerts([]);
    }
  };

  useEffect(() => {
    const query = symbolInput.trim();
    if (query.length < 2) {
      setSymbolResults([]);
      return;
    }
    const timer = window.setTimeout(() => {
      setSymbolSearchLoading(true);
      api.searchBitgetSymbols(query, category, 8)
        .then((response) => setSymbolResults(response.candidates || []))
        .catch(() => setSymbolResults([]))
        .finally(() => setSymbolSearchLoading(false));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [symbolInput, category]);

  useEffect(() => {
    void loadHistory();
  }, [symbol, category, interval]);

  useEffect(() => {
    void loadPrivateState();
    const timer = window.setInterval(() => void loadPrivateState(), 20_000);
    return () => window.clearInterval(timer);
  }, [symbol, category]);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let cancelled = false;
    setPositionStreamState("connecting");
    const start = async () => {
      try {
        const url = await withAuthTicket(bitgetPositionWsUrl(symbol, category));
        if (cancelled) return;
        socket = new WebSocket(url);
        socket.addEventListener("open", () => setPositionStreamState("live"));
        socket.addEventListener("message", (event) => {
          try {
            const payload = JSON.parse(String(event.data)) as { positions?: BitgetMcpEnvelope; orders?: BitgetMcpEnvelope };
            if (payload.positions) setPositionRows(payloadRows(payload.positions).slice(0, 6));
            if (payload.orders) setOrderRows(payloadRows(payload.orders).slice(0, 6));
            setPositionStreamState("live");
          } catch {
            // Ignore malformed stream frames; polling still refreshes the panels.
          }
        });
        socket.addEventListener("close", () => setPositionStreamState("offline"));
        socket.addEventListener("error", () => setPositionStreamState("offline"));
      } catch {
        setPositionStreamState("offline");
      }
    };
    void start();
    return () => {
      cancelled = true;
      socket?.close();
    };
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

  const selectSymbol = (candidate: BitgetSymbolCandidate) => {
    const next = normalizeSymbol(candidate.symbol);
    setSymbolInput(next);
    setSymbol(next);
    if (candidate.category === "SPOT" || candidate.category === "USDT-FUTURES") {
      setCategory(candidate.category);
    }
    setSymbolFocused(false);
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
            <div className="relative">
              <input
                value={symbolInput}
                onChange={(event) => setSymbolInput(event.target.value)}
                onFocus={() => setSymbolFocused(true)}
                onBlur={() => {
                  applySymbol();
                  window.setTimeout(() => setSymbolFocused(false), 120);
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter") applySymbol();
                }}
                className="h-9 w-36 rounded-md border bg-background px-3 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
              />
              {symbolFocused && symbolInput.trim().length >= 2 ? (
                <div className="absolute right-0 top-10 z-30 w-80 overflow-hidden rounded-md border bg-popover shadow-lg">
                  {symbolSearchLoading ? (
                    <div className="flex items-center gap-2 px-3 py-2 text-xs text-muted-foreground">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Searching Bitget
                    </div>
                  ) : symbolResults.length ? (
                    symbolResults.map((candidate) => (
                      <button
                        key={`${candidate.category}-${candidate.symbol}`}
                        type="button"
                        onMouseDown={(event) => {
                          event.preventDefault();
                          selectSymbol(candidate);
                        }}
                        className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-xs transition hover:bg-muted"
                      >
                        <span>
                          <span className="block text-sm font-medium text-foreground">{candidate.symbol}</span>
                          <span className="text-muted-foreground">
                            {candidate.base_coin && candidate.quote_coin
                              ? `${candidate.base_coin}/${candidate.quote_coin}`
                              : candidate.market || candidate.status || "Bitget"}
                          </span>
                        </span>
                        <span className="rounded border px-2 py-1 text-[11px] text-muted-foreground">{candidate.category}</span>
                      </button>
                    ))
                  ) : (
                    <div className="px-3 py-2 text-xs text-muted-foreground">No Bitget symbols</div>
                  )}
                </div>
              ) : null}
            </div>
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

        <section className="grid gap-3 md:grid-cols-4 xl:grid-cols-8">
          <Metric label="Symbol" value={`${symbol} ${category === "SPOT" ? "Spot" : "Perp"}`} icon={<Target className="h-4 w-4 text-primary" />} />
          <Metric label="Last price" value={lastPrice === null ? "Loading" : `$${formatPrice(lastPrice)}`} />
          <Metric
            label="Feed"
            value={wsState === "connecting" ? "Connecting" : wsState === "live" ? `Live ${lastTickAt || ""}` : "Offline"}
            icon={wsState === "live" ? <Wifi className="h-4 w-4 text-success" /> : <WifiOff className="h-4 w-4 text-warning" />}
          />
          <Metric label="MCP" value={statusText} icon={<ShieldCheck className="h-4 w-4 text-info" />} />
          <Metric
            label="Positions"
            value={positionStreamState === "live" ? `${positionRows.length} streaming` : `${positionRows.length} ${positionStreamState}`}
            icon={positionStreamState === "live" ? <Wifi className="h-4 w-4 text-success" /> : <WifiOff className="h-4 w-4 text-warning" />}
          />
          <Metric label="Live PnL" value={formatSignedMoney(livePnl)} icon={<TrendingUp className="h-4 w-4 text-success" />} />
          <Metric label="Exposure" value={formatMoney(estimatedExposure)} icon={<Layers className="h-4 w-4 text-info" />} />
          <Metric label="Alerts" value={`${alerts.length} active`} icon={<Bell className={`h-4 w-4 ${alerts.length ? "text-warning" : "text-success"}`} />} />
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

        <section className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(360px,0.9fr)]">
          <RiskDashboardPanel dashboard={riskDashboard} alerts={alerts} />
          <TradeManagementPanel category={category} symbol={symbol} onRefresh={() => void loadPrivateState()} />
        </section>

        <section className="grid gap-4 lg:grid-cols-2">
          <DataPanel title="Fill Timeline" rows={fillRows} empty="No fills returned by Bitget MCP" />
          <DataPanel title="TP/SL Orders" rows={strategyRows} empty="No active TP/SL strategy orders" />
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
      <div className="mt-1 flex min-w-0 items-center gap-2 text-sm font-medium">
        {icon}
        <span className="min-w-0 truncate">{value}</span>
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

function RiskDashboardPanel({ dashboard, alerts }: { dashboard: BitgetRiskDashboard | null; alerts: BitgetAlert[] }) {
  const fundingRows = payloadRows(dashboard?.funding);
  const openInterestRows = payloadRows(dashboard?.open_interest);
  const orders = payloadRows(dashboard?.orders).length;
  const strategyOrders = payloadRows(dashboard?.strategy_orders).length;
  const summary: NonNullable<BitgetRiskDashboard["summary"]> = dashboard?.summary || {};

  return (
    <section className="rounded-md border bg-card p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Gauge className="h-4 w-4 text-primary" />
          Risk Dashboard
        </div>
        <div className="text-xs text-muted-foreground">{dashboard?.symbol || "Bitget"}</div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-4">
        <MiniStat label="Positions" value={String(summary.positions ?? 0)} />
        <MiniStat label="PnL" value={formatSignedMoney(summary.estimated_unrealized_pnl_usdt ?? 0)} />
        <MiniStat label="Exposure" value={formatMoney(summary.estimated_notional_usdt ?? 0)} />
        <MiniStat label="Orders" value={`${orders} open / ${strategyOrders} TP-SL`} />
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <CompactRows title="Funding" rows={fundingRows} empty="No funding data" />
        <CompactRows title="Open Interest" rows={openInterestRows} empty="No open interest data" />
      </div>

      <div className="mt-4">
        <AlertPanel alerts={alerts} />
      </div>
    </section>
  );
}

function AlertPanel({ alerts }: { alerts: BitgetAlert[] }) {
  return (
    <div className="rounded-md border bg-background p-3">
      <div className="flex items-center gap-2 text-xs font-semibold">
        <Bell className="h-3.5 w-3.5 text-warning" />
        Alerts
      </div>
      {alerts.length ? (
        <div className="mt-3 space-y-2">
          {alerts.slice(0, 6).map((alert, index) => (
            <div key={`${alert.type}-${index}`} className={`rounded-md border px-3 py-2 text-xs ${alertToneClass(alert.severity)}`}>
              <div className="font-medium">{alert.type.replace(/_/g, " ")}</div>
              <div className="mt-1 opacity-90">
                {alert.symbol || "Bitget"}
                {alert.distance_percent !== undefined ? ` · ${formatCompactNumber(alert.distance_percent)}% away` : ""}
                {alert.status ? ` · ${alert.status}` : ""}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-3 rounded-md border border-dashed p-3 text-xs text-muted-foreground">No active Bitget alerts</div>
      )}
    </div>
  );
}

function CompactRows({ title, rows, empty }: { title: string; rows: Record<string, unknown>[]; empty: string }) {
  return (
    <div className="rounded-md border bg-background p-3">
      <div className="text-xs font-semibold">{title}</div>
      {rows.length ? (
        <div className="mt-2 space-y-2">
          {rows.slice(0, 3).map((row, index) => (
            <div key={index} className="text-xs text-muted-foreground">
              {Object.entries(row).slice(0, 4).map(([key, value]) => (
                <span key={key} className="mr-3 inline-block">
                  <span>{key}: </span>
                  <span className="text-foreground">{String(value)}</span>
                </span>
              ))}
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-2 text-xs text-muted-foreground">{empty}</div>
      )}
    </div>
  );
}

function TradeManagementPanel({ category, symbol, onRefresh }: { category: string; symbol: string; onRefresh: () => void }) {
  const [posSide, setPosSide] = useState<"long" | "short">("long");
  const [scaleSide, setScaleSide] = useState<"buy" | "sell">("buy");
  const [qty, setQty] = useState("");
  const [takeProfit, setTakeProfit] = useState("");
  const [stopLoss, setStopLoss] = useState("");
  const [strategyOrderId, setStrategyOrderId] = useState("");
  const [confirmationText, setConfirmationText] = useState("");
  const [dryRun, setDryRun] = useState(true);
  const [callbackPercent, setCallbackPercent] = useState("1");
  const [actionLoading, setActionLoading] = useState("");
  const [actionResult, setActionResult] = useState("");
  const [trailingProposal, setTrailingProposal] = useState<BitgetTrailingStopProposal | null>(null);

  const qtyValue = numberFromInput(qty);
  const takeProfitValue = numberFromInput(takeProfit);
  const stopLossValue = numberFromInput(stopLoss);
  const callbackValue = numberFromInput(callbackPercent) ?? 1;
  const busy = Boolean(actionLoading);
  const hasConfirmation = confirmationText.trim().length > 0;
  const hasTargets = takeProfitValue !== undefined || stopLossValue !== undefined;

  const runEnvelopeAction = async (label: string, action: () => Promise<BitgetMcpEnvelope>) => {
    setActionLoading(label);
    setActionResult("");
    try {
      const response = await action();
      const message = envelopeMessage(response);
      setActionResult(`${label}: ${message}`);
      if (String(response.status || "").toLowerCase() === "error" || response.error) {
        toast.error(message);
      } else {
        toast.success(`${label} submitted`);
        onRefresh();
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "unknown error";
      setActionResult(`${label}: ${message}`);
      toast.error(message);
    } finally {
      setActionLoading("");
    }
  };

  const runTrailingProposal = async () => {
    setActionLoading("Trailing proposal");
    setActionResult("");
    try {
      const response = await api.createBitgetTrailingStopProposal({
        symbol,
        category,
        pos_side: posSide,
        callback_percent: callbackValue,
      });
      setTrailingProposal(response);
      setActionResult(response.message || "Trailing stop proposal ready");
      toast.success("Trailing stop proposal ready");
    } catch (error) {
      const message = error instanceof Error ? error.message : "unknown error";
      setActionResult(`Trailing proposal: ${message}`);
      toast.error(message);
    } finally {
      setActionLoading("");
    }
  };

  return (
    <section className="rounded-md border bg-card p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Target className="h-4 w-4 text-primary" />
          Position Management
        </div>
        <label className="inline-flex items-center gap-2 text-xs text-muted-foreground">
          <input
            type="checkbox"
            checked={dryRun}
            onChange={(event) => setDryRun(event.target.checked)}
            className="h-4 w-4 rounded border"
          />
          Dry run
        </label>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <label className="text-xs font-medium">
          Position Side
          <select
            value={posSide}
            onChange={(event) => setPosSide(event.target.value as "long" | "short")}
            className="mt-1 h-9 w-full rounded-md border bg-background px-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
          >
            <option value="long">Long</option>
            <option value="short">Short</option>
          </select>
        </label>
        <label className="text-xs font-medium">
          Scale Side
          <select
            value={scaleSide}
            onChange={(event) => setScaleSide(event.target.value as "buy" | "sell")}
            className="mt-1 h-9 w-full rounded-md border bg-background px-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
          >
            <option value="buy">Buy</option>
            <option value="sell">Sell</option>
          </select>
        </label>
        <label className="text-xs font-medium">
          Qty
          <input
            value={qty}
            onChange={(event) => setQty(event.target.value)}
            inputMode="decimal"
            className="mt-1 h-9 w-full rounded-md border bg-background px-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
          />
        </label>
        <label className="text-xs font-medium">
          Callback %
          <input
            value={callbackPercent}
            onChange={(event) => setCallbackPercent(event.target.value)}
            inputMode="decimal"
            className="mt-1 h-9 w-full rounded-md border bg-background px-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
          />
        </label>
        <label className="text-xs font-medium">
          Take Profit
          <input
            value={takeProfit}
            onChange={(event) => setTakeProfit(event.target.value)}
            inputMode="decimal"
            className="mt-1 h-9 w-full rounded-md border bg-background px-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
          />
        </label>
        <label className="text-xs font-medium">
          Stop Loss
          <input
            value={stopLoss}
            onChange={(event) => setStopLoss(event.target.value)}
            inputMode="decimal"
            className="mt-1 h-9 w-full rounded-md border bg-background px-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
          />
        </label>
        <label className="text-xs font-medium sm:col-span-2">
          Strategy Order ID
          <input
            value={strategyOrderId}
            onChange={(event) => setStrategyOrderId(event.target.value)}
            className="mt-1 h-9 w-full rounded-md border bg-background px-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
          />
        </label>
        <label className="text-xs font-medium sm:col-span-2">
          Confirmation
          <input
            value={confirmationText}
            onChange={(event) => setConfirmationText(event.target.value)}
            placeholder="confirm"
            className="mt-1 h-9 w-full rounded-md border bg-background px-3 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
          />
        </label>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-2">
        <button
          type="button"
          disabled={busy || !hasConfirmation || !hasTargets}
          onClick={() => void runEnvelopeAction("TP/SL update", () => api.updateBitgetTpsl({
            symbol,
            category,
            pos_side: posSide,
            take_profit: takeProfitValue ?? null,
            stop_loss: stopLossValue ?? null,
            qty: qtyValue ?? null,
            strategy_order_id: strategyOrderId.trim() || null,
            confirmation_text: confirmationText,
            dry_run: dryRun,
          }))}
          className="inline-flex h-9 items-center justify-center gap-2 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {actionLoading === "TP/SL update" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Target className="h-4 w-4" />}
          Modify TP/SL
        </button>
        <button
          type="button"
          disabled={busy || !hasConfirmation || qtyValue === undefined}
          onClick={() => void runEnvelopeAction("Partial close", () => api.partialCloseBitgetPosition({
            symbol,
            category,
            pos_side: posSide,
            qty: qtyValue ?? 0,
            confirmation_text: confirmationText,
            dry_run: dryRun,
          }))}
          className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-destructive/40 bg-destructive px-3 text-sm font-medium text-destructive-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {actionLoading === "Partial close" ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
          Partial Close
        </button>
        <button
          type="button"
          disabled={busy || !hasConfirmation || qtyValue === undefined}
          onClick={() => void runEnvelopeAction("Scale position", () => api.scaleBitgetPosition({
            symbol,
            category,
            side: scaleSide,
            qty: qtyValue ?? 0,
            pos_side: posSide,
            confirmation_text: confirmationText,
            dry_run: dryRun,
          }))}
          className="inline-flex h-9 items-center justify-center gap-2 rounded-md border px-3 text-sm font-medium transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
        >
          {actionLoading === "Scale position" ? <Loader2 className="h-4 w-4 animate-spin" /> : <TrendingUp className="h-4 w-4" />}
          Scale Position
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void runTrailingProposal()}
          className="inline-flex h-9 items-center justify-center gap-2 rounded-md border px-3 text-sm font-medium transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
        >
          {actionLoading === "Trailing proposal" ? <Loader2 className="h-4 w-4 animate-spin" /> : <History className="h-4 w-4" />}
          Trail Proposal
        </button>
      </div>

      {trailingProposal ? (
        <div className="mt-4 grid grid-cols-3 gap-2 text-xs">
          <MiniStat label="Last" value={formatPrice(trailingProposal.last_price)} />
          <MiniStat label="Callback" value={`${formatCompactNumber(trailingProposal.callback_percent)}%`} />
          <MiniStat label="Stop" value={formatPrice(trailingProposal.suggested_stop)} />
        </div>
      ) : null}

      {actionResult ? <div className="mt-3 rounded-md border bg-muted/30 p-3 text-xs text-muted-foreground">{actionResult}</div> : null}
    </section>
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
                    {String(row.symbol || row.instId || row.coin || row.category || row.orderId || row.tradeId || `Row ${index + 1}`)}
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

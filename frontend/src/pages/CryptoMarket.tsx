import { useEffect, useMemo, useState, type ReactNode } from "react";
import { CoinGlassHeatmapCard } from "@/components/common/CoinGlassHeatmapCard";

import {
  Activity,
  AlertTriangle,
  Bell,
  Bot,
  CheckCircle2,
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
} from "@/lib/api";
import { withAuthTicket } from "@/lib/apiAuth";


type WsState = "connecting" | "live" | "offline";

const CATEGORIES = [
  { value: "USDT-FUTURES", label: "Futures", instType: "usdt-futures" },
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



function bitgetPositionWsUrl(symbol: string, category: string): string {
  const q = new URLSearchParams();
  q.set("symbol", symbol);
  q.set("category", category);
  q.set("interval_ms", "5000");
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/bitget/ws/positions?${q.toString()}`;
}


export function CryptoMarket() {
  const [category, setCategory] = useState<(typeof CATEGORIES)[number]["value"]>("USDT-FUTURES");
  const [symbolInput, setSymbolInput] = useState("BTCUSDT");
  const [symbol, setSymbol] = useState("BTCUSDT");
  const [symbolResults, setSymbolResults] = useState<BitgetSymbolCandidate[]>([]);
  const [symbolFocused, setSymbolFocused] = useState(false);
  const [symbolSearchLoading, setSymbolSearchLoading] = useState(false);
  const [interval, setInterval] = useState("5m");
  const [loading, setLoading] = useState(true);
  const [wsState, setWsState] = useState<WsState>("connecting");
  const [lastPrice, setLastPrice] = useState<number | null>(null);
  const [lastTickAt, setLastTickAt] = useState("");
  const [statusText, setStatusText] = useState("Checking");
  const [positionRows, setPositionRows] = useState<Record<string, unknown>[]>([]);
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





  const loadHistory = async () => {
    setLoading(false);
  };

  const loadPrivateState = async () => {
    try {
      const [status, positions, risk, alertPayload] = await Promise.all([
        api.getBitgetStatus(),
        api.getBitgetPositions({ category, symbol }),
        api.getBitgetRiskDashboard({ category, symbol }),
        api.getBitgetAlerts({ category, symbol }),
      ]);
      setStatusText(status.mcp_available ? (status.credentials_configured ? "MCP ready" : "Public only") : "MCP offline");
      setPositionRows(payloadRows(positions).slice(0, 6));
      setRiskDashboard(risk);
      setAlerts(alertPayload.alerts || []);
    } catch {
      setStatusText("Private reads unavailable");
      setPositionRows([]);
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
    if (candidate.category === "USDT-FUTURES") {
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
          <Metric label="Symbol" value={`${symbol} Perp`} icon={<Target className="h-4 w-4 text-primary" />} />
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
            <div className="h-[540px] w-full">
              <iframe
                src={`https://s.tradingview.com/widgetembed/?frameElementId=tradingview_123&symbol=BITGET:${symbol}${category === "USDT-FUTURES" ? ".P" : ""}&interval=${interval === '1m' ? '1' : interval.replace('m', '')}&hidesidetoolbar=0&symboledit=1&saveimage=1&toolbarbg=f1f3f6&studies=[]&theme=light&style=1&timezone=Etc%2FUTC&withdateranges=1&showpopupbutton=1&studies_overrides={}&overrides={}&enabled_features=[]&disabled_features=[]&locale=en&utm_source=localhost&utm_medium=widget&utm_campaign=chart&utm_term=BITGET%3A${symbol}`}
                style={{ width: "100%", height: "100%", border: "none", borderRadius: "8px" }}
                title="TradingView Advanced Chart"
              />
            </div>
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

        {/* CoinGlass Liquidation Heatmap Embed (Memoized to prevent lag) */}
        <section className="mt-6">
          <CoinGlassHeatmapCard symbol={symbol} />
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



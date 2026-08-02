import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Activity,
  Briefcase,
  CheckCircle2,
  Clock,
  Coins,
  Gauge,
  Layers,
  Loader2,
  RefreshCw,
  Target,
  TrendingUp,
} from "lucide-react";
import { toast } from "sonner";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { api, type BitgetMcpEnvelope } from "@/lib/api";

const CATEGORIES = [
  { value: "SPOT", label: "Spot Account" },
  { value: "USDT-FUTURES", label: "Futures Account" },
] as const;

function payloadRows(envelope: BitgetMcpEnvelope | null | undefined): Record<string, unknown>[] {
  if (!envelope) return [];
  const data = (envelope.structured_content as { data?: unknown } | undefined)?.data
    ?? (envelope.data as { data?: unknown } | undefined)?.data;
  
  let arrayData: Record<string, unknown>[] = [];
  if (Array.isArray(data)) {
    arrayData = data;
  } else if (data && typeof data === "object") {
    const d = data as any;
    if (d.assets?.data?.assets && Array.isArray(d.assets.data.assets)) {
      arrayData = d.assets.data.assets;
    } else if (d.list && Array.isArray(d.list)) {
      arrayData = d.list;
    } else {
      for (const val of Object.values(d)) {
        if (Array.isArray(val)) {
          arrayData = val;
          break;
        }
        if (val && typeof val === "object" && "list" in val && Array.isArray((val as any).list)) {
          arrayData = (val as any).list;
          break;
        }
      }
    }
  }
  return arrayData.filter((row): row is Record<string, unknown> => Boolean(row) && typeof row === "object");
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

function envelopeMessage(envelope: BitgetMcpEnvelope): string {
  const structured = envelope.structured_content as Record<string, unknown> | undefined;
  const data = envelope.data as Record<string, unknown> | undefined;
  const error = envelope.error ?? structured?.error ?? structured?.msg ?? structured?.message ?? data?.error ?? data?.msg ?? data?.message;
  if (error) return String(error);
  return String(envelope.status || structured?.status || data?.status || "ok");
}


function payloadObject(envelope: BitgetMcpEnvelope | null | undefined): Record<string, unknown> {
  if (!envelope) return {};
  const data = (envelope.structured_content as { data?: unknown } | undefined)?.data
    ?? (envelope.data as { data?: unknown } | undefined)?.data;
  if (data && typeof data === "object" && !Array.isArray(data)) {
    const d = data as any;
    if (d.assets?.data) return d.assets.data;
    if (d.data) return d.data;
    return d;
  }
  return {};
}

function bitgetPositionWsUrl(category: string): string {
  const q = new URLSearchParams();
  q.set("category", category);
  q.set("interval_ms", "2000");
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/bitget/ws/positions?${q.toString()}`;
}

export function Portfolio() {
  const [category, setCategory] = useState<(typeof CATEGORIES)[number]["value"]>("USDT-FUTURES");
  const [loading, setLoading] = useState(true);
  
  // Data states
  const [accountEnvelope, setAccountEnvelope] = useState<BitgetMcpEnvelope | null>(null);
  const [accountRows, setAccountRows] = useState<Record<string, unknown>[]>([]);
  const [spotAccountRows, setSpotAccountRows] = useState<Record<string, unknown>[]>([]);
  const [positionRows, setPositionRows] = useState<Record<string, unknown>[]>([]);
  const [orderRows, setOrderRows] = useState<Record<string, unknown>[]>([]);
  const [fillRows, setFillRows] = useState<Record<string, unknown>[]>([]);
  const [strategyRows, setStrategyRows] = useState<Record<string, unknown>[]>([]);

  // Action states
  const [actionLoading, setActionLoading] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmAction, setConfirmAction] = useState<{
    title: string;
    description: string;
    execute: () => Promise<void>;
  } | null>(null);

  const loadData = (showLoading = false) => {
    if (showLoading) setLoading(true);

    let activeRequests = 0;
    const increment = () => activeRequests++;
    const decrement = () => {
      activeRequests--;
      if (activeRequests <= 0 && showLoading) {
        setLoading(false);
      }
    };

    // Account
    increment();
    api.getBitgetAccount({ category }).then(account => {
      setAccountEnvelope(account);
      setAccountRows(payloadRows(account));
    }).catch(error => {
      toast.error(`Failed to load account data: ${error instanceof Error ? error.message : "unknown error"}`);
    }).finally(decrement);

    // Orders
    increment();
    api.getBitgetOrders({ category }).then(orders => {
      setOrderRows(payloadRows(orders));
    }).catch(console.error).finally(decrement);

    // Fills
    increment();
    api.getBitgetFills({ category, limit: 50 }).then(fills => {
      setFillRows(payloadRows(fills));
    }).catch(console.error).finally(decrement);

    if (category !== "SPOT") {
      // Positions
      increment();
      api.getBitgetPositions({ category }).then(positions => {
        setPositionRows(payloadRows(positions));
      }).catch(console.error).finally(decrement);

      // Strategy
      increment();
      api.getBitgetStrategyOrders({ category }).then(strategy => {
        setStrategyRows(payloadRows(strategy));
      }).catch(console.error).finally(decrement);
    } else {
      setPositionRows([]);
      setStrategyRows([]);
    }

    // Spot specific
    increment();
    api.getBitgetAccount({ category: "SPOT" }).then(spot => {
      setSpotAccountRows(payloadRows(spot));
    }).catch(() => {
      // Spot might fail if unsupported, ignore
    }).finally(decrement);
  };

  useEffect(() => {
    void loadData(true);
    const dataTimer = window.setInterval(() => void loadData(), 30_000);
    return () => window.clearInterval(dataTimer);
  }, [category]);

  useEffect(() => {
    if (category === "SPOT") return;
    let cancelled = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: number;

    const start = () => {
      if (cancelled) return;
      try {
        socket = new WebSocket(bitgetPositionWsUrl(category));
        socket.addEventListener("message", (event) => {
          if (cancelled) return;
          try {
            const payload = JSON.parse(String(event.data)) as { positions?: BitgetMcpEnvelope };
            if (payload.positions) {
              setPositionRows(payloadRows(payload.positions));
            }
          } catch {
            // Ignore malformed stream frames
          }
        });
        socket.addEventListener("close", () => {
          if (!cancelled) reconnectTimer = window.setTimeout(start, 5000);
        });
        socket.addEventListener("error", () => {
          socket?.close();
        });
      } catch {
        if (!cancelled) reconnectTimer = window.setTimeout(start, 5000);
      }
    };
    start();
    return () => {
      cancelled = true;
      socket?.close();
      window.clearTimeout(reconnectTimer);
    };
  }, [category]);

  // Derived values for Portfolio Overview
  const spotBalance = useMemo(() => sumRows(spotAccountRows, "usdtEquity", "usdValue", "equity", "available", "total"), [spotAccountRows]);
  const futuresBalance = useMemo(() => {
    const parentObj = payloadObject(accountEnvelope);
    if (parentObj.accountEquity || parentObj.usdtEquity) {
      return Number(parentObj.accountEquity || parentObj.usdtEquity || 0);
    }
    return sumRows(accountRows, "usdtEquity", "usdValue", "equity", "available", "total");
  }, [accountEnvelope, accountRows]);
  const totalValue = spotBalance + futuresBalance;
  const livePnl = useMemo(() => sumRows(positionRows, "unrealizedPL", "unrealisedPnl", "upl", "pnl", "unrealizedPnl"), [positionRows]);
  
  const handleAction = (title: string, description: string, action: () => Promise<BitgetMcpEnvelope>) => {
    setConfirmAction({
      title,
      description,
      execute: async () => {
        setActionLoading(title);
        try {
          const response = await action();
          const message = envelopeMessage(response);
          if (String(response.status || "").toLowerCase() === "error" || response.error) {
            toast.error(message);
          } else {
            toast.success(`${title} successful`);
            void loadData();
          }
        } catch (error) {
          toast.error(`${title} failed: ${error instanceof Error ? error.message : "unknown error"}`);
        } finally {
          setActionLoading("");
          setConfirmOpen(false);
        }
      },
    });
    setConfirmOpen(true);
  };

  const accountObj = payloadObject(accountEnvelope);

  return (
    <main className="min-h-screen bg-background p-4 md:p-6" id="portfolio">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        {/* Header Section */}
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Briefcase className="h-4 w-4 text-primary" />
              Bitget Portfolio Management
            </div>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight">My Portfolio</h1>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex h-9 rounded-md border bg-background p-0.5">
              {CATEGORIES.map((item) => (
                <button
                  key={item.value}
                  type="button"
                  onClick={() => setCategory(item.value)}
                  className={`min-w-24 rounded px-3 text-xs font-medium transition ${
                    item.value === category
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
              onClick={() => void loadData(true)}
              disabled={loading}
              className="inline-flex h-9 items-center justify-center gap-2 rounded-md border px-3 text-sm text-muted-foreground transition hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              <span className="hidden sm:inline">Refresh</span>
            </button>
          </div>
        </div>

        {/* Portfolio Overview */}
        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <Metric loading={loading} label="Total Portfolio Value" value={formatMoney(totalValue)} icon={<Briefcase className="h-4 w-4 text-primary" />} />
          <Metric loading={loading} label="Spot Wallet" value={formatMoney(spotBalance)} icon={<Coins className="h-4 w-4 text-info" />} />
          <Metric loading={loading} label="Futures Wallet" value={formatMoney(futuresBalance)} icon={<Layers className="h-4 w-4 text-warning" />} />
          <Metric loading={loading} label="Unrealized PnL (Futures)" value={formatSignedMoney(livePnl)} icon={<TrendingUp className={`h-4 w-4 ${livePnl >= 0 ? "text-success" : "text-destructive"}`} />} />
        </section>

        {category === "SPOT" ? (
          <section className="rounded-md border bg-card p-4">
            <div className="flex items-center gap-2 text-sm font-semibold mb-4">
              <Coins className="h-4 w-4 text-info" />
              Spot Assets
            </div>
            {loading && spotAccountRows.length === 0 ? (
              <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
                {[1, 2, 3, 4].map(i => (
                  <div key={i} className="rounded-md border bg-background p-3 animate-pulse">
                    <div className="h-4 w-16 bg-muted/60 rounded mb-3" />
                    <div className="space-y-2">
                      <div className="h-3 bg-muted/60 rounded w-full" />
                      <div className="h-3 bg-muted/60 rounded w-full" />
                      <div className="h-3 bg-muted/60 rounded w-full mt-3" />
                    </div>
                  </div>
                ))}
              </div>
            ) : spotAccountRows.length > 0 ? (
              <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
                {spotAccountRows.map((row, idx) => (
                  <div key={idx} className="rounded-md border bg-background p-3">
                    <div className="font-semibold text-sm mb-2">{String(row.coin || row.currency || "Unknown")}</div>
                    <div className="space-y-1 text-xs text-muted-foreground">
                      <div className="flex justify-between">
                        <span>Available:</span>
                        <span className="text-foreground">{formatCompactNumber(Number(row.available || 0))}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Frozen:</span>
                        <span className="text-foreground">{formatCompactNumber(Number(row.frozen || row.locked || 0))}</span>
                      </div>
                      <div className="flex justify-between border-t pt-1 mt-1">
                        <span>Est. USD:</span>
                        <span className="text-foreground font-medium">{formatMoney(rowNumber(row, "usdtEquity", "usdValue", "equity", "total"))}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
                No spot assets found
              </div>
            )}
          </section>
        ) : (
          <div className="flex flex-col gap-6">
            {/* Futures Account Overview */}
            <section className="rounded-md border bg-card p-4">
               <div className="flex items-center gap-2 text-sm font-semibold mb-4">
                <Gauge className="h-4 w-4 text-warning" />
                Futures Account Status
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {loading && accountRows.length === 0 ? (
                  <div className="col-span-full grid grid-cols-2 md:grid-cols-4 gap-4">
                    {[1, 2, 3, 4].map(i => (
                      <div key={i} className="rounded border bg-background p-3">
                        <div className="mb-2 h-3 w-16 animate-pulse rounded bg-muted/60" />
                        <div className="h-4 w-24 animate-pulse rounded bg-muted/60" />
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="col-span-full grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="rounded border bg-background p-3 text-xs">
                      <div className="text-muted-foreground mb-1">Account Equity</div>
                      <div className="text-sm font-semibold">{formatMoney(rowNumber(accountObj, "usdtEquity", "accountEquity", "equity"))}</div>
                    </div>
                    <div className="rounded border bg-background p-3 text-xs">
                      <div className="text-muted-foreground mb-1">Available Margin</div>
                      <div className="text-sm font-semibold">{formatMoney(rowNumber(accountObj, "available", "free", "effEquity"))}</div>
                    </div>
                    <div className="rounded border bg-background p-3 text-xs">
                      <div className="text-muted-foreground mb-1">Used Margin</div>
                      <div className="text-sm font-semibold">{formatMoney(rowNumber(accountObj, "locked", "frozen", "imr", "mmr"))}</div>
                    </div>
                    <div className="rounded border bg-background p-3 text-xs">
                      <div className="text-muted-foreground mb-1">Margin Ratio</div>
                      <div className="text-sm font-semibold">
                        {accountObj.marginRatio || accountObj.mgnRatio ? `${(Number(accountObj.marginRatio || accountObj.mgnRatio) * 100).toFixed(2)}%` : "N/A"}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </section>

            {/* Open Positions Table */}
            <section className="rounded-md border bg-card p-4">
              <div className="flex items-center gap-2 text-sm font-semibold mb-4">
                <Activity className="h-4 w-4 text-primary" />
                Open Positions
              </div>
              <div className="overflow-x-auto rounded-md border">
                <table className="w-full text-left text-xs whitespace-nowrap">
                  <thead className="border-b bg-muted/50">
                    <tr>
                      <th className="px-3 py-2 font-medium">Symbol</th>
                      <th className="px-3 py-2 font-medium">Side</th>
                      <th className="px-3 py-2 font-medium">Size</th>
                      <th className="px-3 py-2 font-medium">Entry Price</th>
                      <th className="px-3 py-2 font-medium">Mark Price</th>
                      <th className="px-3 py-2 font-medium">PnL</th>
                      <th className="px-3 py-2 font-medium">Lev / Margin</th>
                      <th className="px-3 py-2 font-medium text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {positionRows.length > 0 ? (
                      positionRows.map((row, idx) => {
                        const side = String(row.holdSide || row.posSide || "long").toLowerCase();
                        const pnl = Number(row.unrealizedPL || row.unrealisedPnl || row.upl || row.pnl || row.unrealizedPnl || 0);
                        const isLong = side === "long";
                        
                        return (
                          <tr key={idx} className="border-b last:border-0 hover:bg-muted/30">
                            <td className="px-3 py-2 font-medium">{String(row.symbol || row.instId || "Unknown")}</td>
                            <td className="px-3 py-2">
                              <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${isLong ? 'bg-success/10 text-success' : 'bg-destructive/10 text-destructive'}`}>
                                {side.toUpperCase()}
                              </span>
                            </td>
                            <td className="px-3 py-2">{formatCompactNumber(Number(row.total || row.size || 0))}</td>
                            <td className="px-3 py-2">{formatPrice(Number(row.averageOpenPrice || row.openPriceAvg || row.avgPrice || row.openPrice || 0))}</td>
                            <td className="px-3 py-2">{formatPrice(Number(row.markPrice || 0))}</td>
                            <td className={`px-3 py-2 font-medium ${pnl >= 0 ? 'text-success' : 'text-destructive'}`}>
                              {formatSignedMoney(pnl)}
                            </td>
                            <td className="px-3 py-2 text-muted-foreground">
                              {String(row.leverage || "1")}x <span className="opacity-50">|</span> {String(row.marginMode || "crossed").toUpperCase()}
                            </td>
                            <td className="px-3 py-2 text-right">
                              <button
                                onClick={() => handleAction(
                                  "Close Position", 
                                  `Close ${side} position on ${row.symbol}`,
                                  () => api.partialCloseBitgetPosition({
                                    symbol: String(row.symbol),
                                    category: "USDT-FUTURES",
                                    pos_side: side,
                                    qty: Number(row.total || row.size || 0),
                                    confirmation_text: "confirm"
                                  })
                                )}
                                className="inline-flex h-6 items-center justify-center rounded border px-2 text-[10px] font-medium transition hover:bg-destructive hover:text-destructive-foreground hover:border-destructive"
                              >
                                Close
                              </button>
                            </td>
                          </tr>
                        );
                      })
                    ) : (
                      <tr>
                        <td colSpan={8} className="px-3 py-6 text-center text-muted-foreground">No open positions</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>

            <div className="grid gap-6 xl:grid-cols-2">
              {/* Open Orders Table */}
              <section className="rounded-md border bg-card p-4">
                <div className="flex items-center gap-2 text-sm font-semibold mb-4">
                  <Clock className="h-4 w-4 text-info" />
                  Pending Orders
                </div>
                <div className="overflow-x-auto rounded-md border">
                  <table className="w-full text-left text-xs whitespace-nowrap">
                    <thead className="border-b bg-muted/50">
                      <tr>
                        <th className="px-3 py-2 font-medium">Symbol</th>
                        <th className="px-3 py-2 font-medium">Type</th>
                        <th className="px-3 py-2 font-medium">Side</th>
                        <th className="px-3 py-2 font-medium">Price</th>
                        <th className="px-3 py-2 font-medium">Qty</th>
                        <th className="px-3 py-2 font-medium">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {orderRows.length > 0 ? (
                        orderRows.map((row, idx) => (
                          <tr key={idx} className="border-b last:border-0 hover:bg-muted/30">
                            <td className="px-3 py-2 font-medium">{String(row.symbol || row.instId || "Unknown")}</td>
                            <td className="px-3 py-2">{String(row.orderType || row.type || "-")}</td>
                            <td className="px-3 py-2">
                              {String(row.side || "-").toLowerCase() === "buy" ? (
                                <span className="text-success">BUY</span>
                              ) : (
                                <span className="text-destructive">SELL</span>
                              )}
                            </td>
                            <td className="px-3 py-2">{formatPrice(Number(row.price || 0))}</td>
                            <td className="px-3 py-2">{formatCompactNumber(Number(row.size || row.qty || 0))}</td>
                            <td className="px-3 py-2 text-muted-foreground">{String(row.state || row.status || "-")}</td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={6} className="px-3 py-6 text-center text-muted-foreground">No pending orders</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </section>

              {/* Strategy Orders */}
              <section className="rounded-md border bg-card p-4">
                <div className="flex items-center gap-2 text-sm font-semibold mb-4">
                  <Target className="h-4 w-4 text-primary" />
                  Strategy Orders (TP/SL)
                </div>
                <div className="overflow-x-auto rounded-md border">
                  <table className="w-full text-left text-xs whitespace-nowrap">
                    <thead className="border-b bg-muted/50">
                      <tr>
                        <th className="px-3 py-2 font-medium">Symbol</th>
                        <th className="px-3 py-2 font-medium">Type</th>
                        <th className="px-3 py-2 font-medium">Trigger</th>
                        <th className="px-3 py-2 font-medium">Qty</th>
                        <th className="px-3 py-2 font-medium">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {strategyRows.length > 0 ? (
                        strategyRows.map((row, idx) => {
                          const tp = Number(row.takeProfit || row.tpLimitPrice || 0);
                          const sl = Number(row.stopLoss || row.slLimitPrice || 0);
                          const triggers = [];
                          if (tp) triggers.push(`TP: ${formatPrice(tp)}`);
                          if (sl) triggers.push(`SL: ${formatPrice(sl)}`);
                          const triggerDisplay = triggers.length > 0 
                            ? triggers.join(" | ") 
                            : formatPrice(Number(row.triggerPrice || row.planPrice || 0));

                          return (
                            <tr key={idx} className="border-b last:border-0 hover:bg-muted/30">
                              <td className="px-3 py-2 font-medium">{String(row.symbol || "Unknown")}</td>
                              <td className="px-3 py-2">{String(row.planType || row.type || "-")}</td>
                              <td className="px-3 py-2 text-[11px] whitespace-nowrap">{triggerDisplay}</td>
                              <td className="px-3 py-2">{formatCompactNumber(Number(row.size || row.qty || 0))}</td>
                              <td className="px-3 py-2 text-muted-foreground">{String(row.state || row.status || "-")}</td>
                            </tr>
                          );
                        })
                      ) : (
                        <tr>
                          <td colSpan={5} className="px-3 py-6 text-center text-muted-foreground">No strategy orders</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>

            {/* Recent Fills */}
            <section className="rounded-md border bg-card p-4">
              <div className="flex items-center gap-2 text-sm font-semibold mb-4">
                <CheckCircle2 className="h-4 w-4 text-success" />
                Recent Fills
              </div>
              <div className="overflow-x-auto rounded-md border">
                <table className="w-full text-left text-xs whitespace-nowrap">
                  <thead className="border-b bg-muted/50">
                    <tr>
                      <th className="px-3 py-2 font-medium">Time</th>
                      <th className="px-3 py-2 font-medium">Symbol</th>
                      <th className="px-3 py-2 font-medium">Side</th>
                      <th className="px-3 py-2 font-medium">Price</th>
                      <th className="px-3 py-2 font-medium">Qty</th>
                      <th className="px-3 py-2 font-medium">Fee</th>
                    </tr>
                  </thead>
                  <tbody>
                    {fillRows.length > 0 ? (
                      fillRows.map((row, idx) => {
                        const time = new Date(Number(row.cTime || row.ts || Date.now()));
                        return (
                          <tr key={idx} className="border-b last:border-0 hover:bg-muted/30">
                            <td className="px-3 py-2 text-muted-foreground">
                              {time.toLocaleDateString()} {time.toLocaleTimeString()}
                            </td>
                            <td className="px-3 py-2 font-medium">{String(row.symbol || row.instId || "Unknown")}</td>
                            <td className="px-3 py-2">
                              {String(row.side || "-").toLowerCase() === "buy" ? (
                                <span className="text-success">BUY</span>
                              ) : (
                                <span className="text-destructive">SELL</span>
                              )}
                            </td>
                            <td className="px-3 py-2">{formatPrice(Number(row.price || 0))}</td>
                            <td className="px-3 py-2">{formatCompactNumber(Number(row.baseVolume || row.size || 0))}</td>
                            <td className="px-3 py-2 text-muted-foreground">
                              {formatCompactNumber(Number(row.fee || 0))} {String(row.feeCcy || "")}
                            </td>
                          </tr>
                        );
                      })
                    ) : (
                      <tr>
                        <td colSpan={6} className="px-3 py-6 text-center text-muted-foreground">No recent fills</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={confirmOpen}
        title={confirmAction?.title || "Confirm Action"}
        description={confirmAction?.description || "Are you sure you want to proceed?"}
        confirmLabel={actionLoading ? "Processing..." : "Confirm"}
        cancelLabel="Cancel"
        tone="destructive"
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => {
          if (confirmAction) void confirmAction.execute();
        }}
      />
    </main>
  );
}

function Metric({ label, value, icon, loading }: { label: string; value: ReactNode; icon?: ReactNode; loading?: boolean }) {
  return (
    <div className="rounded-md border bg-card px-4 py-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 flex min-w-0 items-center gap-2 text-sm font-medium">
        {icon}
        {loading ? (
          <div className="h-5 w-24 animate-pulse rounded bg-muted/60" />
        ) : (
          <span className="min-w-0 truncate">{value}</span>
        )}
      </div>
    </div>
  );
}

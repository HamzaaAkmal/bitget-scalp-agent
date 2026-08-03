import { useEffect, useState } from "react";
import {
  Activity,
  AlertOctagon,
  Bot,
  Brain,
  CheckCircle2,
  Flame,
  LineChart,
  Play,
  Radar,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Square,
  Zap,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import {
  scalpApi,
  type ScalpSessionData,
  type SessionPolicy,
  type ScalpCandidate,
  type ScalpTrade,
} from "@/lib/scalp-api";

const PRESET_MISSIONS = [
  {
    label: "3H Bitget Scalp (BTC/ETH/SOL)",
    text: "Allocate 20 USDT for the next 3 hours. Scan BTC, ETH, SOL and other high-volume Bitget futures markets. Use isolated margin, maximum 3x leverage, risk no more than 0.50 USDT per trade, stop after earning 5 USDT or losing 2 USDT.",
  },
  {
    label: "Conservative Copilot",
    text: "Use 20 USDT and scalp BTCUSDT only using 5-minute chart. Use Copilot mode, isolated 2x leverage, risk 0.30 USDT per trade, and ask before every trade.",
  },
  {
    label: "Altcoin Volume Scalper",
    text: "Find the best high-volume futures opportunity on Bitget. Exclude meme coins. Stop after 2 consecutive losses. Max duration 2 hours.",
  },
];

function formatLargeNumber(val?: number): string {
  if (!val || val <= 0) return "N/A";
  if (val >= 1e9) return `${(val / 1e9).toFixed(2)}B`;
  if (val >= 1e6) return `${(val / 1e6).toFixed(2)}M`;
  if (val >= 1e3) return `${(val / 1e3).toFixed(2)}K`;
  return val.toFixed(2);
}

export function AIScalpTrader() {
  const [missionInput, setMissionInput] = useState(PRESET_MISSIONS[0].text);
  const [parsing, setParsing] = useState(false);
  const [parsedPolicy, setParsedPolicy] = useState<SessionPolicy | null>(null);
  const [activeSession, setActiveSession] = useState<ScalpSessionData | null>(null);
  const [activeTrade, setActiveTrade] = useState<ScalpTrade | null>(null);
  const [activeTrades, setActiveTrades] = useState<ScalpTrade[]>([]);
  const [pendingProposal, setPendingProposal] = useState<any>(null);
  const [requireApproval, setRequireApproval] = useState(true);
  const [isClosing, setIsClosing] = useState(false);
  const [recentTrades, setRecentTrades] = useState<ScalpTrade[]>([]);
  const [candidates, setCandidates] = useState<ScalpCandidate[]>([]);
  const [funnelCounts, setFunnelCounts] = useState({
    all_markets: 126,
    passed_liquidity: 18,
    passed_technical: 4,
    top_candidates: 2,
  });
  const [selectedSymbol, setSelectedSymbol] = useState<string>("BTCUSDT");
  const [symbolDetail, setSymbolDetail] = useState<any>(null);
  const [regimeInfo, setRegimeInfo] = useState<any>(null);
  const [loadingCandidates, setLoadingCandidates] = useState(true);
  const [emergencyActive, setEmergencyActive] = useState(false);
  const [agentLogs, setAgentLogs] = useState<Array<{ timestamp: string; session_id?: string; agent: string; level: string; action: string; message: string; details?: any }>>([]);
  const [selectedAgentFilter, setSelectedAgentFilter] = useState<string>("ALL");
  const [autonomyMode, setAutonomyMode] = useState<"copilot" | "guarded_autopilot" | "full_autonomous">("guarded_autopilot");

  // Load active sessions & market candidates on mount
  useEffect(() => {
    loadActiveSession();
    loadMarketData();
    const interval = setInterval(loadMarketData, 8000);
    return () => clearInterval(interval);
  }, []);

  // Fetch symbol detail when selected symbol changes
  useEffect(() => {
    if (!selectedSymbol) return;
    scalpApi.getMarketDetail(selectedSymbol).then((res) => {
      setSymbolDetail(res);
    }).catch(() => {});
  }, [selectedSymbol]);

  // Session status & active trade poll
  useEffect(() => {
    if (!activeSession || activeSession.status !== "ACTIVE") return;
    const sessionInterval = setInterval(async () => {
      try {
        const res = await scalpApi.getSessionDetail(activeSession.session_id);
        setActiveSession(res.session);
        if (res.active_trades) {
          setActiveTrades(res.active_trades);
          if (res.active_trades.length > 0) {
            setActiveTrade(res.active_trades[res.active_trades.length - 1]);
          } else {
            setActiveTrade(null);
          }
        } else if (res.active_trade) {
          setActiveTrade(res.active_trade);
          setActiveTrades([res.active_trade]);
        } else {
          setActiveTrade(null);
          setActiveTrades([]);
        }

        if (res.pending_proposal) {
          setPendingProposal(res.pending_proposal);
        } else {
          setPendingProposal(null);
        }

        if (res.recent_trades) {
          setRecentTrades(res.recent_trades);
        }

        // Fetch Realtime Agent Decision Logs
        try {
          const logRes = await scalpApi.getSessionLogs(activeSession.session_id);
          if (logRes.logs) {
            setAgentLogs(logRes.logs);
          }
        } catch (_) {}
      } catch (err) {
        /* best-effort poll */
      }
    }, 2000);
    return () => clearInterval(sessionInterval);
  }, [activeSession?.session_id, activeSession?.status]);

  const loadActiveSession = async () => {
    try {
      const res = await scalpApi.getActiveSessions();
      if (res.active_sessions && res.active_sessions.length > 0) {
        const active = res.active_sessions[0];
        setActiveSession(active);
        const detail = await scalpApi.getSessionDetail(active.session_id);
        setActiveSession(detail.session);
        if (detail.active_trades) {
          setActiveTrades(detail.active_trades);
          if (detail.active_trades.length > 0) {
            setActiveTrade(detail.active_trades[detail.active_trades.length - 1]);
          }
        } else if (detail.active_trade) {
          setActiveTrade(detail.active_trade);
          setActiveTrades([detail.active_trade]);
        }
        if (detail.pending_proposal) {
          setPendingProposal(detail.pending_proposal);
        }
        if (detail.recent_trades) {
          setRecentTrades(detail.recent_trades);
        }
      }
    } catch (err) {
      /* best-effort fallback */
    }
  };

  const loadMarketData = async () => {
    try {
      const [candRes, regRes] = await Promise.all([
        scalpApi.getMarketCandidates(),
        scalpApi.getMarketRegime(),
      ]);
      setCandidates(candRes.data.candidates || []);
      setFunnelCounts(candRes.data.funnel_counts || funnelCounts);
      setRegimeInfo(regRes.regime);
    } catch (err) {
      /* best-effort fallback */
    } finally {
      setLoadingCandidates(false);
    }
  };

  const handleParseMission = async () => {
    setParsing(true);
    try {
      const res = await scalpApi.parseMission(missionInput);
      setParsedPolicy(res.policy);
      setAutonomyMode(res.policy.autonomy_mode || "guarded_autopilot");
      toast.success("Trading mission parsed into strict session policy.");
    } catch (err: any) {
      toast.error(err.message || "Failed to parse mission");
    } finally {
      setParsing(false);
    }
  };

  const handleStartSession = async () => {
    try {
      let policyToUse = parsedPolicy;
      if (!policyToUse) {
        const parseRes = await scalpApi.parseMission(missionInput);
        policyToUse = parseRes.policy;
        setParsedPolicy(policyToUse);
      }

      // Apply selected autonomy mode and requireHumanApproval toggle
      policyToUse = { 
        ...policyToUse, 
        autonomy_mode: autonomyMode,
        require_human_approval: requireApproval,
      };

      const createRes = await scalpApi.createSession(missionInput, policyToUse);
      const startRes = await scalpApi.startSession(createRes.session.session_id);
      setActiveSession(startRes.session);
      toast.success(`Autonomous Scalp Session ${startRes.session.session_id} Started!`);
    } catch (err: any) {
      toast.error(err.message || "Failed to start session");
    }
  };

  const handleStopSession = async () => {
    if (!activeSession) return;
    try {
      const res = await scalpApi.stopSession(activeSession.session_id);
      setActiveSession(res.session);
      toast.info("Scalp Session Stopped.");
    } catch (err: any) {
      toast.error(err.message || "Failed to stop session");
    }
  };

  const handleEmergencyStop = async () => {
    try {
      const res = await scalpApi.triggerEmergencyStop();
      setEmergencyActive(true);
      if (activeSession) {
        setActiveSession({ ...activeSession, status: "EMERGENCY_STOPPED" });
      }
      toast.error(`🚨 EMERGENCY STOP ACTIVATED: ${res.message}`);
    } catch (err: any) {
      toast.error(err.message || "Emergency stop failed");
    }
  };

  const handleConfirmCopilotTrade = async () => {
    if (!activeSession || !pendingProposal) return;
    try {
      const res = await scalpApi.confirmCopilotTrade(activeSession.session_id, pendingProposal.proposal_id);
      toast.success("Trade Proposal Approved & Order Submitted to Bitget!");
      setPendingProposal(null);
      if (res.trade) {
        setActiveTrades((prev) => [...prev, res.trade!]);
        setActiveTrade(res.trade!);
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to confirm trade proposal");
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground p-4 md:p-6 space-y-6 max-w-7xl mx-auto">
      {/* 1. Header Bar */}
      <header className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 p-4 rounded-xl bg-card border border-border/80 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-primary/10 text-primary">
            <Radar className="h-6 w-6 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight">AI Scalp Trader</h1>
              <span className="px-2 py-0.5 text-[11px] font-semibold rounded-full bg-primary/15 text-primary">
                Vibe Agents v1.0
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              Production-Grade Multi-Agent Autonomous Futures Trading Desk
            </p>
          </div>
        </div>

        {/* Live Status Indicators & Emergency Stop */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-muted text-xs font-medium border border-border/60">
            <Bot className="h-3.5 w-3.5 text-primary" />
            <span className="capitalize">{autonomyMode.replace("_", " ")}</span>
          </div>

          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-500 text-xs font-medium border border-emerald-500/20">
            <ShieldCheck className="h-3.5 w-3.5" />
            <span>Bitget Production (USDT-Futures)</span>
          </div>

          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-info/10 text-info text-xs font-medium border border-info/20">
            <Activity className="h-3.5 w-3.5" />
            <span>Regime: {regimeInfo?.primary_regime || "STRONG_DOWNTREND"}</span>
          </div>

          <div
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border",
              activeSession?.status === "ACTIVE"
                ? "bg-emerald-500/15 text-emerald-500 border-emerald-500/30"
                : "bg-muted text-muted-foreground border-border"
            )}
          >
            <span className="relative flex h-2 w-2">
              {activeSession?.status === "ACTIVE" && (
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              )}
              <span
                className={cn(
                  "relative inline-flex rounded-full h-2 w-2",
                  activeSession?.status === "ACTIVE" ? "bg-emerald-500" : "bg-muted-foreground"
                )}
              ></span>
            </span>
            <span>{activeSession?.status || "STOPPED"}</span>
          </div>

          <button
            onClick={handleEmergencyStop}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-destructive hover:bg-destructive/90 text-destructive-foreground text-xs font-bold transition-all shadow-md active:scale-95"
          >
            <AlertOctagon className="h-4 w-4" />
            <span>EMERGENCY STOP</span>
          </button>
        </div>
      </header>

      {/* Emergency Stop Alert Banner if Active */}
      {emergencyActive && (
        <div className="p-4 rounded-xl bg-destructive/15 border-2 border-destructive text-destructive flex items-center justify-between">
          <div className="flex items-center gap-3">
            <AlertOctagon className="h-6 w-6 shrink-0" />
            <div>
              <h3 className="font-bold text-sm">GLOBAL EMERGENCY STOP IS ACTIVE</h3>
              <p className="text-xs">All autonomous execution halted. All pending Bitget orders cancelled.</p>
            </div>
          </div>
          <button
            onClick={async () => {
              await scalpApi.resetEmergencyStop();
              setEmergencyActive(false);
              toast.info("Emergency Stop Reset.");
            }}
            className="px-3 py-1.5 rounded-md bg-background text-xs font-semibold hover:bg-muted border border-border"
          >
            Reset Emergency Stop
          </button>
        </div>
      )}

      {/* Copilot Trade Proposal Approval Banner */}
      {activeSession && activeSession.active_proposal_id && (
        <div className="p-4 rounded-xl bg-primary/15 border-2 border-primary text-foreground flex items-center justify-between shadow-md">
          <div className="flex items-center gap-3">
            <Bot className="h-6 w-6 text-primary shrink-0 animate-bounce" />
            <div>
              <h3 className="font-bold text-sm">Copilot Trade Proposal Ready for Authorization</h3>
              <p className="text-xs text-muted-foreground">
                The agent desk generated a trade proposal with verified net edge. Click approve to execute on Bitget.
              </p>
            </div>
          </div>
          <button
            onClick={handleConfirmCopilotTrade}
            className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-xs font-bold shadow hover:opacity-90 transition-all"
          >
            Approve & Execute Trade
          </button>
        </div>
      )}

      {/* Main Streamlined Grid */}
      <div className="space-y-6">
        {/* 2. Natural Language Mission Builder */}
        <div className="p-5 rounded-xl bg-card border border-border/80 space-y-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" />
              <h2 className="font-semibold text-base">Natural-Language Trading Mission</h2>
            </div>
            <span className="text-xs text-muted-foreground">Describe your strategy policy in plain English</span>
          </div>

          {/* Presets */}
          <div className="flex flex-wrap gap-2">
            {PRESET_MISSIONS.map((preset, idx) => (
              <button
                key={idx}
                onClick={() => {
                  setMissionInput(preset.text);
                  setParsedPolicy(null);
                }}
                className="px-2.5 py-1 text-[11px] rounded-md bg-muted hover:bg-muted/80 text-muted-foreground hover:text-foreground transition-colors border border-border/40"
              >
                {preset.label}
              </button>
            ))}
          </div>

          {/* Textarea Prompt Input */}
          <textarea
            value={missionInput}
            onChange={(e) => setMissionInput(e.target.value)}
            rows={3}
            placeholder="e.g. Allocate 20 USDT for 3 hours. Scan BTC, ETH, SOL futures..."
            className="w-full p-3 rounded-lg bg-background text-sm border border-border focus:ring-2 focus:ring-primary/40 outline-none resize-none"
          />

          {/* Action Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 bg-muted/60 p-1 rounded-lg text-xs font-medium border border-border/40">
              <button
                onClick={() => setAutonomyMode("copilot")}
                className={cn(
                  "px-3 py-1.5 rounded-md transition-colors",
                  autonomyMode === "copilot"
                    ? "bg-card text-foreground font-semibold shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                1. Copilot
              </button>
              <button
                onClick={() => setAutonomyMode("guarded_autopilot")}
                className={cn(
                  "px-3 py-1.5 rounded-md transition-colors",
                  autonomyMode === "guarded_autopilot"
                    ? "bg-card text-foreground font-semibold shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                2. Guarded Autopilot
              </button>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleParseMission}
                disabled={parsing}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-muted hover:bg-muted/80 text-foreground text-xs font-semibold transition-colors border border-border"
              >
                {parsing ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Brain className="h-3.5 w-3.5" />}
                <span>Parse Policy</span>
              </button>

              {!activeSession || activeSession.status !== "ACTIVE" ? (
                <button
                  onClick={handleStartSession}
                  className="flex items-center gap-1.5 px-5 py-2 rounded-lg bg-primary text-primary-foreground text-xs font-bold transition-all shadow-md hover:opacity-90 active:scale-95"
                >
                  <Play className="h-3.5 w-3.5 fill-current" />
                  <span>Start Session</span>
                </button>
              ) : (
                <button
                  onClick={handleStopSession}
                  className="flex items-center gap-1.5 px-5 py-2 rounded-lg bg-destructive text-destructive-foreground text-xs font-bold transition-all shadow-md hover:opacity-90"
                >
                  <Square className="h-3.5 w-3.5 fill-current" />
                  <span>Stop Session</span>
                </button>
              )}
            </div>
          </div>

          {/* Parsed Policy Preview */}
          {parsedPolicy && (
            <div className="p-4 rounded-lg bg-muted/40 border border-border/80 space-y-3 mt-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-foreground">Active Session Policy Parameters</span>
                <span className="text-[11px] text-muted-foreground">Enforced Deterministic Rules</span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                <div className="p-2 rounded bg-card border border-border/50">
                  <div className="text-[10px] text-muted-foreground">Allocated Capital</div>
                  <div className="font-semibold">{parsedPolicy.allocated_capital} USDT</div>
                </div>
                <div className="p-2 rounded bg-card border border-border/50">
                  <div className="text-[10px] text-muted-foreground">Target Profit</div>
                  <div className="font-semibold text-emerald-500">+{parsedPolicy.target_profit} USDT</div>
                </div>
                <div className="p-2 rounded bg-card border border-border/50">
                  <div className="text-[10px] text-muted-foreground">Max Session Loss</div>
                  <div className="font-semibold text-destructive">-{parsedPolicy.maximum_session_loss} USDT</div>
                </div>
                <div className="p-2 rounded bg-card border border-border/50">
                  <div className="text-[10px] text-muted-foreground">Max Leverage</div>
                  <div className="font-semibold">{parsedPolicy.maximum_leverage}x Isolated</div>
                </div>
              </div>

              {parsedPolicy.warnings && parsedPolicy.warnings.length > 0 && (
                <div className="space-y-1.5 pt-1">
                  {parsedPolicy.warnings.map((w, idx) => (
                    <div
                      key={idx}
                      className={cn(
                        "p-2.5 rounded-md text-xs flex items-start gap-2 border",
                        w.level === "critical"
                          ? "bg-destructive/10 text-destructive border-destructive/30"
                          : "bg-warning/10 text-warning border-warning/30"
                      )}
                    >
                      <ShieldAlert className="h-4 w-4 shrink-0 mt-0.5" />
                      <div>
                        <p className="font-semibold">{w.message}</p>
                        <p className="text-[11px] opacity-90 mt-0.5">{w.impact}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* 3. ALWAYS VISIBLE: Active Positions & Live Trade Desk */}
        {(() => {
          const rawPositions = activeTrades.length > 0 ? activeTrades : (activeTrade ? [activeTrade] : []);
          const deduplicatedMap: Record<string, ScalpTrade> = {};
          for (const t of rawPositions) {
            if (t && t.symbol) {
              deduplicatedMap[t.symbol] = t;
            }
          }
          const openPositionsList = Object.values(deduplicatedMap);
          const combinedUnrealizedPnl = openPositionsList.reduce((sum, t) => sum + (t.unrealized_pnl_usdt || 0), 0);
          const liveTotalPnl = (activeSession?.session_pnl_usdt || 0) + combinedUnrealizedPnl;

          return (
            <>
              <div className="p-5 rounded-xl bg-card border-2 border-primary/40 space-y-4 shadow-sm">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-2 flex-wrap">
                    <Flame className="h-5 w-5 text-primary animate-bounce" />
                    <h3 className="font-bold text-base">
                      Active Futures Positions & Live PnL Desk ({openPositionsList.length} Active)
                    </h3>
                  </div>

                  {/* Human Approval Toggle Switch */}
                  <div className="flex items-center gap-2.5 px-3 py-1.5 rounded-lg bg-muted/60 border border-border/60 text-xs shrink-0">
                    <ShieldAlert className={cn("h-4 w-4", requireApproval ? "text-primary animate-pulse" : "text-muted-foreground")} />
                    <span className="font-semibold text-foreground">Require Human Approval</span>
                    <button
                      type="button"
                      onClick={() => setRequireApproval(!requireApproval)}
                      className={cn(
                        "relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none",
                        requireApproval ? "bg-primary" : "bg-muted-foreground/30"
                      )}
                    >
                      <span
                        className={cn(
                          "pointer-events-none inline-block h-4 w-4 transform rounded-full bg-background shadow-lg ring-0 transition duration-200 ease-in-out",
                          requireApproval ? "translate-x-4" : "translate-x-0"
                        )}
                      />
                    </button>
                  </div>
                </div>

                {/* Pending Proposal Approval Modal Alert */}
                {pendingProposal && (
                  <div className="p-4 rounded-xl bg-primary/10 border-2 border-primary/60 space-y-3 shadow-md animate-pulse">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <ShieldAlert className="h-5 w-5 text-primary" />
                        <span className="font-bold text-sm text-foreground">
                          🚨 TRADE PROPOSAL APPROVAL REQUIRED (Human Approval Gate ON)
                        </span>
                      </div>
                      <span className="text-xs font-semibold px-2 py-0.5 rounded bg-primary/20 text-primary">
                        Setup Quality: {pendingProposal.setup_quality_score || 85}%
                      </span>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs bg-card/80 p-3 rounded-lg border border-border/50">
                      <div>
                        <div className="text-[10px] text-muted-foreground">Market & Setup</div>
                        <div className="font-bold text-sm text-foreground">
                          {pendingProposal.symbol} {pendingProposal.direction} {pendingProposal.leverage}x
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] text-muted-foreground">Entry / Stop / Target</div>
                        <div className="font-semibold text-xs">
                          ${pendingProposal.entry_price} (SL: ${pendingProposal.stop_loss} | TP: ${pendingProposal.take_profit_1})
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] text-muted-foreground">Position Margin</div>
                        <div className="font-semibold text-xs">${pendingProposal.margin_required_usdt} USDT</div>
                      </div>
                      <div>
                        <div className="text-[10px] text-muted-foreground">Expected Net Edge</div>
                        <div className="font-bold text-xs text-emerald-500">
                          {pendingProposal.why_this_trade?.expected_net_edge || "+0.25 USDT"}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center justify-end gap-3 pt-1">
                      <button
                        onClick={() => setPendingProposal(null)}
                        className="px-4 py-1.5 rounded-lg border border-border text-xs font-bold hover:bg-muted"
                      >
                        Reject Trade
                      </button>
                      <button
                        onClick={handleConfirmCopilotTrade}
                        className="px-5 py-1.5 rounded-lg bg-primary text-primary-foreground text-xs font-bold shadow hover:opacity-90 transition-all flex items-center gap-1.5"
                      >
                        <CheckCircle2 className="h-4 w-4" />
                        <span>Approve & Place Trade</span>
                      </button>
                    </div>
                  </div>
                )}

                {/* Open Position Cards List */}
                {openPositionsList.length > 0 ? (
                  <div className="space-y-6">
                    {openPositionsList.map((trade, idx) => (
                      <div key={trade.trade_id || idx} className="p-5 rounded-xl bg-card border border-border/80 space-y-4 shadow-sm">
                        <div className="flex items-center justify-between flex-wrap gap-2">
                          <div className="flex items-center gap-2.5">
                            {trade.coin_icon ? (
                              <img
                                src={trade.coin_icon}
                                alt={trade.symbol}
                                className="h-6 w-6 rounded-full object-cover border border-border/50 shrink-0"
                                onError={(e) => {
                                  (e.target as HTMLImageElement).src = "https://assets.coingecko.com/coins/images/1/large/bitcoin.png";
                                }}
                              />
                            ) : (
                              <div className="h-6 w-6 rounded-full bg-primary/20 flex items-center justify-center font-bold text-[10px] text-primary shrink-0">
                                {trade.symbol.slice(0, 3)}
                              </div>
                            )}
                            <span
                              className={cn(
                                "px-2.5 py-0.5 text-xs font-bold rounded",
                                trade.direction === "LONG"
                                  ? "bg-emerald-500/15 text-emerald-500"
                                  : "bg-destructive/15 text-destructive"
                              )}
                            >
                              {trade.symbol} {trade.direction} {trade.leverage}x Isolated
                            </span>
                            <span className="text-xs text-muted-foreground font-mono">Trade ID: {trade.trade_id}</span>
                          </div>

                          <button
                            disabled={isClosing}
                            onClick={async () => {
                              setIsClosing(true);
                              try {
                                const res = await scalpApi.closePosition(trade.trade_id);
                                if (res.status === "ok") {
                                  toast.success(`Position ${trade.symbol} closed successfully on Bitget`);
                                  setActiveTrades((prev) => prev.filter((t) => t.trade_id !== trade.trade_id));
                                } else {
                                  toast.error(res.message || "Failed to close position");
                                }
                              } catch (err: any) {
                                toast.error(err.message || "Error closing position");
                              } finally {
                                setIsClosing(false);
                              }
                            }}
                            className="px-3 py-1 rounded-lg bg-destructive text-destructive-foreground text-xs font-bold hover:bg-destructive/90 disabled:opacity-50 transition-all shadow-xs"
                          >
                            {isClosing ? "Closing..." : "Close Position"}
                          </button>
                        </div>

                        {/* CoinGecko Market Metrics Pill Bar */}
                        <div className="flex items-center gap-3 text-xs bg-muted/40 p-2.5 rounded-lg border border-border/50 text-muted-foreground flex-wrap">
                          <span className="font-semibold text-foreground flex items-center gap-1 shrink-0">
                            🦎 CoinGecko Data:
                          </span>
                          <span>
                            24h Vol: <strong className="text-foreground font-semibold">${formatLargeNumber(trade.coingecko_volume_24h)}</strong>
                          </span>
                          <span>•</span>
                          <span>
                            Market Cap: <strong className="text-foreground font-semibold">${formatLargeNumber(trade.coingecko_market_cap)}</strong>{" "}
                            {trade.coingecko_rank ? <span className="text-primary font-bold">(#{trade.coingecko_rank})</span> : ""}
                          </span>
                        </div>

                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                          <div className="p-3 rounded bg-muted/40 border border-border/50">
                            <div className="text-[10px] text-muted-foreground">Entry Price</div>
                            <div className="font-semibold text-sm">${trade.entry_price?.toLocaleString()}</div>
                          </div>
                          <div className="p-3 rounded bg-muted/40 border border-border/50">
                            <div className="text-[10px] text-muted-foreground">Current Mark Price</div>
                            <div className="font-semibold text-sm">${trade.current_price?.toLocaleString()}</div>
                          </div>
                          <div className="p-3 rounded bg-muted/40 border border-border/50">
                            <div className="text-[10px] text-muted-foreground">Unrealized PnL ($ & ROE %)</div>
                            <div
                              className={cn(
                                "font-bold text-base",
                                (trade.unrealized_pnl_usdt || 0) >= 0 ? "text-emerald-500" : "text-destructive"
                              )}
                            >
                              {(trade.unrealized_pnl_usdt || 0) >= 0 ? "+" : ""}
                              {(trade.unrealized_pnl_usdt || 0).toFixed(4)} USDT (
                              {(trade.unrealized_pnl_pct || 0).toFixed(2)}%)
                            </div>
                          </div>
                          <div className="p-3 rounded bg-muted/40 border border-border/50">
                            <div className="text-[10px] text-muted-foreground">Native Take-Profit / Stop-Loss</div>
                            <div className="font-semibold text-sm">
                              <span className="text-emerald-500">${trade.take_profit_price}</span> /{" "}
                              <span className="text-destructive">${trade.stop_loss_price}</span>
                            </div>
                          </div>
                        </div>

                        {trade.proposal?.why_this_trade && (
                          <div className="p-3 rounded bg-muted/30 border border-border/40 text-xs space-y-1">
                            <div className="font-semibold text-foreground flex items-center justify-between">
                              <span>Strategy Rationale & Expected Edge</span>
                              <span className="text-emerald-500 font-bold">
                                {trade.proposal.why_this_trade.expected_net_edge}
                              </span>
                            </div>
                            <p className="text-muted-foreground text-[11px]">
                              {trade.proposal.strategy_name} ({trade.proposal.market_regime}) —{" "}
                              {trade.proposal.why_this_trade.market_selection}
                            </p>
                          </div>
                        )}

                        {/* 15-Minute TradingView Live Chart Embed */}
                        <div className="pt-2 border-t border-border/50 space-y-2">
                          <div className="flex items-center justify-between text-xs font-semibold text-foreground">
                            <span className="flex items-center gap-1.5">
                              <LineChart className="h-4 w-4 text-primary" />
                              15-Minute Candlestick Chart (TradingView Live Feed)
                            </span>
                            <span className="text-[10px] text-muted-foreground font-mono">TF: 15m | Bitget Futures</span>
                          </div>
                          <div className="h-[280px] w-full rounded-xl border border-border/70 overflow-hidden shadow-inner bg-zinc-950">
                            <iframe
                              title={`TradingView 15m Chart for ${trade.symbol}`}
                              src={`https://s.tradingview.com/widgetembed/?frameElementId=tv_${trade.symbol}&symbol=BITGET%3A${trade.symbol}&interval=15&hidesidetoolbar=1&hidedetachedtoolbar=1&symboledit=0&saveimage=0&toolbarbg=18181b&theme=dark&style=1&timezone=Etc%2FUTC&locale=en`}
                              className="w-full h-full border-0"
                            />
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : activeSession && activeSession.status === "ACTIVE" ? (
                  <div className="p-4 rounded bg-muted/30 border border-border/40 flex flex-col gap-2 text-xs">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <RefreshCw className="h-4 w-4 text-primary animate-spin" />
                        <span className="font-semibold text-foreground">
                          Session is ACTIVE — Autonomous Scanner evaluating Bitget futures candidates...
                        </span>
                      </div>
                      <span className="text-muted-foreground text-[11px]">Scanning 6 liquid candidates</span>
                    </div>
                  </div>
                ) : (
                  <div className="p-4 rounded bg-muted/30 border border-border/40 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-xs">
                    <div>
                      <span className="font-semibold text-foreground">No Active Session Running</span>
                      <p className="text-muted-foreground text-[11px] mt-0.5">
                        Click "Start Session" above to launch autonomous multi-agent scalp trading on Bitget.
                      </p>
                    </div>
                    <button
                      onClick={handleStartSession}
                      className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-primary-foreground font-bold shadow hover:opacity-90 transition-all shrink-0"
                    >
                      <Play className="h-3.5 w-3.5 fill-current" />
                      <span>Start Autonomous Session</span>
                    </button>
                  </div>
                )}
              </div>

              {/* 4. Session Target & Live Performance */}
              <div className="p-5 rounded-xl bg-card border border-border/80 space-y-4 shadow-sm">
                <div className="flex items-center justify-between text-xs font-semibold">
                  <div className="flex items-center gap-3">
                    <span>Session Target & Live Performance</span>
                    {activeSession && activeSession.stats && (
                      <span className="text-[11px] font-normal text-muted-foreground">
                        Trades: {activeSession.stats.total_trades} | Win Rate: {activeSession.stats.win_rate_pct}%
                      </span>
                    )}
                  </div>
                  <span className="text-muted-foreground">
                    Session ID: {activeSession?.session_id || "ses_idle"}
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <div className="flex justify-between text-xs">
                      <span className="text-muted-foreground">
                        Target Profit (+{activeSession?.policy?.target_profit || 5} USDT)
                      </span>
                      <span className="font-semibold text-emerald-500">
                        {liveTotalPnl >= 0 ? `+${liveTotalPnl.toFixed(2)}` : "0.00"} USDT
                      </span>
                    </div>
                    <div className="h-2 rounded-full bg-muted overflow-hidden">
                      <div
                        className="h-full bg-emerald-500 transition-all duration-300"
                        style={{
                          width: `${Math.min(
                            100,
                            Math.max(0, (liveTotalPnl / (activeSession?.policy?.target_profit || 5)) * 100)
                          )}%`,
                        }}
                      />
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <div className="flex justify-between text-xs">
                      <span className="text-muted-foreground">
                        Max Loss Limit (-{activeSession?.policy?.maximum_session_loss || 2} USDT)
                      </span>
                      <span className="font-semibold text-destructive">
                        {liveTotalPnl < 0 ? `${liveTotalPnl.toFixed(2)}` : "0.00"} USDT
                      </span>
                    </div>
                    <div className="h-2 rounded-full bg-muted overflow-hidden">
                      <div
                        className="h-full bg-destructive transition-all duration-300"
                        style={{
                          width: `${Math.min(
                            100,
                            Math.max(
                              0,
                              (Math.abs(Math.min(0, liveTotalPnl)) /
                                (activeSession?.policy?.maximum_session_loss || 2)) *
                                100
                            )
                          )}%`,
                        }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            </>
          );
        })()}

        {/* 5. Completed Trades History (if available) */}
        {recentTrades && recentTrades.length > 0 && (
          <div className="p-5 rounded-xl bg-card border border-border/80 space-y-4 shadow-sm">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-base">Completed Session Trades</h3>
              <span className="text-xs text-muted-foreground">{recentTrades.length} trades recorded</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-border/60 text-muted-foreground font-medium">
                    <th className="pb-2">Symbol</th>
                    <th className="pb-2">Side</th>
                    <th className="pb-2">Entry Price</th>
                    <th className="pb-2">Exit Price</th>
                    <th className="pb-2">Net PnL</th>
                    <th className="pb-2">Status</th>
                    <th className="pb-2 text-right">Reason</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40">
                  {recentTrades.map((t) => (
                    <tr key={t.trade_id} className="hover:bg-muted/40">
                      <td className="py-2.5 font-semibold">{t.symbol}</td>
                      <td className="py-2.5">
                        <span
                          className={cn(
                            "px-2 py-0.5 text-[10px] font-bold rounded",
                            t.direction === "LONG" ? "bg-emerald-500/15 text-emerald-500" : "bg-destructive/15 text-destructive"
                          )}
                        >
                          {t.direction} {t.leverage}x
                        </span>
                      </td>
                      <td className="py-2.5">${t.entry_price}</td>
                      <td className="py-2.5">${t.exit_price || t.current_price}</td>
                      <td className="py-2.5 font-bold">
                        <span className={t.net_pnl_usdt >= 0 ? "text-emerald-500" : "text-destructive"}>
                          {t.net_pnl_usdt >= 0 ? "+" : ""}{t.net_pnl_usdt?.toFixed(4)} USDT
                        </span>
                      </td>
                      <td className="py-2.5 font-medium">{t.status}</td>
                      <td className="py-2.5 text-right text-muted-foreground">{t.exit_reason || "OPEN"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* 5. Realtime Multi-Agent Execution & Decision Stream */}
        <div className="p-5 rounded-xl bg-card border-2 border-primary/30 space-y-4 shadow-sm">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <Bot className="h-5 w-5 text-primary" />
                <h3 className="font-bold text-base">🤖 Multi-Agent Realtime Execution & Decision Stream</h3>
                <span className="px-2 py-0.5 text-[10px] font-bold rounded bg-emerald-500/15 text-emerald-500 animate-pulse">
                  LIVE ENGINE STREAM
                </span>
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                Real-time execution trace of all 4 autonomous agents evaluating indicators, risk edge, news vetoes & execution gates.
              </p>
            </div>

            {/* Agent Filter Tabs */}
            <div className="flex items-center gap-1.5 bg-muted/60 p-1 rounded-lg text-xs overflow-x-auto shrink-0">
              {["ALL", "Scanner", "Strategy", "Risk", "Execution"].map((filter) => (
                <button
                  key={filter}
                  onClick={() => setSelectedAgentFilter(filter)}
                  className={cn(
                    "px-3 py-1 rounded-md font-semibold transition-all shrink-0",
                    selectedAgentFilter === filter
                      ? "bg-background text-foreground shadow-xs"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {filter}
                </button>
              ))}
            </div>
          </div>

          <div className="p-4 rounded-xl bg-zinc-950 border border-zinc-800/80 font-mono text-xs space-y-2.5 max-h-[380px] overflow-y-auto shadow-inner text-zinc-300">
            {agentLogs && agentLogs.length > 0 ? (
              agentLogs
                .filter((log) => {
                  if (selectedAgentFilter === "ALL") return true;
                  if (selectedAgentFilter === "Scanner") return log.agent.includes("Scanner");
                  if (selectedAgentFilter === "Strategy") return log.agent.includes("Strategy");
                  if (selectedAgentFilter === "Risk") return log.agent.includes("Risk");
                  if (selectedAgentFilter === "Execution") return log.agent.includes("Execution");
                  return true;
                })
                .map((log, idx) => (
                  <div
                    key={idx}
                    className="p-2.5 rounded bg-zinc-900/80 border border-zinc-800/60 space-y-1.5 hover:border-zinc-700/60 transition-all"
                  >
                    <div className="flex items-center justify-between flex-wrap gap-2 text-[11px]">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-zinc-500 font-bold">[{log.timestamp}]</span>
                        <span
                          className={cn(
                            "px-2 py-0.5 rounded text-[10px] font-bold border",
                            log.agent.includes("Scanner")
                              ? "bg-blue-500/15 text-blue-400 border-blue-500/30"
                              : log.agent.includes("Strategy")
                              ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30"
                              : log.agent.includes("Risk")
                              ? "bg-amber-500/15 text-amber-400 border-amber-500/30"
                              : "bg-purple-500/15 text-purple-400 border-purple-500/30"
                          )}
                        >
                          {log.agent}
                        </span>
                        <span className="px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300 text-[10px] font-bold">
                          {log.action}
                        </span>
                      </div>
                      <span className="text-zinc-500 text-[10px] font-mono">{log.session_id || "ses_live"}</span>
                    </div>

                    <p className="text-zinc-200 font-medium text-xs pl-1 leading-relaxed">{log.message}</p>

                    {log.details && Object.keys(log.details).length > 0 && (
                      <details className="text-[10px] text-zinc-400 pl-1 pt-1">
                        <summary className="cursor-pointer hover:text-zinc-200 font-semibold select-none">
                          🔍 View Agent Decision Data & Output JSON
                        </summary>
                        <pre className="mt-1.5 p-2 rounded bg-zinc-950 border border-zinc-800 overflow-x-auto text-[10px] text-emerald-400 leading-tight">
                          {JSON.stringify(log.details, null, 2)}
                        </pre>
                      </details>
                    )}
                  </div>
                ))
            ) : (
              <div className="p-6 text-center text-zinc-500 text-xs font-mono space-y-1">
                <RefreshCw className="h-4 w-4 animate-spin mx-auto text-zinc-600 mb-2" />
                <p>Waiting for agent decisions... Multi-agent execution loop runs continuously every cycle.</p>
              </div>
            )}
          </div>
        </div>

        {/* 6. Quantitative Opportunity Scanner */}
        <div className="p-5 rounded-xl bg-card border border-border/80 space-y-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-primary" />
              <h2 className="font-semibold text-base">Quantitative Opportunity Scanner</h2>
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span>Funnel: {funnelCounts.all_markets} scanned → {funnelCounts.passed_liquidity} liquid → {funnelCounts.top_candidates} shortlisted</span>
              <button onClick={loadMarketData} className="p-1 hover:text-foreground">
                <RefreshCw className={cn("h-3.5 w-3.5", loadingCandidates && "animate-spin")} />
              </button>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-border/60 text-muted-foreground font-medium">
                  <th className="pb-2.5">Symbol</th>
                  <th className="pb-2.5">Price</th>
                  <th className="pb-2.5">24h Vol</th>
                  <th className="pb-2.5">Spread</th>
                  <th className="pb-2.5">Opportunity Score</th>
                  <th className="pb-2.5">Regime</th>
                  <th className="pb-2.5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {candidates.map((cand) => (
                  <tr
                    key={cand.symbol}
                    onClick={() => setSelectedSymbol(cand.symbol)}
                    className={cn(
                      "hover:bg-muted/50 transition-colors cursor-pointer",
                      selectedSymbol === cand.symbol && "bg-primary/10 font-medium"
                    )}
                  >
                    <td className="py-3 flex items-center gap-2">
                      <img src={cand.coin_icon} alt="" className="h-5 w-5 rounded-full" />
                      <span className="font-semibold">{cand.symbol}</span>
                    </td>
                    <td className="py-3">${cand.price_usdt?.toLocaleString()}</td>
                    <td className="py-3">${((cand.volume_24h_usdt || 0) / 1000000).toFixed(1)}M</td>
                    <td className="py-3">{cand.bid_ask_spread_bps} bps</td>
                    <td className="py-3">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-primary">{cand.opportunity_score}/100</span>
                        <div className="w-16 h-1.5 rounded-full bg-muted overflow-hidden">
                          <div
                            className="h-full bg-primary"
                            style={{ width: `${cand.opportunity_score}%` }}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="py-3">
                      <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-info/10 text-info">
                        {cand.regime?.primary_regime || "STRONG_DOWNTREND"}
                      </span>
                    </td>
                    <td className="py-3 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedSymbol(cand.symbol);
                        }}
                        className="px-2.5 py-1 rounded bg-muted hover:bg-primary/20 text-xs text-foreground font-medium"
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* 7. Dynamic Market Analysis Detail (for selected symbol) */}
        {symbolDetail && (
          <div className="p-5 rounded-xl bg-card border border-border/80 space-y-4 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <img src={symbolDetail.coin_icon} alt="" className="h-6 w-6 rounded-full" />
                <h3 className="font-bold text-base">{symbolDetail.symbol} Real-Time Analytics</h3>
              </div>
              <span className="text-xs text-muted-foreground">Bitget USDT Futures</span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-xs">
              <div className="p-2.5 rounded bg-muted/40 border border-border/50">
                <div className="text-[10px] text-muted-foreground">EMA 9 / EMA 20</div>
                <div className="font-semibold">${symbolDetail.indicators?.ema9} / ${symbolDetail.indicators?.ema20}</div>
              </div>
              <div className="p-2.5 rounded bg-muted/40 border border-border/50">
                <div className="text-[10px] text-muted-foreground">VWAP</div>
                <div className="font-semibold">${symbolDetail.indicators?.vwap}</div>
              </div>
              <div className="p-2.5 rounded bg-muted/40 border border-border/50">
                <div className="text-[10px] text-muted-foreground">RSI (14)</div>
                <div className="font-semibold">{symbolDetail.indicators?.rsi14}</div>
              </div>
              <div className="p-2.5 rounded bg-muted/40 border border-border/50">
                <div className="text-[10px] text-muted-foreground">ADX (14)</div>
                <div className="font-semibold">{symbolDetail.indicators?.adx14}</div>
              </div>
              <div className="p-2.5 rounded bg-muted/40 border border-border/50">
                <div className="text-[10px] text-muted-foreground">Volume Ratio</div>
                <div className="font-semibold">{symbolDetail.indicators?.volume_ratio_30}x mean</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

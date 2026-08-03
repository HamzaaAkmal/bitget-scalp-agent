import { useEffect, useState } from "react";
import { CoinGlassHeatmapCard } from "@/components/common/CoinGlassHeatmapCard";
import {
  Activity,
  AlertOctagon,
  Bot,
  Brain,
  CheckCircle2,
  Clock,
  Flame,
  History,
  LineChart,
  Play,
  Radar,
  RefreshCw,
  Search,
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
  const [isStopping, setIsStopping] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
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
  const [activeTab, setActiveTab] = useState<"desk" | "verifications" | "history">("desk");
  const [sessionHistory, setSessionHistory] = useState<ScalpSessionData[]>([]);
  const [historySearch, setHistorySearch] = useState("");
  const [loadingHistory, setLoadingHistory] = useState(false);

  const loadSessionHistory = async () => {
    setLoadingHistory(true);
    try {
      const res = await scalpApi.getSessionHistory();
      setSessionHistory(res.sessions || []);
    } catch (err) {
      toast.error("Failed to load session history");
    } finally {
      setLoadingHistory(false);
    }
  };

  // Load active sessions & market candidates on mount
  useEffect(() => {
    loadActiveSession();
    loadMarketData();
    loadSessionHistory();
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
        if (active.status === "ACTIVE") {
          setActiveSession(active);
          const detail = await scalpApi.getSessionDetail(active.session_id);
          if (detail.session && detail.session.status === "ACTIVE") {
            setActiveSession(detail.session);
          } else {
            setActiveSession(null);
          }
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
        } else {
          setActiveSession(null);
        }
      } else {
        setActiveSession(null);
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
    setIsStarting(true);
    try {
      // 1. Ensure clean slate by stopping any lingering session
      await scalpApi.stopAllSessions().catch(() => {});

      let policyToUse = parsedPolicy;
      if (!policyToUse) {
        const parseRes = await scalpApi.parseMission(missionInput);
        policyToUse = parseRes.policy;
        setParsedPolicy(policyToUse);
      }

      policyToUse = { 
        ...policyToUse, 
        autonomy_mode: autonomyMode,
        require_human_approval: requireApproval,
      };

      const createRes = await scalpApi.createSession(missionInput, policyToUse);
      const startRes = await scalpApi.startSession(createRes.session.session_id);
      setActiveSession(startRes.session);
      toast.success(`🚀 Autonomous Scalp Session ${startRes.session.session_id} Started!`);
    } catch (err: any) {
      toast.error(err.message || "Failed to start scalp session");
    } finally {
      setIsStarting(false);
    }
  };

  const handleStopAllSessions = async () => {
    setIsStopping(true);
    try {
      await scalpApi.stopAllSessions();
      setActiveSession(null);
      setActiveTrade(null);
      setActiveTrades([]);
      setPendingProposal(null);
      toast.success(`Stopped all active scalp sessions. Engine reset.`);
      loadSessionHistory();
    } catch (err: any) {
      setActiveSession(null);
      setActiveTrade(null);
      setActiveTrades([]);
      setPendingProposal(null);
      toast.info("Session state reset.");
    } finally {
      setIsStopping(false);
    }
  };

  const handleStopSession = async () => {
    if (!activeSession) {
      setActiveSession(null);
      return;
    }
    setIsStopping(true);
    try {
      await scalpApi.stopSession(activeSession.session_id);
      setActiveSession(null);
      setActiveTrade(null);
      setActiveTrades([]);
      setPendingProposal(null);
      toast.success("Scalp Trading Session Engine Stopped Successfully.");
      loadSessionHistory();
    } catch (err: any) {
      setActiveSession(null);
      setActiveTrade(null);
      setActiveTrades([]);
      setPendingProposal(null);
      toast.info("Scalp Session Engine Halted.");
    } finally {
      setIsStopping(false);
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
      <header className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 p-5 rounded-2xl bg-card border border-border/80 shadow-md">
        <div className="flex items-center gap-3.5">
          <div className="p-3 rounded-xl bg-primary/10 text-primary border border-primary/20 shadow-inner">
            <Radar className="h-7 w-7 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-extrabold tracking-tight bg-gradient-to-r from-foreground via-foreground to-primary bg-clip-text text-transparent">
                AI Scalp Trader
              </h1>
              <span className="px-2.5 py-0.5 text-[11px] font-bold rounded-full bg-primary/15 text-primary border border-primary/30">
                Vibe Autonomous Core v2.0
              </span>
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              Event-Driven Low-Latency Futures Scalping Engine • Direct Bitget Exchange Reconciliation
            </p>
          </div>
        </div>

        {/* Live Status Indicators & Emergency Stop */}
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-muted/80 text-xs font-semibold border border-border/60 shadow-xs">
            <Bot className="h-4 w-4 text-primary" />
            <span className="capitalize">{autonomyMode.replace("_", " ")}</span>
          </div>

          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-500/10 text-emerald-400 text-xs font-semibold border border-emerald-500/20 shadow-xs">
            <ShieldCheck className="h-4 w-4 text-emerald-500" />
            <span>Bitget Futures Account</span>
          </div>

          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-info/10 text-info text-xs font-semibold border border-info/20 shadow-xs">
            <Activity className="h-4 w-4 text-info" />
            <span>Regime: {regimeInfo?.primary_regime || "TRENDING"}</span>
          </div>

          <div
            className={cn(
              "flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-bold border transition-all shadow-xs",
              activeSession?.status === "ACTIVE"
                ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/40"
                : "bg-muted text-muted-foreground border-border"
            )}
          >
            <span className="relative flex h-2.5 w-2.5">
              {activeSession?.status === "ACTIVE" && (
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              )}
              <span
                className={cn(
                  "relative inline-flex rounded-full h-2.5 w-2.5",
                  activeSession?.status === "ACTIVE" ? "bg-emerald-500" : "bg-muted-foreground"
                )}
              ></span>
            </span>
            <span>{activeSession?.status || "STANDBY"}</span>
          </div>

          <button
            onClick={handleStopAllSessions}
            disabled={isStopping}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-muted hover:bg-muted/80 text-foreground text-xs font-bold transition-all border border-border shadow-xs cursor-pointer disabled:opacity-50"
            title="Stop all active scalp trading sessions and reset engine state"
          >
            <RefreshCw className={cn("h-3.5 w-3.5 text-primary", isStopping && "animate-spin")} />
            <span>Reset All Sessions</span>
          </button>

          <button
            onClick={handleEmergencyStop}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-destructive hover:bg-destructive/90 text-destructive-foreground text-xs font-bold transition-all shadow-md active:scale-95 cursor-pointer"
          >
            <AlertOctagon className="h-4 w-4" />
            <span>EMERGENCY STOP</span>
          </button>
        </div>
      </header>

      {/* Sub-Tab Navigation Bar */}
      <div className="flex flex-wrap items-center gap-2 border-b border-border/60 pb-3">
        <button
          onClick={() => setActiveTab("desk")}
          className={cn(
            "flex items-center gap-2 px-4.5 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer shadow-xs",
            activeTab === "desk"
              ? "bg-primary text-primary-foreground shadow-sm"
              : "bg-muted/60 text-muted-foreground hover:text-foreground hover:bg-muted"
          )}
        >
          <Radar className="h-4 w-4" />
          <span>Autonomous Live Scalp Desk</span>
        </button>

        <button
          onClick={() => setActiveTab("verifications")}
          className={cn(
            "flex items-center gap-2 px-4.5 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer shadow-xs relative",
            activeTab === "verifications"
              ? "bg-primary text-primary-foreground shadow-sm"
              : "bg-muted/60 text-muted-foreground hover:text-foreground hover:bg-muted"
          )}
        >
          <ShieldCheck className="h-4 w-4 text-emerald-400" />
          <span>Trade Verifications & Approvals</span>
          {pendingProposal ? (
            <span className="px-2 py-0.5 rounded-full bg-emerald-500 text-zinc-950 text-[10px] font-black animate-pulse">
              1 PENDING
            </span>
          ) : (
            <span className="px-2 py-0.5 rounded-full bg-background/20 text-[10px] font-extrabold opacity-70">
              0
            </span>
          )}
        </button>

        <button
          onClick={() => {
            setActiveTab("history");
            loadSessionHistory();
          }}
          className={cn(
            "flex items-center gap-2 px-4.5 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer shadow-xs",
            activeTab === "history"
              ? "bg-primary text-primary-foreground shadow-sm"
              : "bg-muted/60 text-muted-foreground hover:text-foreground hover:bg-muted"
          )}
        >
          <History className="h-4 w-4" />
          <span>Session History & Audit Trail</span>
          {sessionHistory.length > 0 && (
            <span className="px-2 py-0.5 rounded-full bg-background/20 text-[10px] font-extrabold">
              {sessionHistory.length}
            </span>
          )}
        </button>
      </div>

      {/* Emergency Stop Alert Banner if Active */}
      {emergencyActive && (
        <div className="p-4 rounded-xl bg-destructive/15 border-2 border-destructive text-destructive flex items-center justify-between shadow-lg">
          <div className="flex items-center gap-3">
            <AlertOctagon className="h-6 w-6 shrink-0" />
            <div>
              <h3 className="font-bold text-sm">GLOBAL EMERGENCY STOP IS ACTIVE</h3>
              <p className="text-xs opacity-90">All autonomous execution halted. All pending Bitget orders cancelled.</p>
            </div>
          </div>
          <button
            onClick={async () => {
              await scalpApi.resetEmergencyStop();
              setEmergencyActive(false);
              toast.info("Emergency Stop Reset.");
            }}
            className="px-3.5 py-1.5 rounded-lg bg-background text-xs font-bold hover:bg-muted border border-border transition-all shadow-xs"
          >
            Reset Emergency Stop
          </button>
        </div>
      )}

      {/* Copilot Trade Proposal Approval Banner */}
      {activeSession && activeSession.active_proposal_id && (
        <div className="p-4 rounded-xl bg-primary/15 border-2 border-primary text-foreground flex items-center justify-between shadow-lg backdrop-blur-md">
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
            className="px-5 py-2 rounded-lg bg-primary text-primary-foreground text-xs font-bold shadow-md hover:opacity-90 transition-all flex items-center gap-1.5"
          >
            <CheckCircle2 className="h-4 w-4" />
            <span>Approve & Execute Trade</span>
          </button>
        </div>
      )}

      {activeTab === "verifications" ? (
        /* TRADE VERIFICATIONS & HUMAN APPROVAL GATE VIEW */
        <div className="space-y-6">
          <div className="p-6 rounded-2xl bg-card border-2 border-primary/40 space-y-4 shadow-md backdrop-blur-md">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border/50 pb-4">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-primary/15 text-primary border border-primary/30">
                  <ShieldCheck className="h-6 w-6" />
                </div>
                <div>
                  <h2 className="font-extrabold text-base text-foreground">Trade Verifications & Human Approval Gate</h2>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Verified multi-agent trade proposals requiring human authorization before order submission to Bitget Futures.
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="px-3 py-1 rounded-full text-xs font-extrabold bg-primary/20 text-primary border border-primary/40">
                  {pendingProposal ? "1 Pending Verification" : "0 Pending Verification"}
                </span>
              </div>
            </div>

            {pendingProposal ? (
              <div className="p-6 rounded-2xl bg-zinc-950 border-2 border-primary/50 space-y-6 shadow-xl">
                {/* Trade Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-zinc-800 pb-4">
                  <div className="flex items-center gap-3">
                    <div className={cn(
                      "px-3 py-1.5 rounded-xl text-xs font-black tracking-wider uppercase border",
                      pendingProposal.direction === "LONG" ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/50" : "bg-destructive/20 text-destructive border-destructive/50"
                    )}>
                      {pendingProposal.direction} {pendingProposal.leverage || 5}X
                    </div>
                    <div>
                      <h3 className="text-xl font-extrabold text-white tracking-tight">{pendingProposal.symbol || "BTCUSDT"}</h3>
                      <p className="text-xs text-zinc-400 font-mono">Strategy: {pendingProposal.strategy_name || "Vol-Breakout-Scalp"}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 text-xs">
                    <span className="px-2.5 py-1 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 font-mono">
                      Regime: {pendingProposal.market_regime || "TRENDING"}
                    </span>
                    <span className="px-2.5 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-bold">
                      Confidence: {pendingProposal.confidence || 88}%
                    </span>
                  </div>
                </div>

                {/* Key Price Levels & Margin Metrics Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                  <div className="p-3.5 rounded-xl bg-zinc-900/80 border border-zinc-800">
                    <div className="text-[10px] text-zinc-400 font-semibold uppercase">Required Margin</div>
                    <div className="text-sm font-extrabold text-white mt-1">${pendingProposal.margin_required_usdt || 15.0} USDT</div>
                  </div>
                  <div className="p-3.5 rounded-xl bg-zinc-900/80 border border-zinc-800">
                    <div className="text-[10px] text-zinc-400 font-semibold uppercase">Entry Target Price</div>
                    <div className="text-sm font-extrabold text-white mt-1">${pendingProposal.entry_price || 65000.0}</div>
                  </div>
                  <div className="p-3.5 rounded-xl bg-zinc-900/80 border border-zinc-800">
                    <div className="text-[10px] text-emerald-400 font-semibold uppercase">Take Profit (TP)</div>
                    <div className="text-sm font-extrabold text-emerald-400 mt-1">${pendingProposal.take_profit_1 || pendingProposal.take_profit || 66000.0}</div>
                  </div>
                  <div className="p-3.5 rounded-xl bg-zinc-900/80 border border-zinc-800">
                    <div className="text-[10px] text-destructive font-semibold uppercase">Stop Loss (SL)</div>
                    <div className="text-sm font-extrabold text-destructive mt-1">${pendingProposal.stop_loss || 64500.0}</div>
                  </div>
                </div>

                {/* Agent Reasoning & Risk Checklist */}
                <div className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800 space-y-2 text-xs">
                  <div className="font-bold text-zinc-200 flex items-center gap-2">
                    <Brain className="h-4 w-4 text-primary" />
                    <span>Technical Strategy & Risk Critic Agent Rationale</span>
                  </div>
                  <p className="text-zinc-300 leading-relaxed font-sans">
                    {pendingProposal.why_this_trade?.primary_driver || pendingProposal.reasoning || "Technical momentum breakout confirmed by volume ratio > 1.5x and positive net edge."}
                  </p>
                </div>

                {/* Interactive Approval Action Buttons */}
                <div className="flex flex-col sm:flex-row items-center gap-3 pt-2">
                  <button
                    onClick={async () => {
                      await handleConfirmCopilotTrade();
                      setActiveTab("desk");
                    }}
                    className="w-full sm:w-auto flex-1 px-6 py-3.5 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-zinc-950 font-black text-sm transition-all shadow-lg hover:shadow-emerald-500/20 flex items-center justify-center gap-2 cursor-pointer"
                  >
                    <CheckCircle2 className="h-5 w-5" />
                    <span>APPROVE & PLACE BITGET TRADE NOW</span>
                  </button>
                  <button
                    onClick={() => {
                      setPendingProposal(null);
                      toast.info("Trade proposal rejected & dismissed.");
                    }}
                    className="w-full sm:w-auto px-5 py-3.5 rounded-xl bg-zinc-900 hover:bg-zinc-800 text-zinc-300 font-bold text-xs border border-zinc-800 transition-all cursor-pointer"
                  >
                    REJECT & DISMISS
                  </button>
                </div>
              </div>
            ) : (
              <div className="p-12 rounded-2xl bg-zinc-950/60 border border-zinc-800 text-center space-y-3">
                <ShieldCheck className="h-10 w-10 text-muted-foreground mx-auto opacity-40" />
                <h3 className="font-bold text-base text-foreground">No Pending Trade Proposals for Verification</h3>
                <p className="text-xs text-muted-foreground max-w-md mx-auto">
                  The multi-agent scalp engine is actively scanning Bitget futures markets. When a trade setup passes Technical Strategy and Risk Critic checks, the trade verification card will appear here for your approval.
                </p>
              </div>
            )}
          </div>
        </div>
      ) : activeTab === "history" ? (
        /* SESSION HISTORY & AUDIT TRAIL VIEW */
        <div className="space-y-6">
          {/* History Header Metrics */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-4.5 rounded-2xl bg-card border border-border/80 shadow-xs">
              <div className="text-xs text-muted-foreground">Total Sessions Recorded</div>
              <div className="text-xl font-extrabold text-foreground mt-0.5">{sessionHistory.length} Sessions</div>
            </div>
            <div className="p-4.5 rounded-2xl bg-card border border-border/80 shadow-xs">
              <div className="text-xs text-muted-foreground">Active Sessions</div>
              <div className="text-xl font-extrabold text-primary mt-0.5">
                {sessionHistory.filter((s) => s.status === "ACTIVE").length} Running
              </div>
            </div>
            <div className="p-4.5 rounded-2xl bg-card border border-border/80 shadow-xs">
              <div className="text-xs text-muted-foreground">Cumulative Realized PnL</div>
              {(() => {
                const totalPnl = sessionHistory.reduce((sum, s) => sum + (s.session_pnl_usdt || 0), 0);
                return (
                  <div className={cn("text-xl font-extrabold mt-0.5", totalPnl >= 0 ? "text-emerald-500" : "text-destructive")}>
                    {totalPnl >= 0 ? "+" : ""}{totalPnl.toFixed(4)} USDT
                  </div>
                );
              })()}
            </div>
            <div className="p-4.5 rounded-2xl bg-card border border-border/80 shadow-xs">
              <div className="text-xs text-muted-foreground">Executed Scalp Trades</div>
              <div className="text-xl font-extrabold text-foreground mt-0.5">
                {sessionHistory.reduce((sum, s) => sum + (s.stats?.total_trades || 0), 0)} Trades
              </div>
            </div>
          </div>

          {/* Search & Filter Bar */}
          <div className="p-5 rounded-2xl bg-card border border-border/80 flex flex-col sm:flex-row items-center justify-between gap-3 shadow-xs">
            <div className="relative w-full sm:w-96">
              <Search className="absolute left-3.5 top-3 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search sessions by prompt or ID..."
                value={historySearch}
                onChange={(e) => setHistorySearch(e.target.value)}
                className="w-full pl-10 pr-4 py-2 rounded-xl bg-background border border-border text-xs outline-none focus:ring-2 focus:ring-primary/40"
              />
            </div>

            <button
              onClick={loadSessionHistory}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-muted hover:bg-muted/80 text-xs font-bold transition-all border border-border shrink-0 cursor-pointer"
            >
              <RefreshCw className={cn("h-3.5 w-3.5", loadingHistory && "animate-spin text-primary")} />
              <span>Refresh History</span>
            </button>
          </div>

          {/* Session Cards & Table */}
          <div className="space-y-4">
            {sessionHistory.length > 0 ? (
              sessionHistory
                .filter((s) =>
                  s.session_id.toLowerCase().includes(historySearch.toLowerCase()) ||
                  s.user_mission.toLowerCase().includes(historySearch.toLowerCase())
                )
                .map((sess) => (
                  <div
                    key={sess.session_id}
                    className={cn(
                      "p-5 rounded-2xl bg-card border-2 space-y-4 shadow-sm transition-all hover:border-primary/40",
                      sess.status === "ACTIVE" ? "border-emerald-500/40" : "border-border/80"
                    )}
                  >
                    <div className="flex items-center justify-between flex-wrap gap-2">
                      <div className="flex items-center gap-2.5">
                        <span className="font-mono text-xs font-bold text-foreground bg-muted px-2.5 py-1 rounded-lg border border-border/50">
                          {sess.session_id}
                        </span>
                        <span
                          className={cn(
                            "px-2.5 py-0.5 text-xs font-extrabold rounded-full border",
                            sess.status === "ACTIVE"
                              ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30 animate-pulse"
                              : sess.status === "STOPPED"
                              ? "bg-amber-500/15 text-amber-400 border-amber-500/30"
                              : sess.status === "COMPLETED"
                              ? "bg-blue-500/15 text-blue-400 border-blue-500/30"
                              : "bg-muted text-muted-foreground border-border"
                          )}
                        >
                          {sess.status}
                        </span>
                        <span className="text-xs text-muted-foreground font-mono flex items-center gap-1">
                          <Clock className="h-3.5 w-3.5" />
                          Created: {sess.created_at ? new Date(sess.created_at).toLocaleString() : "N/A"}
                        </span>
                      </div>

                      <div className="flex items-center gap-2">
                        {sess.status === "ACTIVE" && (
                          <button
                            onClick={async () => {
                              await scalpApi.stopSession(sess.session_id);
                              toast.info(`Session ${sess.session_id} stopped.`);
                              loadSessionHistory();
                              loadActiveSession();
                            }}
                            className="px-3.5 py-1.5 rounded-xl bg-destructive text-destructive-foreground text-xs font-bold hover:bg-destructive/90 transition-all cursor-pointer shadow-xs"
                          >
                            Stop Session
                          </button>
                        )}
                        <button
                          onClick={async () => {
                            const detail = await scalpApi.getSessionDetail(sess.session_id);
                            setActiveSession(detail.session);
                            if (detail.active_trades) setActiveTrades(detail.active_trades);
                            setActiveTab("desk");
                            toast.success(`Loaded session ${sess.session_id} on live desk`);
                          }}
                          className="px-4 py-1.5 rounded-xl bg-primary text-primary-foreground text-xs font-bold shadow hover:opacity-90 transition-all cursor-pointer"
                        >
                          Load Session Desk
                        </button>
                      </div>
                    </div>

                    {/* Mission Prompt Box */}
                    <div className="p-3.5 rounded-xl bg-muted/40 border border-border/50 text-xs">
                      <div className="text-[10px] text-muted-foreground font-semibold">User Strategy Mission</div>
                      <p className="text-foreground font-medium mt-0.5 leading-relaxed">{sess.user_mission}</p>
                    </div>

                    {/* Policy & PnL Metrics Grid */}
                    <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-xs">
                      <div className="p-3 rounded-xl bg-muted/30 border border-border/40">
                        <div className="text-[10px] text-muted-foreground">Allocated Capital</div>
                        <div className="font-bold text-foreground">${sess.starting_capital_usdt || sess.policy?.allocated_capital} USDT</div>
                      </div>
                      <div className="p-3 rounded-xl bg-muted/30 border border-border/40">
                        <div className="text-[10px] text-muted-foreground">Target Profit / Max Loss</div>
                        <div className="font-bold">
                          <span className="text-emerald-500">+{sess.policy?.target_profit}</span> /{" "}
                          <span className="text-destructive">-{sess.policy?.maximum_session_loss}</span> USDT
                        </div>
                      </div>
                      <div className="p-3 rounded-xl bg-muted/30 border border-border/40">
                        <div className="text-[10px] text-muted-foreground">Leverage & Margin</div>
                        <div className="font-bold text-foreground">{sess.policy?.maximum_leverage || 3}x Isolated</div>
                      </div>
                      <div className="p-3 rounded-xl bg-muted/30 border border-border/40">
                        <div className="text-[10px] text-muted-foreground">Final Session PnL</div>
                        <div className={cn("font-extrabold text-sm", (sess.session_pnl_usdt || 0) >= 0 ? "text-emerald-500" : "text-destructive")}>
                          {(sess.session_pnl_usdt || 0) >= 0 ? "+" : ""}{(sess.session_pnl_usdt || 0).toFixed(4)} USDT
                        </div>
                      </div>
                      <div className="p-3 rounded-xl bg-muted/30 border border-border/40">
                        <div className="text-[10px] text-muted-foreground">Performance Stats</div>
                        <div className="font-bold text-foreground">
                          {sess.stats?.win_rate_pct || 0}% WR ({sess.stats?.winning_trades || 0}W / {sess.stats?.losing_trades || 0}L)
                        </div>
                      </div>
                    </div>
                  </div>
                ))
            ) : (
              <div className="p-8 rounded-2xl bg-card border border-border/80 text-center space-y-2">
                <History className="h-8 w-8 text-muted-foreground mx-auto opacity-50" />
                <p className="font-bold text-sm text-foreground">No Scalp Sessions Found in History</p>
              </div>
            )}
          </div>
        </div>
      ) : (
        /* LIVE SCALP DESK VIEW */
        <div className="space-y-6">
        {/* 2. Mission Control Policy Builder */}
        <div className="p-6 rounded-2xl bg-card border border-border/80 space-y-5 shadow-sm">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-lg bg-primary/15 text-primary">
                <Sparkles className="h-5 w-5" />
              </div>
              <div>
                <h2 className="font-bold text-base">Natural-Language Scalp Mission Builder</h2>
                <p className="text-xs text-muted-foreground">Define risk budgets, profit targets, leverage and pair filters in natural text</p>
              </div>
            </div>
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
                className="px-3 py-1.5 text-xs rounded-xl bg-muted/70 hover:bg-primary/15 hover:text-primary text-muted-foreground font-semibold transition-all border border-border/50 shadow-xs"
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
            className="w-full p-3.5 rounded-xl bg-background text-sm border border-border focus:ring-2 focus:ring-primary/40 outline-none resize-none shadow-inner"
          />

          {/* Action Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-1.5 bg-muted/60 p-1 rounded-xl text-xs font-semibold border border-border/40">
              <button
                onClick={() => setAutonomyMode("copilot")}
                className={cn(
                  "px-3 py-1.5 rounded-lg transition-all",
                  autonomyMode === "copilot"
                    ? "bg-card text-foreground font-bold shadow-xs"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                1. Copilot Mode
              </button>
              <button
                onClick={() => setAutonomyMode("guarded_autopilot")}
                className={cn(
                  "px-3 py-1.5 rounded-lg transition-all",
                  autonomyMode === "guarded_autopilot"
                    ? "bg-card text-foreground font-bold shadow-xs"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                2. Guarded Autopilot
              </button>
            </div>

            <div className="flex items-center gap-2.5">
              <button
                onClick={handleParseMission}
                disabled={parsing}
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-muted hover:bg-muted/80 text-foreground text-xs font-semibold transition-all border border-border shadow-xs"
              >
                {parsing ? <RefreshCw className="h-4 w-4 animate-spin text-primary" /> : <Brain className="h-4 w-4 text-primary" />}
                <span>Parse Policy</span>
              </button>

              {!activeSession || activeSession.status !== "ACTIVE" ? (
                <button
                  onClick={handleStartSession}
                  disabled={isStarting}
                  className="flex items-center gap-2 px-6 py-2 rounded-xl bg-primary text-primary-foreground text-xs font-bold transition-all shadow-md hover:opacity-90 active:scale-95 disabled:opacity-50 cursor-pointer"
                >
                  {isStarting ? (
                    <RefreshCw className="h-4 w-4 animate-spin fill-current" />
                  ) : (
                    <Play className="h-4 w-4 fill-current" />
                  )}
                  <span>{isStarting ? "Starting Engine..." : "Start Scalp Engine"}</span>
                </button>
              ) : (
                <button
                  onClick={handleStopSession}
                  disabled={isStopping}
                  className="flex items-center gap-2 px-6 py-2 rounded-xl bg-destructive text-destructive-foreground text-xs font-bold transition-all shadow-md hover:opacity-90 disabled:opacity-50 cursor-pointer"
                >
                  {isStopping ? (
                    <RefreshCw className="h-4 w-4 animate-spin fill-current" />
                  ) : (
                    <Square className="h-4 w-4 fill-current" />
                  )}
                  <span>{isStopping ? "Stopping Engine..." : "Stop Engine"}</span>
                </button>
              )}
            </div>
          </div>

          {/* Parsed Policy Preview */}
          {parsedPolicy && (
            <div className="p-4 rounded-xl bg-muted/40 border border-border/80 space-y-3 mt-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-foreground">Enforced Strategy Policy Parameters</span>
                <span className="text-[11px] text-muted-foreground font-mono">Verified Deterministic Risk Rules</span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">
                <div className="p-2.5 rounded-lg bg-card border border-border/60 shadow-xs">
                  <div className="text-[10px] text-muted-foreground">Allocated Capital</div>
                  <div className="font-bold text-sm">${parsedPolicy.allocated_capital} USDT</div>
                </div>
                <div className="p-2.5 rounded-lg bg-card border border-border/60 shadow-xs">
                  <div className="text-[10px] text-muted-foreground">Target Profit</div>
                  <div className="font-bold text-sm text-emerald-500">+{parsedPolicy.target_profit} USDT</div>
                </div>
                <div className="p-2.5 rounded-lg bg-card border border-border/60 shadow-xs">
                  <div className="text-[10px] text-muted-foreground">Max Session Loss</div>
                  <div className="font-bold text-sm text-destructive">-{parsedPolicy.maximum_session_loss} USDT</div>
                </div>
                <div className="p-2.5 rounded-lg bg-card border border-border/60 shadow-xs">
                  <div className="text-[10px] text-muted-foreground">Max Leverage Limit</div>
                  <div className="font-bold text-sm text-primary">{parsedPolicy.maximum_leverage}x Isolated</div>
                </div>
              </div>

              {parsedPolicy.warnings && parsedPolicy.warnings.length > 0 && (
                <div className="space-y-1.5 pt-1">
                  {parsedPolicy.warnings.map((w, idx) => (
                    <div
                      key={idx}
                      className={cn(
                        "p-2.5 rounded-lg text-xs flex items-start gap-2 border",
                        w.level === "critical"
                          ? "bg-destructive/10 text-destructive border-destructive/30"
                          : "bg-amber-500/10 text-amber-500 border-amber-500/30"
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
              {/* Active Session Stats Banner */}
              {activeSession && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="p-4 rounded-xl bg-card border border-border/80 shadow-xs">
                    <div className="text-xs text-muted-foreground">Active Session PnL</div>
                    <div className={cn("text-lg font-extrabold mt-0.5", liveTotalPnl >= 0 ? "text-emerald-500" : "text-destructive")}>
                      {liveTotalPnl >= 0 ? "+" : ""}{liveTotalPnl.toFixed(4)} USDT
                    </div>
                  </div>
                  <div className="p-4 rounded-xl bg-card border border-border/80 shadow-xs">
                    <div className="text-xs text-muted-foreground">Session Win Rate</div>
                    <div className="text-lg font-extrabold text-foreground mt-0.5">
                      {activeSession.stats?.win_rate_pct || 0}% ({activeSession.stats?.winning_trades || 0}W / {activeSession.stats?.losing_trades || 0}L)
                    </div>
                  </div>
                  <div className="p-4 rounded-xl bg-card border border-border/80 shadow-xs">
                    <div className="text-xs text-muted-foreground">Active Positions</div>
                    <div className="text-lg font-extrabold text-primary mt-0.5">
                      {openPositionsList.length} Open Position{openPositionsList.length === 1 ? "" : "s"}
                    </div>
                  </div>
                  <div className="p-4 rounded-xl bg-card border border-border/80 shadow-xs">
                    <div className="text-xs text-muted-foreground">Current Capital</div>
                    <div className="text-lg font-extrabold text-foreground mt-0.5">
                      ${(activeSession.current_capital_usdt || 0).toFixed(2)} USDT
                    </div>
                  </div>
                </div>
              )}

              <div className="p-6 rounded-2xl bg-card border-2 border-primary/40 space-y-5 shadow-md">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5">
                    <div className="p-2 rounded-lg bg-primary/15 text-primary">
                      <Flame className="h-5 w-5 animate-bounce" />
                    </div>
                    <h3 className="font-extrabold text-lg tracking-tight">
                      Active Futures Positions & Live Trade Desk ({openPositionsList.length} Active)
                    </h3>
                  </div>

                  {/* Human Approval Toggle Switch */}
                  <div className="flex items-center gap-2.5 px-3.5 py-1.5 rounded-xl bg-muted/60 border border-border/60 text-xs shrink-0 shadow-xs">
                    <ShieldAlert className={cn("h-4 w-4", requireApproval ? "text-primary animate-pulse" : "text-muted-foreground")} />
                    <span className="font-bold text-foreground">Require Human Approval</span>
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
                  <div className="p-5 rounded-2xl bg-primary/10 border-2 border-primary/60 space-y-4 shadow-lg animate-pulse">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <ShieldAlert className="h-5 w-5 text-primary" />
                        <span className="font-bold text-sm text-foreground">
                          🚨 TRADE PROPOSAL APPROVAL REQUIRED (Human Approval Gate ON)
                        </span>
                      </div>
                      <span className="text-xs font-bold px-2.5 py-0.5 rounded-lg bg-primary/20 text-primary border border-primary/40">
                        Setup Quality: {pendingProposal.setup_quality_score || 85}%
                      </span>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs bg-card/90 p-3.5 rounded-xl border border-border/60">
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
                      <div
                        key={trade.trade_id || idx}
                        className="p-5 rounded-2xl bg-gradient-to-br from-card via-card to-muted/20 border-2 border-border/90 space-y-4 shadow-md hover:border-primary/40 transition-all"
                      >
                        <div className="flex items-center justify-between flex-wrap gap-3">
                          <div className="flex items-center gap-3">
                            {trade.coin_icon ? (
                              <img
                                src={trade.coin_icon}
                                alt={trade.symbol}
                                className="h-7 w-7 rounded-full object-cover border border-border/50 shrink-0 shadow-xs"
                                onError={(e) => {
                                  (e.target as HTMLImageElement).src = "https://assets.coingecko.com/coins/images/1/large/bitcoin.png";
                                }}
                              />
                            ) : (
                              <div className="h-7 w-7 rounded-full bg-primary/20 flex items-center justify-center font-bold text-xs text-primary shrink-0">
                                {trade.symbol.slice(0, 3)}
                              </div>
                            )}
                            <div className="flex items-center gap-2">
                              <span
                                className={cn(
                                  "px-3 py-1 text-xs font-extrabold rounded-lg shadow-xs",
                                  trade.direction === "LONG"
                                    ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                                    : "bg-destructive/15 text-destructive border border-destructive/30"
                                )}
                              >
                                {trade.symbol} {trade.direction} {trade.leverage}x Isolated
                              </span>
                              <span className="text-[11px] px-2 py-0.5 rounded bg-muted text-muted-foreground font-mono">
                                Bitget Verified
                              </span>
                            </div>
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
                            className="px-4 py-1.5 rounded-xl bg-destructive text-destructive-foreground text-xs font-bold hover:bg-destructive/90 disabled:opacity-50 transition-all shadow-sm cursor-pointer"
                          >
                            {isClosing ? "Closing..." : "Close Position"}
                          </button>
                        </div>

                        {/* CoinGecko Market Metrics Bar */}
                        <div className="flex items-center gap-3 text-xs bg-muted/50 p-3 rounded-xl border border-border/50 text-muted-foreground flex-wrap shadow-inner">
                          <span className="font-bold text-foreground flex items-center gap-1 shrink-0">
                            🦎 CoinGecko Live Metrics:
                          </span>
                          <span>
                            24h Vol: <strong className="text-foreground font-bold">${formatLargeNumber(trade.coingecko_volume_24h)}</strong>
                          </span>
                          <span>•</span>
                          <span>
                            Market Cap: <strong className="text-foreground font-bold">${formatLargeNumber(trade.coingecko_market_cap)}</strong>{" "}
                            {trade.coingecko_rank ? <span className="text-primary font-bold">(Rank #{trade.coingecko_rank})</span> : ""}
                          </span>
                        </div>

                        {/* Position Metrics Grid */}
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                          <div className="p-3.5 rounded-xl bg-card border border-border/60 shadow-xs">
                            <div className="text-[10px] text-muted-foreground">Entry Price</div>
                            <div className="font-bold text-sm text-foreground">${trade.entry_price?.toLocaleString()}</div>
                          </div>
                          <div className="p-3.5 rounded-xl bg-card border border-border/60 shadow-xs">
                            <div className="text-[10px] text-muted-foreground">Current Mark Price</div>
                            <div className="font-bold text-sm text-foreground">${trade.current_price?.toLocaleString()}</div>
                          </div>
                          <div className="p-3.5 rounded-xl bg-card border border-border/60 shadow-xs">
                            <div className="text-[10px] text-muted-foreground">Unrealized PnL ($ & ROE %)</div>
                            <div
                              className={cn(
                                "font-extrabold text-base",
                                (trade.unrealized_pnl_usdt || 0) >= 0 ? "text-emerald-500" : "text-destructive"
                              )}
                            >
                              {(trade.unrealized_pnl_usdt || 0) >= 0 ? "+" : ""}
                              {(trade.unrealized_pnl_usdt || 0).toFixed(4)} USDT (
                              {(trade.unrealized_pnl_pct || 0).toFixed(2)}%)
                            </div>
                          </div>
                          <div className="p-3.5 rounded-xl bg-card border border-border/60 shadow-xs">
                            <div className="text-[10px] text-muted-foreground">Take-Profit / Stop-Loss</div>
                            <div className="font-bold text-sm">
                              <span className="text-emerald-500">${trade.take_profit_price}</span> /{" "}
                              <span className="text-destructive">${trade.stop_loss_price}</span>
                            </div>
                          </div>
                        </div>

                        {trade.proposal?.why_this_trade && (
                          <div className="p-3.5 rounded-xl bg-muted/40 border border-border/50 text-xs space-y-1">
                            <div className="font-semibold text-foreground flex items-center justify-between">
                              <span>Strategy Rationale & Edge</span>
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
                        <div className="pt-2 border-t border-border/60 space-y-2.5">
                          <div className="flex items-center justify-between text-xs font-bold text-foreground">
                            <span className="flex items-center gap-2">
                              <LineChart className="h-4 w-4 text-primary" />
                              15-Minute Candlestick Chart (TradingView Live Feed)
                            </span>
                            <span className="text-[10px] text-muted-foreground font-mono">TF: 15m | Bitget Futures</span>
                          </div>
                          <div className="h-[290px] w-full rounded-2xl border border-border/80 overflow-hidden shadow-inner bg-zinc-950">
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
                  <div className="p-6 rounded-xl bg-muted/30 border border-border/40 flex flex-col gap-2 text-xs">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <RefreshCw className="h-4 w-4 text-primary animate-spin" />
                        <span className="font-bold text-foreground">
                          Session is ACTIVE — Autonomous Scanner evaluating Bitget futures candidates...
                        </span>
                      </div>
                      <span className="text-emerald-500 font-mono text-[11px]">Cycle: 3s</span>
                    </div>
                    <p className="text-muted-foreground text-[11px]">
                      The multi-agent system is actively reading indicator edges, checking news vetoes, and computing net expected profit. When a setup meets all strategy thresholds, a trade will open.
                    </p>
                  </div>
                ) : (
                  <div className="p-8 rounded-xl bg-muted/20 border border-border/40 text-center space-y-2">
                    <Bot className="h-8 w-8 text-muted-foreground mx-auto opacity-50" />
                    <p className="font-bold text-sm text-foreground">No Open Scalp Positions Currently Active</p>
                    <p className="text-xs text-muted-foreground max-w-md mx-auto">
                      Click <strong>"Start Scalp Engine"</strong> above to launch the autonomous multi-agent scanner and begin live execution on Bitget.
                    </p>
                  </div>
                )}
              </div>
            </>
          );
        })()}

        {/* 4. Completed Trades History (if available) */}
        {recentTrades && recentTrades.length > 0 && (
          <div className="p-6 rounded-2xl bg-card border border-border/80 space-y-4 shadow-sm">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-base">Completed Session Trades</h3>
              <span className="text-xs text-muted-foreground font-mono">{recentTrades.length} trades recorded</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-border/60 text-muted-foreground font-medium">
                    <th className="pb-2.5">Symbol</th>
                    <th className="pb-2.5">Side</th>
                    <th className="pb-2.5">Entry Price</th>
                    <th className="pb-2.5">Exit Price</th>
                    <th className="pb-2.5">Net PnL</th>
                    <th className="pb-2.5">Status</th>
                    <th className="pb-2.5 text-right">Reason</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40">
                  {recentTrades.map((t) => (
                    <tr key={t.trade_id} className="hover:bg-muted/40 transition-colors">
                      <td className="py-3 font-bold">{t.symbol}</td>
                      <td className="py-3">
                        <span
                          className={cn(
                            "px-2.5 py-0.5 text-[10px] font-bold rounded-md",
                            t.direction === "LONG" ? "bg-emerald-500/15 text-emerald-500" : "bg-destructive/15 text-destructive"
                          )}
                        >
                          {t.direction} {t.leverage}x
                        </span>
                      </td>
                      <td className="py-3">${t.entry_price}</td>
                      <td className="py-3">${t.exit_price || t.current_price}</td>
                      <td className="py-3 font-bold">
                        <span className={t.net_pnl_usdt >= 0 ? "text-emerald-500" : "text-destructive"}>
                          {t.net_pnl_usdt >= 0 ? "+" : ""}{t.net_pnl_usdt?.toFixed(4)} USDT
                        </span>
                      </td>
                      <td className="py-3 font-semibold">{t.status}</td>
                      <td className="py-3 text-right text-muted-foreground font-mono">{t.exit_reason || "CLOSED"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* 5. Realtime Multi-Agent Execution & Decision Stream */}
        <div className="p-6 rounded-2xl bg-card border-2 border-primary/30 space-y-4 shadow-md">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <Bot className="h-5 w-5 text-primary" />
                <h3 className="font-extrabold text-base">🤖 Multi-Agent Realtime Execution & Decision Stream</h3>
                <span className="px-2.5 py-0.5 text-[10px] font-extrabold rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 animate-pulse">
                  LIVE ENGINE STREAM
                </span>
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                Real-time execution trace of all 4 autonomous agents evaluating indicators, risk edge, news vetoes & execution gates.
              </p>
            </div>

            {/* Agent Filter Tabs */}
            <div className="flex items-center gap-1.5 bg-muted/70 p-1 rounded-xl text-xs overflow-x-auto shrink-0 border border-border/50">
              {["ALL", "Scanner", "Strategy", "Risk", "Execution"].map((filter) => (
                <button
                  key={filter}
                  onClick={() => setSelectedAgentFilter(filter)}
                  className={cn(
                    "px-3 py-1 rounded-lg font-bold transition-all shrink-0 cursor-pointer",
                    selectedAgentFilter === filter
                      ? "bg-card text-foreground shadow-xs"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {filter}
                </button>
              ))}
            </div>
          </div>

          <div className="p-4.5 rounded-2xl bg-zinc-950 border border-zinc-800/90 font-mono text-xs space-y-2.5 max-h-[380px] overflow-y-auto shadow-inner text-zinc-300">
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
                    className="p-3 rounded-xl bg-zinc-900/90 border border-zinc-800/70 space-y-1.5 hover:border-zinc-700/80 transition-all shadow-xs"
                  >
                    <div className="flex items-center justify-between flex-wrap gap-2 text-[11px]">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-zinc-500 font-bold">[{log.timestamp}]</span>
                        <span
                          className={cn(
                            "px-2.5 py-0.5 rounded-md text-[10px] font-bold border",
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
                        <span className="px-2 py-0.5 rounded-md bg-zinc-800 text-zinc-300 text-[10px] font-bold">
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
                        <pre className="mt-1.5 p-2.5 rounded-lg bg-zinc-950 border border-zinc-800 overflow-x-auto text-[10px] text-emerald-400 leading-tight">
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
        <div className="p-6 rounded-2xl bg-card border border-border/80 space-y-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="p-2 rounded-lg bg-primary/15 text-primary">
                <Zap className="h-5 w-5" />
              </div>
              <h2 className="font-bold text-base">Quantitative Opportunity Scanner</h2>
            </div>
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <span className="font-semibold text-foreground">
                Candidates: {candidates.length} Scanned
              </span>
              <button
                onClick={loadMarketData}
                className="p-1.5 rounded-lg bg-muted hover:bg-muted/80 text-foreground transition-all cursor-pointer"
              >
                <RefreshCw className={cn("h-4 w-4", loadingCandidates && "animate-spin text-primary")} />
              </button>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-border/60 text-muted-foreground font-medium">
                  <th className="pb-3">Symbol</th>
                  <th className="pb-3">Price</th>
                  <th className="pb-3">24h Vol</th>
                  <th className="pb-3">Spread</th>
                  <th className="pb-3">Opportunity Score</th>
                  <th className="pb-3">Regime</th>
                  <th className="pb-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {candidates.map((cand) => (
                  <tr
                    key={cand.symbol}
                    onClick={() => setSelectedSymbol(cand.symbol)}
                    className={cn(
                      "hover:bg-muted/50 transition-colors cursor-pointer",
                      selectedSymbol === cand.symbol && "bg-primary/10 font-bold"
                    )}
                  >
                    <td className="py-3 flex items-center gap-2.5">
                      <img src={cand.coin_icon} alt="" className="h-6 w-6 rounded-full shrink-0 border border-border/40" />
                      <span className="font-bold">{cand.symbol}</span>
                    </td>
                    <td className="py-3 font-semibold">${cand.price_usdt?.toLocaleString()}</td>
                    <td className="py-3 font-semibold">${((cand.volume_24h_usdt || 0) / 1000000).toFixed(1)}M</td>
                    <td className="py-3 font-mono">{cand.bid_ask_spread_bps} bps</td>
                    <td className="py-3">
                      <div className="flex items-center gap-2.5">
                        <span className="font-extrabold text-primary">{cand.opportunity_score}/100</span>
                        <div className="w-20 h-2 rounded-full bg-muted overflow-hidden">
                          <div
                            className="h-full bg-primary rounded-full"
                            style={{ width: `${cand.opportunity_score}%` }}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="py-3">
                      <span className="px-2.5 py-0.5 rounded-md text-[10px] font-bold bg-info/10 text-info border border-info/20">
                        {cand.regime?.primary_regime || "TRENDING"}
                      </span>
                    </td>
                    <td className="py-3 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedSymbol(cand.symbol);
                        }}
                        className="px-3 py-1 rounded-lg bg-muted hover:bg-primary/20 text-xs text-foreground font-semibold transition-all cursor-pointer"
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
          <div className="p-6 rounded-2xl bg-card border border-border/80 space-y-4 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <img src={symbolDetail.coin_icon} alt="" className="h-6 w-6 rounded-full shrink-0" />
                <h3 className="font-extrabold text-base">{symbolDetail.symbol} Real-Time Indicator Analytics</h3>
              </div>
              <span className="text-xs text-muted-foreground font-mono">Bitget USDT Futures</span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-xs">
              <div className="p-3 rounded-xl bg-muted/40 border border-border/50 shadow-xs">
                <div className="text-[10px] text-muted-foreground">EMA 9 / EMA 20</div>
                <div className="font-bold text-foreground mt-0.5">${symbolDetail.indicators?.ema9} / ${symbolDetail.indicators?.ema20}</div>
              </div>
              <div className="p-3 rounded-xl bg-muted/40 border border-border/50 shadow-xs">
                <div className="text-[10px] text-muted-foreground">VWAP</div>
                <div className="font-bold text-foreground mt-0.5">${symbolDetail.indicators?.vwap}</div>
              </div>
              <div className="p-3 rounded-xl bg-muted/40 border border-border/50 shadow-xs">
                <div className="text-[10px] text-muted-foreground">RSI (14)</div>
                <div className="font-bold text-foreground mt-0.5">{symbolDetail.indicators?.rsi14}</div>
              </div>
              <div className="p-3 rounded-xl bg-muted/40 border border-border/50 shadow-xs">
                <div className="text-[10px] text-muted-foreground">ADX (14)</div>
                <div className="font-bold text-foreground mt-0.5">{symbolDetail.indicators?.adx14}</div>
              </div>
              <div className="p-3 rounded-xl bg-muted/40 border border-border/50 shadow-xs">
                <div className="text-[10px] text-muted-foreground">Volume Ratio</div>
                <div className="font-bold text-foreground mt-0.5">{symbolDetail.indicators?.volume_ratio_30}x mean</div>
              </div>
            </div>
          </div>
        )}

        {/* 8. CoinGlass Liquidation Heatmap Embed (Memoized to prevent lag) */}
        <CoinGlassHeatmapCard symbol={selectedSymbol} />
      </div>
      )}
    </div>
  );
}

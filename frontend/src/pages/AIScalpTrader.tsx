import { useEffect, useState } from "react";
import {
  Activity,
  AlertOctagon,
  Bot,
  Brain,
  Flame,
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

export function AIScalpTrader() {
  const [missionInput, setMissionInput] = useState(PRESET_MISSIONS[0].text);
  const [parsing, setParsing] = useState(false);
  const [parsedPolicy, setParsedPolicy] = useState<SessionPolicy | null>(null);
  const [activeSession, setActiveSession] = useState<ScalpSessionData | null>(null);
  const [activeTrade, setActiveTrade] = useState<ScalpTrade | null>(null);
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
  const [autonomyMode, setAutonomyMode] = useState<"copilot" | "guarded_autopilot" | "full_autonomous">("guarded_autopilot");

  // Initial candidate scan & market regime fetch
  useEffect(() => {
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

  // Session status poll
  useEffect(() => {
    if (!activeSession || activeSession.status !== "ACTIVE") return;
    const sessionInterval = setInterval(async () => {
      try {
        const res = await scalpApi.getSessionDetail(activeSession.session_id);
        setActiveSession(res.session);
        if (res.active_trade) {
          setActiveTrade(res.active_trade);
        } else {
          setActiveTrade(null);
        }
      } catch (err) {
        /* best-effort poll */
      }
    }, 2000);
    return () => clearInterval(sessionInterval);
  }, [activeSession]);

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

      // Ensure active selected autonomy mode is applied
      policyToUse = { ...policyToUse, autonomy_mode: autonomyMode };

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
      setActiveTrade(null);
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
      setActiveTrade(null);
      toast.error(`🚨 EMERGENCY STOP ACTIVATED: ${res.message}`);
    } catch (err: any) {
      toast.error(err.message || "Emergency stop failed");
    }
  };

  const handleConfirmCopilotTrade = async () => {
    if (!activeSession) return;
    try {
      const res = await scalpApi.confirmCopilotTrade(activeSession.session_id);
      toast.success(res.message);
    } catch (err: any) {
      toast.error(err.message || "Failed to confirm trade");
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

          {activeSession && (
            <div
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border",
                activeSession.status === "ACTIVE"
                  ? "bg-emerald-500/15 text-emerald-500 border-emerald-500/30"
                  : "bg-muted text-muted-foreground border-border"
              )}
            >
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <span>{activeSession.status}</span>
            </div>
          )}

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

        {/* 3. Session Target & Risk Progress Bar */}
        {activeSession && (
          <div className="p-5 rounded-xl bg-card border border-border/80 space-y-4 shadow-sm">
            <div className="flex items-center justify-between text-xs font-semibold">
              <span>Session Target & Risk Limits</span>
              <span className="text-muted-foreground">Session ID: {activeSession.session_id}</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">Target Profit (+{activeSession.policy.target_profit} USDT)</span>
                  <span className="font-semibold text-emerald-500">
                    {activeSession.session_pnl_usdt >= 0 ? `+${activeSession.session_pnl_usdt.toFixed(2)}` : "0.00"} USDT
                  </span>
                </div>
                <div className="h-2 rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full bg-emerald-500 transition-all duration-300"
                    style={{
                      width: `${Math.min(100, Math.max(0, (activeSession.session_pnl_usdt / activeSession.policy.target_profit) * 100))}%`,
                    }}
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">Max Loss Limit (-{activeSession.policy.maximum_session_loss} USDT)</span>
                  <span className="font-semibold text-destructive">
                    {activeSession.session_pnl_usdt < 0 ? `${activeSession.session_pnl_usdt.toFixed(2)}` : "0.00"} USDT
                  </span>
                </div>
                <div className="h-2 rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full bg-destructive transition-all duration-300"
                    style={{
                      width: `${Math.min(100, Math.max(0, (Math.abs(Math.min(0, activeSession.session_pnl_usdt)) / activeSession.policy.maximum_session_loss) * 100))}%`,
                    }}
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 4. Active Position Panel (if open) */}
        {activeTrade && (
          <div className="p-5 rounded-xl bg-card border-2 border-primary/50 space-y-4 shadow-md">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Flame className="h-5 w-5 text-primary animate-bounce" />
                <h3 className="font-bold text-base">Active Futures Position</h3>
                <span
                  className={cn(
                    "px-2 py-0.5 text-xs font-bold rounded",
                    activeTrade.direction === "LONG"
                      ? "bg-emerald-500/15 text-emerald-500"
                      : "bg-destructive/15 text-destructive"
                  )}
                >
                  {activeTrade.direction} {activeTrade.leverage}x
                </span>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">ID: {activeTrade.trade_id}</span>
                <button
                  onClick={async () => {
                    await scalpApi.closePosition(activeTrade.trade_id);
                    toast.info("Manual Close Requested");
                  }}
                  className="px-3 py-1 rounded bg-destructive text-destructive-foreground text-xs font-bold hover:bg-destructive/90"
                >
                  Close Position
                </button>
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="p-2.5 rounded bg-muted/40 border border-border/50">
                <div className="text-[10px] text-muted-foreground">Entry Price</div>
                <div className="font-semibold">${activeTrade.entry_price.toLocaleString()}</div>
              </div>
              <div className="p-2.5 rounded bg-muted/40 border border-border/50">
                <div className="text-[10px] text-muted-foreground">Current Price</div>
                <div className="font-semibold">${activeTrade.current_price.toLocaleString()}</div>
              </div>
              <div className="p-2.5 rounded bg-muted/40 border border-border/50">
                <div className="text-[10px] text-muted-foreground">Unrealized PnL</div>
                <div
                  className={cn(
                    "font-bold text-sm",
                    activeTrade.unrealized_pnl_usdt >= 0 ? "text-emerald-500" : "text-destructive"
                  )}
                >
                  {activeTrade.unrealized_pnl_usdt >= 0 ? "+" : ""}
                  {activeTrade.unrealized_pnl_usdt.toFixed(2)} USDT ({activeTrade.unrealized_pnl_pct.toFixed(1)}%)
                </div>
              </div>
              <div className="p-2.5 rounded bg-muted/40 border border-border/50">
                <div className="text-[10px] text-muted-foreground">Native TP / SL</div>
                <div className="font-semibold">
                  <span className="text-emerald-500">${activeTrade.take_profit_price}</span> /{" "}
                  <span className="text-destructive">${activeTrade.stop_loss_price}</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 5. Quantitative Opportunity Scanner */}
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
                    <td className="py-3">${cand.price_usdt.toLocaleString()}</td>
                    <td className="py-3">${(cand.volume_24h_usdt / 1000000).toFixed(1)}M</td>
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

        {/* 6. Dynamic Market Analysis Detail (for selected symbol) */}
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

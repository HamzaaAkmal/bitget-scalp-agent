import { authHeaders } from "@/lib/apiAuth";

const BASE = "";

export interface SessionPolicy {
  autonomy_mode: "copilot" | "guarded_autopilot" | "full_autonomous";
  allocated_capital: number;
  target_profit: number;
  target_final_balance: number;
  target_classification: string;
  maximum_session_loss: number;
  maximum_daily_loss: number;
  maximum_duration_minutes: number;
  allowed_symbols: string[];
  excluded_symbols: string[];
  market_type: string;
  margin_mode: string;
  maximum_leverage: number;
  hard_max_leverage: number;
  maximum_margin_per_trade: number;
  risk_per_trade_usdt: number;
  risk_per_trade_percent: number;
  maximum_concurrent_positions: number;
  maximum_consecutive_losses: number;
  minimum_setup_quality_score: number;
  minimum_historical_edge: boolean;
  minimum_risk_reward: number;
  allowed_strategy_templates: string[];
  preferred_timeframes: string[];
  trade_cooldown_seconds: number;
  allowed_session_hours: number[];
  news_research_requirement: boolean;
  automatic_early_exit_permission: boolean;
  partial_profit_permission: boolean;
  trailing_stop_permission: boolean;
  exchange_native_sl_required: boolean;
  exchange_native_tp_required: boolean;
  exa_critical_event_check_required: boolean;
  warnings: Array<{
    level: string;
    code: string;
    message: string;
    impact: string;
  }>;
}

export interface ScalpSessionData {
  session_id: string;
  user_mission: string;
  policy: SessionPolicy;
  status: string;
  starting_capital_usdt: number;
  current_capital_usdt: number;
  session_pnl_usdt: number;
  session_pnl_pct: number;
  active_position_id?: string;
  active_proposal_id?: string;
  created_at: string;
  started_at?: string;
  stopped_at?: string;
  stop_reason?: string;
  stats: {
    total_trades: number;
    winning_trades: number;
    losing_trades: number;
    win_rate_pct: number;
    net_pnl_usdt: number;
    gross_pnl_usdt: number;
    total_fees_usdt: number;
    total_funding_usdt: number;
    total_slippage_usdt: number;
    profit_factor: number;
    max_drawdown_usdt: number;
    max_drawdown_pct: number;
    average_win_usdt: number;
    average_loss_usdt: number;
    consecutive_losses: number;
    current_risk_multiplier: number;
  };
}

export interface ScalpCandidate {
  symbol: string;
  coin_name: string;
  coin_icon: string;
  price_usdt: number;
  volume_24h_usdt: number;
  bid_ask_spread_bps: number;
  funding_rate: number;
  opportunity_score: number;
  regime: {
    primary_regime: string;
    confidence: number;
    reasoning: string[];
  };
  score_breakdown: {
    liquidity_quality: number;
    volume_anomaly: number;
    spread_quality: number;
    volatility_suitability: number;
    open_interest_change: number;
    market_structure_quality: number;
    catalyst_context: number;
  };
  eligible_strategies: string[];
  funnel_stage: string;
  passed_filters: boolean;
}

export interface TradeProposal {
  proposal_id: string;
  symbol: string;
  coin_name: string;
  coin_icon: string;
  strategy_id: string;
  strategy_name: string;
  market_regime: string;
  direction: "LONG" | "SHORT" | "WAIT";
  timeframe: string;
  entry_price: number;
  stop_loss: number;
  take_profit_1: number;
  take_profit_2?: number;
  leverage: number;
  margin_mode: string;
  position_size_usdt: number;
  margin_required_usdt: number;
  risk_amount_usdt: number;
  risk_percent: number;
  estimated_liquidation_price: number;
  liquidation_distance_percent: number;
  setup_quality_score: number;
  net_edge: {
    expected_gross_profit_usdt: number;
    estimated_entry_fee_usdt: number;
    estimated_exit_fee_usdt: number;
    estimated_slippage_usdt: number;
    estimated_spread_cost_usdt: number;
    estimated_funding_cost_usdt: number;
    expected_net_profit_usdt: number;
    expected_net_reward_risk_ratio: number;
    has_positive_edge: boolean;
  };
  why_this_trade: Record<string, any>;
  status: string;
  rejection_reason?: string;
  created_at: string;
}

export interface ScalpTrade {
  trade_id: string;
  session_id: string;
  proposal: TradeProposal;
  symbol: string;
  direction: "LONG" | "SHORT";
  leverage: number;
  margin_mode: string;
  margin_usdt: number;
  position_size_usdt: number;
  entry_price: number;
  fill_time: string;
  stop_loss_price: number;
  take_profit_price: number;
  current_price: number;
  unrealized_pnl_usdt: number;
  unrealized_pnl_pct: number;
  max_favorable_excursion_pct: number;
  max_adverse_excursion_pct: number;
  liquidation_price: number;
  status: "OPEN" | "CLOSED" | "CANCELLED";
  exit_price?: number;
  exit_time?: string;
  exit_reason?: string;
  net_pnl_usdt: number;
  timeline_events: Array<{ timestamp: string; event: string; details: string }>;
}

async function scalpRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const { headers, ...rest } = options ?? {};
  const mergedHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    ...authHeaders(),
  };
  if (headers) {
    new Headers(headers).forEach((val, key) => {
      mergedHeaders[key] = val;
    });
  }
  const res = await fetch(`${BASE}${path}`, { headers: mergedHeaders, ...rest });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const b = await res.json();
      msg = b.detail || b.message || msg;
    } catch { /* ignore */ }
    throw new Error(msg);
  }
  return res.json();
}

export const scalpApi = {
  getActiveSessions: () =>
    scalpRequest<{ status: string; active_sessions: ScalpSessionData[] }>("/scalp/sessions"),

  parseMission: (user_mission: string) =>
    scalpRequest<{ status: string; policy: SessionPolicy; warnings: any[] }>("/scalp/sessions/parse", {
      method: "POST",
      body: JSON.stringify({ user_mission }),
    }),

  createSession: (user_mission: string, custom_policy?: any) =>
    scalpRequest<{ status: string; session: ScalpSessionData }>("/scalp/sessions", {
      method: "POST",
      body: JSON.stringify({ user_mission, custom_policy }),
    }),

  startSession: (session_id: string) =>
    scalpRequest<{ status: string; session: ScalpSessionData }>(`/scalp/sessions/${session_id}/start`, {
      method: "POST",
    }),

  stopSession: (session_id: string) =>
    scalpRequest<{ status: string; session: ScalpSessionData }>(`/scalp/sessions/${session_id}/stop`, {
      method: "POST",
    }),

  getSessionDetail: (session_id: string) =>
    scalpRequest<{
      status: string;
      session: ScalpSessionData;
      active_trade?: ScalpTrade;
      latest_cycle?: any;
    }>(`/scalp/sessions/${session_id}`),

  getMarketCandidates: () =>
    scalpRequest<{
      status: string;
      data: {
        funnel_counts: { all_markets: number; passed_liquidity: number; passed_technical: number; top_candidates: number };
        candidates: ScalpCandidate[];
      };
    }>("/scalp/market/candidates"),

  getMarketDetail: (symbol: string) =>
    scalpRequest<{
      status: string;
      symbol: string;
      coin_icon: string;
      indicators: any;
      regime: any;
      bars: any[];
    }>(`/scalp/market/${symbol}`),

  getResearchDetail: (symbol: string) =>
    scalpRequest<{ status: string; research: any }>(`/scalp/research/${symbol}`),

  getMarketRegime: () =>
    scalpRequest<{ status: string; regime: any }>("/scalp/regime"),

  getStrategies: () =>
    scalpRequest<{ status: string; strategies: Array<{ id: string; name: string; version: string; eligible_regimes: string[] }> }>("/scalp/strategies"),

  triggerEmergencyStop: () =>
    scalpRequest<{ status: string; message: string; cancelled_orders: number }>("/scalp/emergency-stop", {
      method: "POST",
    }),

  resetEmergencyStop: () =>
    scalpRequest<{ status: string; message: string }>("/scalp/emergency-stop/reset", {
      method: "POST",
    }),

  closePosition: (trade_id: string) =>
    scalpRequest<{ status: string; message: string }>(`/scalp/positions/${trade_id}/close`, {
      method: "POST",
    }),

  confirmCopilotTrade: (session_id: string) =>
    scalpRequest<{ status: string; message: string }>(`/scalp/sessions/${session_id}/confirm`, {
      method: "POST",
    }),
};

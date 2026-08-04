import { create } from "zustand";
import type {
  ScalpSessionData,
  SessionPolicy,
  ScalpCandidate,
  ScalpTrade,
} from "@/lib/scalp-api";

interface ScalpState {
  missionInput: string;
  setMissionInput: (input: string) => void;

  parsing: boolean;
  setParsing: (parsing: boolean) => void;

  parsedPolicy: SessionPolicy | null;
  setParsedPolicy: (policy: SessionPolicy | null) => void;

  activeSession: ScalpSessionData | null;
  setActiveSession: (session: ScalpSessionData | null) => void;

  activeTrade: ScalpTrade | null;
  setActiveTrade: (trade: ScalpTrade | null) => void;

  activeTrades: ScalpTrade[];
  setActiveTrades: (trades: ScalpTrade[] | ((prev: ScalpTrade[]) => ScalpTrade[])) => void;

  pendingProposal: any;
  setPendingProposal: (proposal: any) => void;

  requireApproval: boolean;
  setRequireApproval: (require: boolean) => void;

  isClosing: boolean;
  setIsClosing: (isClosing: boolean) => void;

  isStopping: boolean;
  setIsStopping: (isStopping: boolean) => void;

  isStarting: boolean;
  setIsStarting: (isStarting: boolean) => void;

  recentTrades: ScalpTrade[];
  setRecentTrades: (trades: ScalpTrade[]) => void;

  candidates: ScalpCandidate[];
  setCandidates: (candidates: ScalpCandidate[]) => void;

  funnelCounts: {
    all_markets: number;
    passed_liquidity: number;
    passed_technical: number;
    top_candidates: number;
  };
  setFunnelCounts: (counts: {
    all_markets: number;
    passed_liquidity: number;
    passed_technical: number;
    top_candidates: number;
  }) => void;

  selectedSymbol: string;
  setSelectedSymbol: (symbol: string) => void;

  symbolDetail: any;
  setSymbolDetail: (detail: any) => void;

  regimeInfo: any;
  setRegimeInfo: (info: any) => void;

  loadingCandidates: boolean;
  setLoadingCandidates: (loading: boolean) => void;

  emergencyActive: boolean;
  setEmergencyActive: (active: boolean) => void;

  agentLogs: Array<{
    timestamp: string;
    session_id?: string;
    agent: string;
    level: string;
    action: string;
    message: string;
    details?: any;
  }>;
  setAgentLogs: (logs: any[]) => void;

  selectedAgentFilter: string;
  setSelectedAgentFilter: (filter: string) => void;

  autonomyMode: "copilot" | "guarded_autopilot" | "full_autonomous";
  setAutonomyMode: (mode: "copilot" | "guarded_autopilot" | "full_autonomous") => void;

  activeTab: "desk" | "verifications" | "history";
  setActiveTab: (tab: "desk" | "verifications" | "history") => void;

  sessionHistory: ScalpSessionData[];
  setSessionHistory: (history: ScalpSessionData[]) => void;

  historySearch: string;
  setHistorySearch: (search: string) => void;

  loadingHistory: boolean;
  setLoadingHistory: (loading: boolean) => void;
}

export const useScalpStore = create<ScalpState>((set) => ({
  missionInput: "Allocate 20 USDT for the next 3 hours. Scan BTC, ETH, SOL and other high-volume Bitget futures markets. Use isolated margin, maximum 3x leverage, risk no more than 0.50 USDT per trade, stop after earning 5 USDT or losing 2 USDT.",
  setMissionInput: (input) => set({ missionInput: input }),

  parsing: false,
  setParsing: (parsing) => set({ parsing }),

  parsedPolicy: null,
  setParsedPolicy: (policy) => set({ parsedPolicy: policy }),

  activeSession: null,
  setActiveSession: (session) => set((state) => JSON.stringify(state.activeSession) === JSON.stringify(session) ? {} : { activeSession: session }),

  activeTrade: null,
  setActiveTrade: (trade) => set((state) => JSON.stringify(state.activeTrade) === JSON.stringify(trade) ? {} : { activeTrade: trade }),

  activeTrades: [],
  setActiveTrades: (trades) => set((state) => {
    const nextTrades = typeof trades === 'function' ? trades(state.activeTrades) : trades;
    return JSON.stringify(state.activeTrades) === JSON.stringify(nextTrades) ? {} : { activeTrades: nextTrades };
  }),

  pendingProposal: null,
  setPendingProposal: (proposal) => set((state) => JSON.stringify(state.pendingProposal) === JSON.stringify(proposal) ? {} : { pendingProposal: proposal }),

  requireApproval: true,
  setRequireApproval: (require) => set({ requireApproval: require }),

  isClosing: false,
  setIsClosing: (isClosing) => set({ isClosing }),

  isStopping: false,
  setIsStopping: (isStopping) => set({ isStopping }),

  isStarting: false,
  setIsStarting: (isStarting) => set({ isStarting }),

  recentTrades: [],
  setRecentTrades: (trades) => set((state) => JSON.stringify(state.recentTrades) === JSON.stringify(trades) ? {} : { recentTrades: trades }),

  candidates: [],
  setCandidates: (candidates) => set((state) => JSON.stringify(state.candidates) === JSON.stringify(candidates) ? {} : { candidates }),

  funnelCounts: {
    all_markets: 126,
    passed_liquidity: 18,
    passed_technical: 4,
    top_candidates: 2,
  },
  setFunnelCounts: (counts) => set((state) => JSON.stringify(state.funnelCounts) === JSON.stringify(counts) ? {} : { funnelCounts: counts }),

  selectedSymbol: "BTCUSDT",
  setSelectedSymbol: (symbol) => set({ selectedSymbol: symbol }),

  symbolDetail: null,
  setSymbolDetail: (detail) => set((state) => JSON.stringify(state.symbolDetail) === JSON.stringify(detail) ? {} : { symbolDetail: detail }),

  regimeInfo: null,
  setRegimeInfo: (info) => set((state) => JSON.stringify(state.regimeInfo) === JSON.stringify(info) ? {} : { regimeInfo: info }),

  loadingCandidates: true,
  setLoadingCandidates: (loading) => set({ loadingCandidates: loading }),

  emergencyActive: false,
  setEmergencyActive: (active) => set({ emergencyActive: active }),

  agentLogs: [],
  setAgentLogs: (logs) => set((state) => JSON.stringify(state.agentLogs) === JSON.stringify(logs) ? {} : { agentLogs: logs }),

  selectedAgentFilter: "ALL",
  setSelectedAgentFilter: (filter) => set({ selectedAgentFilter: filter }),

  autonomyMode: "guarded_autopilot",
  setAutonomyMode: (mode) => set({ autonomyMode: mode }),

  activeTab: "desk",
  setActiveTab: (tab) => set({ activeTab: tab }),

  sessionHistory: [],
  setSessionHistory: (history) => set((state) => JSON.stringify(state.sessionHistory) === JSON.stringify(history) ? {} : { sessionHistory: history }),

  historySearch: "",
  setHistorySearch: (search) => set({ historySearch: search }),

  loadingHistory: false,
  setLoadingHistory: (loading) => set({ loadingHistory: loading }),
}));

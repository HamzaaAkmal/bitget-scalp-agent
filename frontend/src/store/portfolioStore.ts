import { create } from "zustand";
import type { BitgetMcpEnvelope } from "@/lib/api";

export type PortfolioCategory = "USDT-FUTURES";

interface PortfolioState {
  category: PortfolioCategory;
  setCategory: (cat: PortfolioCategory) => void;
  
  loading: boolean;
  setLoading: (loading: boolean) => void;

  accountEnvelope: BitgetMcpEnvelope | null;
  accountRows: Record<string, unknown>[];
  positionRows: Record<string, unknown>[];
  orderRows: Record<string, unknown>[];
  fillRows: Record<string, unknown>[];
  strategyRows: Record<string, unknown>[];

  setAccountEnvelope: (env: BitgetMcpEnvelope | null) => void;
  setAccountRows: (rows: Record<string, unknown>[]) => void;
  setPositionRows: (rows: Record<string, unknown>[]) => void;
  setOrderRows: (rows: Record<string, unknown>[]) => void;
  setFillRows: (rows: Record<string, unknown>[]) => void;
  setStrategyRows: (rows: Record<string, unknown>[]) => void;
}

export const usePortfolioStore = create<PortfolioState>((set) => ({
  category: "USDT-FUTURES",
  setCategory: (cat) => set({ category: cat }),
  
  loading: true,
  setLoading: (loading) => set({ loading }),

  accountEnvelope: null,
  accountRows: [],
  positionRows: [],
  orderRows: [],
  fillRows: [],
  strategyRows: [],

  setAccountEnvelope: (env) => set((state) => JSON.stringify(state.accountEnvelope) === JSON.stringify(env) ? {} : { accountEnvelope: env }),
  setAccountRows: (rows) => set((state) => JSON.stringify(state.accountRows) === JSON.stringify(rows) ? {} : { accountRows: rows }),
  setPositionRows: (rows) => set((state) => JSON.stringify(state.positionRows) === JSON.stringify(rows) ? {} : { positionRows: rows }),
  setOrderRows: (rows) => set((state) => JSON.stringify(state.orderRows) === JSON.stringify(rows) ? {} : { orderRows: rows }),
  setFillRows: (rows) => set((state) => JSON.stringify(state.fillRows) === JSON.stringify(rows) ? {} : { fillRows: rows }),
  setStrategyRows: (rows) => set((state) => JSON.stringify(state.strategyRows) === JSON.stringify(rows) ? {} : { strategyRows: rows }),
}));

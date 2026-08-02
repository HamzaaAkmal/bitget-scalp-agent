import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Loader2,
  OctagonX,
  RefreshCw,
  ShieldCheck,
  ShieldOff,
  Wifi,
  WifiOff,
} from "lucide-react";
import { api, type LiveBrokerStatus, type LiveStatus } from "@/lib/api";
import { cn } from "@/lib/utils";

const RUNTIME_POLL_INTERVAL_MS = 15_000;
const RUNTIME_CLOCK_INTERVAL_MS = 1_000;

export function Runtime() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<LiveStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nowMs, setNowMs] = useState(() => Date.now());
  const activeRequestRef = useRef<{ id: number; controller: AbortController } | null>(null);
  const requestSeqRef = useRef(0);
  const mountedRef = useRef(false);
  const tRef = useRef(t);

  useEffect(() => {
    tRef.current = t;
  }, [t]);

  const loadStatus = useCallback(async (mode: "initial" | "refresh" = "refresh") => {
    const requestId = requestSeqRef.current + 1;
    requestSeqRef.current = requestId;
    activeRequestRef.current?.controller.abort();
    const controller = new AbortController();
    activeRequestRef.current = { id: requestId, controller };

    if (mode === "initial") setLoading(true);
    else setRefreshing(true);
    setError(null);
    try {
      const next = await api.getLiveStatus(controller.signal);
      if (!mountedRef.current || !isCurrentStatusRequest(activeRequestRef.current, requestId, controller)) return;
      setStatus(next);
    } catch (err) {
      if (controller.signal.aborted) return;
      if (!mountedRef.current || !isCurrentStatusRequest(activeRequestRef.current, requestId, controller)) return;
      console.warn("Failed to load runtime status", err);
      setStatus(null);
      setError(err instanceof Error ? err.message : tRef.current("runtime.statusUnavailable"));
    } finally {
      if (!mountedRef.current || !isCurrentStatusRequest(activeRequestRef.current, requestId, controller)) return;
      activeRequestRef.current = null;
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    loadStatus("initial");
    const pollTimer = window.setInterval(() => loadStatus("refresh"), RUNTIME_POLL_INTERVAL_MS);
    const clockTimer = window.setInterval(() => setNowMs(Date.now()), RUNTIME_CLOCK_INTERVAL_MS);
    return () => {
      mountedRef.current = false;
      requestSeqRef.current += 1;
      activeRequestRef.current?.controller.abort();
      activeRequestRef.current = null;
      window.clearInterval(pollTimer);
      window.clearInterval(clockTimer);
    };
  }, [loadStatus]);



  return (
    <div className="min-h-screen p-6 lg:p-8">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
        <section className="flex flex-col gap-4 border-b border-border/60 pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-3">
            <div className="inline-flex items-center gap-2 rounded-md border border-border/60 px-2.5 py-1 text-xs font-medium text-muted-foreground">
              <Activity className="h-3.5 w-3.5" />
              {t("runtime.monitorBadge")}
            </div>
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">{t("runtime.title")}</h1>
              <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
                {t("runtime.subtitlePre")} <span className="font-mono">/live/status</span>
                {t("runtime.subtitlePost")}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => loadStatus("refresh")}
            disabled={refreshing}
            className="inline-flex items-center gap-2 rounded-md border border-border/60 px-4 py-2 text-sm font-medium transition hover:bg-muted/60 disabled:opacity-50"
          >
            {refreshing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            {t("runtime.refresh")}
          </button>
        </section>

        {loading ? (
          <div className="grid gap-3 md:grid-cols-4">
            {[1, 2, 3, 4].map((item) => (
              <div key={item} className="h-24 animate-pulse rounded-xl border border-border/60 bg-card shadow-sm" />
            ))}
          </div>
        ) : null}

        {!loading && error ? (
          <section className="rounded-xl border border-warning/30 bg-warning/5 p-5 shadow-sm">
            <div className="flex items-center gap-2 font-medium text-warning">
              <AlertTriangle className="h-5 w-5" />
              {t("runtime.unavailableTitle")}
            </div>
            <p className="mt-2 text-sm text-muted-foreground">{error}</p>
            <p className="mt-2 text-xs text-muted-foreground">{t("runtime.unavailableHint")}</p>
          </section>
        ) : null}

        {!loading && !error && status ? (
          <>
            {status.brokers.filter(b => b.auth.broker.toLowerCase().includes('bitget')).length === 0 ? (
              <section className="rounded-xl border border-dashed border-border/60 bg-card p-5 text-center shadow-sm">
                <ShieldOff className="mx-auto h-8 w-8 text-muted-foreground" />
                <h2 className="mt-3 text-sm font-semibold">{t("runtime.noProfilesTitle")}</h2>
                <p className="mt-1 text-sm text-muted-foreground">{t("runtime.noProfilesBody")}</p>
              </section>
            ) : (
              <section className="grid gap-4">
                {status.brokers
                  .filter((broker) => broker.auth.broker.toLowerCase().includes('bitget'))
                  .map((broker) => (
                  <BrokerRuntimeCard
                    key={broker.auth.profile_id || broker.auth.broker}
                    broker={broker}
                    globalHalted={status.global_halted}
                    t={t}
                    nowMs={nowMs}
                    onRefresh={() => loadStatus("refresh")}
                  />
                ))}
              </section>
            )}
          </>
        ) : null}
      </div>
    </div>
  );
}



function isCurrentStatusRequest(
  activeRequest: { id: number; controller: AbortController } | null,
  requestId: number,
  controller: AbortController,
): boolean {
  return activeRequest?.id === requestId && activeRequest.controller === controller;
}

function BrokerRuntimeCard({
  broker,
  globalHalted,
  t,
  nowMs,
  onRefresh,
}: {
  broker: LiveBrokerStatus;
  globalHalted: boolean;
  t: TFunction;
  nowMs: number;
  onRefresh: () => Promise<void>;
}) {
  const brokerKey = broker.auth.broker;
  const runnerAlive = broker.runner?.alive ?? false;
  const halted = globalHalted || broker.halted;
  const risk = deriveRiskState(broker, globalHalted, t);

  if (broker.auth.transport === "broker_sdk") {
    return <SdkBrokerRuntimeCard broker={broker} t={t} onRefresh={onRefresh} />;
  }

  return (
    <article className="rounded-xl border border-border/60 bg-card p-4 shadow-sm">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold capitalize">{brokerKey}</h2>
            {brokerKey.toLowerCase().includes('bitget') ? (
              <StatusPill label="active" tone="success" />
            ) : (
              <>
                <StatusPill
                  label={broker.auth.oauth_token_present ? t("runtime.authPresent") : t("runtime.authMissing")}
                  tone={broker.auth.oauth_token_present ? "success" : "neutral"}
                />
                <StatusPill
                  label={runnerAlive ? t("runtime.runnerAlive") : t("runtime.runnerStopped")}
                  tone={runnerAlive ? "success" : "neutral"}
                />
              </>
            )}
            {halted ? <StatusPill label={t("runtime.haltedPill")} tone="danger" /> : null}
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            {brokerKey.toLowerCase().includes('bitget') ? (
              "MCP Server Connected · Ready to accept orders"
            ) : (
              <>
                {broker.auth.is_live_broker ? t("runtime.recognizedProfile") : t("runtime.unknownProfile")} · {t("runtime.lastTick")}{" "}
                {formatLastTick(broker.runner?.last_tick, broker.runner?.last_tick_age_seconds, t, nowMs)}
              </>
            )}
          </p>
        </div>
        {brokerKey.toLowerCase().includes('bitget') ? (
          <StatusPill label="online" tone="success" />
        ) : (
          <StatusPill label={risk.label} tone={risk.tone} />
        )}
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <RuntimePanel title="Available Tools" icon={Activity}>
          <ul className="grid gap-1.5 text-sm text-muted-foreground list-disc pl-4">
            <li>account - Fetch account balance</li>
            <li>order - Place and manage limit/market orders</li>
            <li>position - Fetch active positions</li>
            <li>strategy_order - Place TP/SL protection orders</li>
            <li>market - Fetch market data and candidates</li>
          </ul>
        </RuntimePanel>
      </div>
    </article>
  );
}

function SdkBrokerRuntimeCard({ broker, t, onRefresh }: { broker: LiveBrokerStatus; t: TFunction; onRefresh: () => Promise<void> }) {
  const auth = broker.auth;
  const [verifying, setVerifying] = useState(false);
  const [verifyError, setVerifyError] = useState<string | null>(null);
  const profileId = auth.profile_id || `${auth.broker}-live-sdk-readonly`;
  const state = connectorState(auth, t);

  const verify = useCallback(async () => {
    if (verifying) return;
    setVerifying(true);
    setVerifyError(null);
    try {
      await api.verifyConnector(profileId);
      await onRefresh();
    } catch {
      setVerifyError(t("runtime.connectorVerifyFailed"));
    } finally {
      setVerifying(false);
    }
  }, [onRefresh, profileId, t, verifying]);

  return (
    <article className="rounded-xl border border-border/60 bg-card p-4 shadow-sm">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold capitalize">{auth.broker}</h2>
            <StatusPill label={state.label} tone={state.tone} />
          </div>
          {isReadOnlyCompatible(auth) ? (
            <p className="mt-2 text-sm text-muted-foreground">{t("runtime.sdkConnectorProfile")}</p>
          ) : null}
        </div>
        {state.action ? (
          <button
            type="button"
            onClick={verify}
            disabled={verifying}
            className="inline-flex items-center gap-2 rounded-md border border-border/60 px-4 py-2 text-sm font-medium transition hover:bg-muted/60 disabled:opacity-50"
          >
            {verifying ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            {t(state.action)}
          </button>
        ) : null}
      </div>

      {state.kind === "not_configured" ? (
        <section className="mt-4 rounded-xl border border-dashed border-border/60 bg-muted/40 p-4 shadow-sm">
          <p className="text-sm text-muted-foreground">{t("runtime.missingLongbridgeVariables")}</p>
          <ul className="mt-2 grid gap-1 font-mono text-sm">
            <li>LONGBRIDGE_APP_KEY</li>
            <li>LONGBRIDGE_APP_SECRET</li>
            <li>LONGBRIDGE_ACCESS_TOKEN</li>
          </ul>
        </section>
      ) : (
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <RuntimePanel title={t("runtime.connectionDetails")} icon={state.kind === "connected" ? Wifi : WifiOff}>
            <KeyValue label={t("runtime.credentialSource")} value={auth.credential_source || t("runtime.unknown")} />
            <KeyValue label={t("runtime.sdk")} value={formatSdkState(auth.sdk_installed, t)} />
          </RuntimePanel>
          <RuntimePanel title={t("runtime.environment")} icon={ShieldCheck}>
            <KeyValue label={t("runtime.environmentIdentity")} value={formatEnvironmentIdentity(auth.environment_identity, t)} />
            <KeyValue label={t("runtime.capabilities")} value={formatCapabilities(auth, t)} />
          </RuntimePanel>
          <RuntimePanel title={t("runtime.diagnostics")} icon={state.kind === "error" ? AlertTriangle : CheckCircle2}>
            <KeyValue label={t("runtime.lastChecked")} value={auth.last_checked_at || t("runtime.never")} />
            {auth.error_code ? <KeyValue label={t("runtime.errorCode")} value={auth.error_code} /> : null}
            {state.kind === "error" ? <p className="text-sm text-muted-foreground">{connectorDiagnostic(auth.error_code, t)}</p> : null}
          </RuntimePanel>
        </div>
      )}
      {verifyError ? <p role="alert" className="mt-3 text-sm text-danger">{verifyError}</p> : null}
    </article>
  );
}

function connectorState(auth: LiveBrokerStatus["auth"], t: TFunction): {
  kind: "not_configured" | "ready" | "connected" | "error" | "unknown";
  label: string;
  tone: "success" | "danger" | "warning" | "neutral";
  action?: "runtime.verifyConnection" | "runtime.retry";
} {
  if (auth.connection_state === "connected") {
    if (isReadOnlyCompatible(auth)) {
      return { kind: "connected", label: t("runtime.connectedReadOnly"), tone: "success" };
    }
    return { kind: "connected", label: t("runtime.connectedAccessUnknown"), tone: "neutral" };
  }
  if (auth.connection_state === "not_configured" || auth.configured === false) {
    return { kind: "not_configured", label: t("runtime.notConfigured"), tone: "neutral" };
  }
  if (auth.connection_state === "error") {
    return { kind: "error", label: t("runtime.connectionFailed"), tone: "danger", action: "runtime.retry" };
  }
  if (auth.connection_state === "ready") {
    return { kind: "ready", label: t("runtime.readyToVerify"), tone: "warning", action: "runtime.verifyConnection" };
  }
  return { kind: "unknown", label: t("runtime.connectorStatusUnavailable"), tone: "neutral" };
}

function connectorDiagnostic(errorCode: string | null | undefined, t: TFunction): string {
  switch (errorCode) {
    case "credentials_partial": return t("runtime.diagnosticCredentialsPartial");
    case "credentials_conflict": return t("runtime.diagnosticCredentialsConflict");
    case "sdk_missing": return t("runtime.diagnosticSdkMissing");
    case "authentication_failed": return t("runtime.diagnosticAuthenticationFailed");
    case "network_unreachable": return t("runtime.diagnosticNetworkUnreachable");
    default: return t("runtime.diagnosticBrokerError");
  }
}

function formatSdkState(installed: boolean | null | undefined, t: TFunction): string {
  if (installed === true) return t("runtime.installed");
  if (installed === false) return t("runtime.notInstalled");
  return t("runtime.unknown");
}

function formatEnvironmentIdentity(identity: string | null | undefined, t: TFunction): string {
  if (identity === "config_declared" || identity === "config-declared") return t("runtime.configDeclared");
  return identity || t("runtime.unknown");
}

function isReadCapability(capability: string): boolean {
  return capability.endsWith(".read");
}

function isReadOnlyCompatible(auth: LiveBrokerStatus["auth"]): boolean {
  if (auth.connection_state !== "connected") return false;
  if (auth.readonly !== true) return false;
  if (!auth.profile_id?.endsWith("-readonly")) return false;
  if (!auth.capabilities?.length) return false;
  return auth.capabilities.every(isReadCapability);
}

function formatCapabilities(auth: LiveBrokerStatus["auth"], t: TFunction): string {
  const labels: Record<string, string> = {
    "account.read": t("runtime.capabilityAccount"),
    "positions.read": t("runtime.capabilityPositions"),
    "orders.read": t("runtime.capabilityOpenOrders"),
    "quotes.read": t("runtime.capabilityQuotes"),
    "history.read": t("runtime.capabilityHistory"),
  };
  const readCapabilities = auth.capabilities?.filter(isReadCapability) ?? [];
  const rendered = readCapabilities.map((capability) => labels[capability] || capability).join(", ");
  if (!isReadOnlyCompatible(auth)) {
    return rendered ? `${rendered} · ${t("runtime.accessUnknown")}` : t("runtime.accessUnknown");
  }
  return `${rendered} · ${t("runtime.readOnly")}`;
}

function RuntimePanel({ title, icon: Icon, children }: { title: string; icon: typeof Activity; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-border/60 bg-muted/40 p-4 shadow-sm">
      <div className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        {title}
      </div>
      <div className="space-y-2">{children}</div>
    </section>
  );
}

function KeyValue({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[11px] uppercase text-muted-foreground">{label}</div>
      <div className="font-mono text-sm">{value || "-"}</div>
    </div>
  );
}

function StatusPill({ label, tone }: { label: string; tone: "success" | "danger" | "warning" | "neutral" }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded px-2 py-0.5 text-xs font-medium",
        tone === "success" && "bg-success/10 text-success",
        tone === "danger" && "bg-danger/10 text-danger",
        tone === "warning" && "bg-warning/10 text-warning",
        tone === "neutral" && "bg-muted text-muted-foreground",
      )}
    >
      {label}
    </span>
  );
}

function deriveRiskState(broker: LiveBrokerStatus, globalHalted: boolean, t: TFunction): {
  label: string;
  tone: "success" | "danger" | "warning" | "neutral";
  icon: typeof Activity;
  description: string;
} {
  if (globalHalted || broker.halted) {
    return {
      label: t("runtime.riskHalted"),
      tone: "danger",
      icon: OctagonX,
      description: t("runtime.riskHaltedDesc"),
    };
  }
  if (broker.runner?.alive && broker.mandate && !broker.mandate.expired) {
    return {
      label: t("runtime.riskActive"),
      tone: "success",
      icon: Activity,
      description: t("runtime.riskActiveDesc"),
    };
  }
  if (broker.auth.oauth_token_present && broker.mandate && !broker.mandate.expired) {
    return {
      label: t("runtime.riskIdle"),
      tone: "warning",
      icon: Clock3,
      description: t("runtime.riskIdleDesc"),
    };
  }
  return {
    label: t("runtime.riskDormant"),
    tone: "neutral",
    icon: ShieldOff,
    description: t("runtime.riskDormantDesc"),
  };
}

function formatLastTick(
  value: string | number | null | undefined,
  ageSeconds: number | null | undefined,
  t: TFunction,
  nowMs: number,
): string {
  if (typeof ageSeconds === "number" && Number.isFinite(ageSeconds)) {
    if (ageSeconds < 60) return `${Math.round(ageSeconds)}s ${t("runtime.ago")}`;
    if (ageSeconds < 3600) return `${Math.floor(ageSeconds / 60)}m ${t("runtime.ago")}`;
    return `${Math.floor(ageSeconds / 3600)}h ${t("runtime.ago")}`;
  }
  if (value == null || value === "") return t("runtime.never");
  const timestamp = typeof value === "number" ? normalizeEpochMs(value) : new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return t("runtime.unknown");
  const deltaSec = Math.round((nowMs - timestamp) / 1000);
  if (deltaSec < 60) return `${Math.max(0, deltaSec)}s ${t("runtime.ago")}`;
  if (deltaSec < 3600) return `${Math.floor(deltaSec / 60)}m ${t("runtime.ago")}`;
  return `${Math.floor(deltaSec / 3600)}h ${t("runtime.ago")}`;
}

function normalizeEpochMs(value: number): number {
  if (value >= 1_000_000_000_000) return value;
  if (value >= 946_684_800 && value <= 4_102_444_800) return value * 1000;
  return Number.NaN;
}

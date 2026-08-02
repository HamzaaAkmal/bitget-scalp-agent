import { useTranslation } from "react-i18next";
import { useEffect, useState } from "react";
import { Link, Outlet, useLocation, useSearchParams } from "react-router";
import { Activity, Bot, CandlestickChart, FileText, Moon, Sun, Plus, Trash2, Pencil, MessageSquare, ChevronsLeft, ChevronsRight, Settings, Loader2, Wallet, Radar } from "lucide-react";
import { cn } from "@/lib/utils";
import { useDarkMode } from "@/hooks/useDarkMode";
import { api, type SessionItem } from "@/lib/api";
import { safeGet, safeSet } from "@/lib/storage";
import { useAgentStore } from "@/stores/agent";
import { BrandMark } from "@/components/common/BrandMark";
import { ConnectionBanner } from "@/components/layout/ConnectionBanner";

// APP_VERSION is sourced from the English locale file (app.version key).

export function Layout() {
  const { t } = useTranslation();

  // "/" is the product (chat); marketing moved to /about. The Agent entry
  // matches both "/" and legacy "/agent" deep links.
  const NAV = [
    { to: "/", icon: Bot, label: t('layout.agent') },
    { to: "/ai-scalp-trader", icon: Radar, label: "AI Scalp Trader" },
    { to: "/runtime", icon: Activity, label: t('layout.runtime') },
    { to: "/markets", icon: CandlestickChart, label: t('layout.markets') },
    { to: "/portfolio", icon: Wallet, label: t('layout.portfolio') },
    { to: "/reports", icon: FileText, label: t('layout.reports') },
    { to: "/settings", icon: Settings, label: t('layout.settings') },
  ];
  const { pathname } = useLocation();
  const [searchParams] = useSearchParams();
  const { dark, toggle } = useDarkMode();
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const sseStatus = useAgentStore(s => s.sseStatus);
  const sseRetryAttempt = useAgentStore(s => s.sseRetryAttempt);
  const [collapsed, setCollapsed] = useState(() => safeGet("qa-sidebar") === "collapsed");

  const activeSessionId = searchParams.get("session");
  const streamingSessionId = useAgentStore(s => s.streamingSessionId);

  useEffect(() => {
    safeSet("qa-sidebar", collapsed ? "collapsed" : "expanded");
  }, [collapsed]);

  useEffect(() => {
    const syncSidebarPreference = (event: StorageEvent) => {
      if (event.key !== null && event.key !== "qa-sidebar") return;
      setCollapsed(safeGet("qa-sidebar") === "collapsed");
    };
    window.addEventListener("storage", syncSidebarPreference);
    return () => window.removeEventListener("storage", syncSidebarPreference);
  }, []);

  const loadSessions = () => {
    api.listSessions()
      .then((list) => setSessions(Array.isArray(list) ? list : []))
      .catch(() => {})
      .finally(() => setSessionsLoading(false));
  };

  // Load sessions on mount. Also refresh when navigating TO /agent or when
  // the active session changes (covers new session creation from Agent).
  const isAgentPage = pathname.startsWith("/agent");
  useEffect(() => { loadSessions(); }, [isAgentPage, activeSessionId]);

  // Re-list after out-of-band title changes (e.g. LLM auto-titling on the
  // first completed exchange).
  useEffect(() => {
    const refresh = () => loadSessions();
    window.addEventListener("vibe:sessions-refresh", refresh);
    return () => window.removeEventListener("vibe:sessions-refresh", refresh);
  }, []);

  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [renameTarget, setRenameTarget] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  const deleteSession = async (sid: string) => {
    try {
      await api.deleteSession(sid);
      setSessions((prev) => prev.filter((s) => s.session_id !== sid));
    } catch { /* ignore */ }
    setDeleteTarget(null);
  };

  const renameSession = async (sid: string) => {
    if (!renameValue.trim()) { setRenameTarget(null); return; }
    try {
      await api.renameSession(sid, renameValue.trim());
      setSessions((prev) => prev.map((s) => s.session_id === sid ? { ...s, title: renameValue.trim() } : s));
    } catch { /* ignore */ }
    setRenameTarget(null);
  };

  return (
    <div className="flex h-screen bg-background">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:start-4 focus:top-4 focus:z-[70] focus:rounded-md focus:bg-background focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-foreground focus:shadow-lg focus:outline-none focus:ring-2 focus:ring-primary/40"
      >
        {t('layout.skipToMain', { defaultValue: 'Skip to main content' })}
      </a>
      {/* Sidebar */}
      <aside
        aria-label={t('layout.sidebar', { defaultValue: 'Vibe-Trading sidebar' })}
        className={cn(
          "max-md:w-12 border-e border-border/60 bg-card flex flex-col shrink-0 transition-all duration-200 overflow-visible",
          collapsed ? "w-12" : "w-64"
        )}
      >
        {/* Brand */}
        <div className={cn("border-b border-border/60", collapsed ? "p-2 flex justify-center" : "p-4 max-md:p-2 max-md:flex max-md:justify-center")}>
          <Link
            to="/"
            aria-label="Vibe-Trading"
            className={cn("flex items-center", collapsed ? "justify-center" : "gap-2 max-md:justify-center")}
          >
            <BrandMark className="h-6 w-6 shrink-0" />
            {!collapsed && (
              <span className="text-[15px] font-semibold tracking-tight max-md:hidden">Vibe-Trading</span>
            )}
          </Link>
        </div>

        {/* Nav */}
        <nav
          aria-label={t('layout.mainNavigation', { defaultValue: 'Main navigation' })}
          className={cn("space-y-0.5", collapsed ? "p-1" : "p-2 max-md:p-1")}
        >
          {NAV.map(({ to, icon: Icon, label }) => {
            const text = label;
            return (
              <Link
                key={to}
                to={to}
                aria-label={text}
                className={cn(
                  "flex items-center rounded-md text-[13px] transition-colors",
                  collapsed ? "justify-center px-2 py-1.5" : "gap-3 px-3 py-1.5 max-md:justify-center max-md:px-2",
                  (to === "/" ? pathname === "/" || pathname.startsWith("/agent") : pathname.startsWith(to))
                    ? "bg-primary/10 text-primary font-medium"
                    : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
                )}
                title={collapsed ? text : undefined}
              >
                <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                {!collapsed && <span className="max-md:hidden">{text}</span>}
              </Link>
            );
          })}
        </nav>

        {/* Sessions — hidden when collapsed */}
        {!collapsed && (
          <div className="flex-1 overflow-auto border-t border-border/60 mt-2 flex flex-col max-md:hidden">
            <div className="flex items-center justify-between px-4 py-2">
              <span className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <MessageSquare className="h-3.5 w-3.5" />
                {t('layout.sessions')}
              </span>
              <Link
                to="/agent"
                aria-label={t('layout.newChat')}
                className="flex items-center gap-1 p-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
                title={t('layout.newChat')}
              >
                <Plus className="h-3.5 w-3.5" aria-hidden="true" />
              </Link>
            </div>

            <div className="px-2 pb-2 space-y-0.5 overflow-auto flex-1">
              {sessionsLoading ? (
                <div className="space-y-1.5 px-2 py-1">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-7 rounded-md bg-muted/50 animate-pulse" />
                  ))}
                </div>
              ) : sessions.length === 0 ? (
                <p className="px-3 py-2 text-xs text-muted-foreground/60">{t('layout.noSessions')}</p>
              ) : null}
              {sessions.map((s) => {
                const isActive = s.session_id === activeSessionId;
                const isDeleting = deleteTarget === s.session_id;
                const isRenaming = renameTarget === s.session_id;
                return (
                  <div key={s.session_id} className="group relative flex items-center">
                    {isRenaming ? (
                      <input
                        autoFocus
                        value={renameValue}
                        onChange={(e) => setRenameValue(e.target.value)}
                        onKeyDown={(e) => { if (e.key === "Enter") renameSession(s.session_id); if (e.key === "Escape") setRenameTarget(null); }}
                        onBlur={() => renameSession(s.session_id)}
                        aria-label={`${t('layout.rename')}: ${s.title || s.session_id}`}
                        className="flex-1 min-w-0 ps-3 pe-2 py-1.5 rounded-md text-xs border border-primary bg-background outline-none focus:ring-2 focus:ring-primary/40"
                      />
                    ) : (
                      <Link
                        to={`/agent?session=${s.session_id}`}
                        className={cn(
                          "flex-1 min-w-0 ps-3 pe-14 py-1.5 rounded-md text-xs transition-colors truncate block border-s-2",
                          isActive
                            ? "border-s-primary bg-primary/10 text-primary font-medium"
                            : "border-s-transparent text-muted-foreground hover:bg-muted hover:text-foreground"
                        )}
                        title={s.title || s.session_id}
                      >
                        <span className="flex min-w-0 items-center gap-1.5">
                          {streamingSessionId === s.session_id ? (
                            <Loader2 className="h-3 w-3 shrink-0 animate-spin text-primary" />
                          ) : (
                            // Transparent placeholder keeps titles aligned with
                            // spinner rows without a meaningless gray dot.
                            <span className={cn(
                              "h-1.5 w-1.5 rounded-full shrink-0",
                              isActive ? "bg-primary/70" : "bg-transparent"
                            )} />
                          )}
                          <span className="min-w-0 truncate">{s.title || s.session_id.slice(0, 16)}</span>
                        </span>
                      </Link>
                    )}
                    {!isRenaming && isDeleting ? (
                      <div className="absolute right-0.5 flex items-center gap-0.5">
                        <button onClick={() => deleteSession(s.session_id)} className="p-1.5 text-danger hover:bg-danger/10 rounded text-[10px] font-medium">{t('layout.confirm')}</button>
                        <button onClick={() => setDeleteTarget(null)} className="p-1.5 text-muted-foreground hover:bg-muted rounded text-[10px]">{t('layout.cancel')}</button>
                      </div>
                    ) : !isRenaming ? (
                      <div className="absolute right-1 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 flex items-center gap-0.5 transition-opacity">
                        <button
                          onClick={(e) => { e.preventDefault(); e.stopPropagation(); setRenameTarget(s.session_id); setRenameValue(s.title || ""); }}
                          className="p-1.5 text-muted-foreground hover:text-foreground rounded"
                          title={t('layout.rename')}
                        >
                          <Pencil className="h-3 w-3" />
                        </button>
                        <button
                          onClick={(e) => { e.preventDefault(); e.stopPropagation(); setDeleteTarget(s.session_id); }}
                          className="p-1.5 text-muted-foreground hover:text-danger rounded"
                          title={t('layout.delete')}
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Spacer when collapsed */}
        {collapsed && <div className="flex-1" />}

        {/* Footer */}
        <div className={cn("mt-auto border-t border-border/60", collapsed ? "p-1 flex flex-col items-center gap-1" : "p-3 space-y-2 max-md:p-1 max-md:flex max-md:flex-col max-md:items-center max-md:gap-1 max-md:space-y-0")}>
          {collapsed ? (
            <>
              <button onClick={toggle} className="p-1.5 text-muted-foreground hover:text-foreground rounded transition-colors" title={dark ? t('layout.light') : t('layout.dark')}>
                {dark ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
              </button>
              <button onClick={() => setCollapsed(false)} className="p-1.5 text-muted-foreground hover:text-foreground rounded transition-colors" title={t('layout.expand')}>
                <ChevronsRight className="h-3.5 w-3.5" />
              </button>
            </>
          ) : (
            <>
              <div className="flex items-center justify-between max-md:flex-col">
                <button
                  onClick={toggle}
                  className="flex items-center gap-1.5 p-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  {dark ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
                  <span className="max-md:hidden">{dark ? t('layout.light') : t('layout.dark')}</span>
                </button>
                <div className="flex items-center gap-1 max-md:hidden">
                  <button
                    onClick={() => setCollapsed(true)}
                    className="p-1.5 text-muted-foreground hover:text-foreground rounded transition-colors"
                    title={t('layout.collapse')}
                  >
                    <ChevronsLeft className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
              <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground/60 max-md:hidden">
                <span>{t('app.version')}</span>
                <span aria-hidden="true">·</span>
                <Link to="/about" className="transition-colors hover:text-foreground">
                  {t('layout.about')}
                </Link>
              </div>
            </>
          )}
        </div>
      </aside>

      {/* Main */}
      <div className="relative flex-1 flex flex-col overflow-hidden">
        <ConnectionBanner status={sseStatus} retryAttempt={sseRetryAttempt} />
        <main id="main" className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

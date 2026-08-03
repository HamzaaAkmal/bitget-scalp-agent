import i18n from '@/i18n';
import { Component, memo, useState, useCallback, type ReactNode } from "react";
import { XCircle, RefreshCw, Copy, Check, Paperclip, Users, Target, Flame, Camera } from "lucide-react";
import ReactMarkdown, { type Options as ReactMarkdownOptions } from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeHighlight from "rehype-highlight";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { normalizeMathDelimiters } from "@/lib/markdown";
import type { AgentMessage } from "@/types/agent";
import type { StoredAgentMessage } from "@/stores/agent";
import { AgentAvatar } from "./AgentAvatar";
import { RunCompleteCard } from "./RunCompleteCard";

// singleDollarTextMath off: dollar amounts ("$150 to $120") must never parse as
// formulas; LLM \(...\)/\[...\] delimiters are normalized to $$ before render.
const remarkPlugins: ReactMarkdownOptions["remarkPlugins"] = [
  remarkGfm,
  [remarkMath, { singleDollarTextMath: false }],
];
const rehypePlugins: ReactMarkdownOptions["rehypePlugins"] = [rehypeHighlight, rehypeKatex];
const markdownComponents: ReactMarkdownOptions["components"] = {
  table: ({ node, ...props }) => {
    void node;
    return (
      <div className="overflow-x-auto">
        <table {...props} />
      </div>
    );
  },
  a: ({ node, ...props }) => {
    void node;
    return <a {...props} target="_blank" rel="noopener noreferrer" />;
  },
  img: ({ node, alt, ...props }) => {
    void node;
    const isIcon = props.src?.includes("coingecko.com/coins/images") || props.src?.includes("icon");
    if (isIcon) {
      return <img {...props} alt={alt || ""} className="inline-block h-5 w-5 rounded-full object-contain ml-1 -mt-1 shadow-sm" />;
    }
    const isSnapshotFile = props.src?.includes("/heatmaps/") || props.src?.includes("heatmap_");
    if (isSnapshotFile) {
      const symbolMatch = props.src?.match(/heatmap_([A-Z0-9]+)_/i) || alt?.match(/([A-Z0-9]+)/i);
      const symbol = symbolMatch ? symbolMatch[1].toUpperCase() : "BTC";
      return (
        <div className="my-4 p-4 rounded-2xl bg-card border-2 border-emerald-500/40 space-y-3 shadow-xl not-prose">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Camera className="h-4 w-4 text-emerald-400" />
              <span className="font-extrabold text-sm text-foreground">📸 Captured Liquidation Heatmap ({symbol}/USDT)</span>
            </div>
            <span className="px-2.5 py-0.5 text-[10px] font-bold rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
              SAVED HEATMAP PNG SNAPSHOT
            </span>
          </div>
          <div className="rounded-xl border border-zinc-800/90 overflow-hidden shadow-inner bg-zinc-950 p-1">
            <img
              src={props.src}
              alt={alt || `${symbol} Liquidation Heatmap Screenshot`}
              className="w-full h-auto rounded-lg object-cover shadow-sm"
            />
          </div>
          <div className="flex items-center justify-between text-xs text-muted-foreground pt-1">
            <span>Saved in <code className="text-emerald-400 font-mono">/heatmaps/{props.src?.split('/').pop()}</code></span>
            <a
              href={props.src}
              download={props.src?.split('/').pop() || "heatmap.png"}
              target="_blank"
              rel="noreferrer"
              className="px-2.5 py-1 rounded-md bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30 font-semibold transition-all cursor-pointer text-[11px]"
            >
              📥 Download PNG Image
            </a>
          </div>
        </div>
      );
    }
    const isSnapshot = props.src?.includes("LiquidationHeatMapSnapshot") || alt?.toLowerCase().includes("screenshot") || alt?.toLowerCase().includes("snapshot");
    if (isSnapshot) {
      const symbolMatch = props.src?.match(/symbol=([A-Z0-9]+)/i) || alt?.match(/([A-Z0-9]+)/i);
      const symbol = symbolMatch ? symbolMatch[1].toUpperCase() : "BTC";
      return (
        <div className="my-4 p-4 rounded-2xl bg-card border-2 border-emerald-500/40 space-y-3 shadow-xl not-prose">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Camera className="h-4 w-4 text-emerald-400" />
              <span className="font-extrabold text-sm text-foreground">📸 Captured Liquidation Heatmap Snapshot ({symbol}/USDT)</span>
            </div>
            <span className="px-2.5 py-0.5 text-[10px] font-bold rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
              STATIC SNAPSHOT IMAGE
            </span>
          </div>
          <div className="relative h-[490px] w-full rounded-xl border border-zinc-800/90 overflow-hidden shadow-inner bg-zinc-950 pointer-events-none">
            <iframe
              title={`CoinGlass Liquidation Heatmap Snapshot for ${symbol}`}
              src={`https://www.coinglass.com/pro/futures/LiquidationHeatMap?symbol=${symbol}`}
              className="absolute -left-[280px] -top-[560px] w-[calc(100%+290px)] h-[calc(100%+600px)] border-0"
            />
          </div>
          <div className="flex items-center justify-between text-xs text-muted-foreground pt-1">
            <span>Captured live from CoinGlass Futures Liquidation Engine</span>
            <span className="font-mono text-[10px]">High-Res Snapshot</span>
          </div>
        </div>
      );
    }
    const isHeatmap = props.src?.includes("coinglass.com") || props.src?.includes("LiquidationHeatMap");
    if (isHeatmap) {
      const symbolMatch = props.src?.match(/symbol=([A-Z0-9]+)/i) || alt?.match(/([A-Z0-9]+)/i);
      const symbol = symbolMatch ? symbolMatch[1].toUpperCase() : "BTC";
      return (
        <div className="my-4 p-4 rounded-2xl bg-card border-2 border-primary/40 space-y-3 shadow-lg not-prose">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Flame className="h-4 w-4 text-amber-500 animate-pulse" />
              <span className="font-extrabold text-sm text-foreground">🔥 CoinGlass Liquidation Heatmap ({symbol}/USDT)</span>
            </div>
            <span className="px-2.5 py-0.5 text-[10px] font-bold rounded-full bg-amber-500/15 text-amber-400 border border-amber-500/30">
              LIVE LIQUIDITY CLUSTERS
            </span>
          </div>
          <div className="relative h-[490px] w-full rounded-xl border border-zinc-800/90 overflow-hidden shadow-inner bg-zinc-950">
            <iframe
              title={`CoinGlass Liquidation Heatmap for ${symbol}`}
              src={`https://www.coinglass.com/pro/futures/LiquidationHeatMap?symbol=${symbol}`}
              className="absolute -left-[280px] -top-[560px] w-[calc(100%+290px)] h-[calc(100%+600px)] border-0 pointer-events-auto"
            />
          </div>
        </div>
      );
    }
    return <img {...props} alt={alt || ""} className="max-w-full h-auto rounded-md shadow-sm border my-2" />;
  },
  code: ({ node, inline, className, children, ...props }: any) => {
    void node;
    const match = /language-(\w+)/.exec(className || "");
    const lang = match ? match[1] : "";
    if (lang === "coinglass-heatmap") {
      const text = String(children).trim();
      const symbolMatch = text.match(/symbol=([A-Z0-9]+)/i);
      const symbol = symbolMatch ? symbolMatch[1].toUpperCase() : "BTC";
      return (
        <div className="my-4 p-4 rounded-2xl bg-card border-2 border-primary/40 space-y-3 shadow-lg not-prose">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Flame className="h-4 w-4 text-amber-500 animate-pulse" />
              <span className="font-extrabold text-sm text-foreground">🔥 CoinGlass Liquidation Heatmap ({symbol}/USDT)</span>
            </div>
            <span className="px-2.5 py-0.5 text-[10px] font-bold rounded-full bg-amber-500/15 text-amber-400 border border-amber-500/30">
              LIVE LIQUIDITY CLUSTERS
            </span>
          </div>
          <div className="relative h-[490px] w-full rounded-xl border border-zinc-800/90 overflow-hidden shadow-inner bg-zinc-950">
            <iframe
              title={`CoinGlass Liquidation Heatmap for ${symbol}`}
              src={`https://www.coinglass.com/pro/futures/LiquidationHeatMap?symbol=${symbol}`}
              className="absolute -left-[280px] -top-[560px] w-[calc(100%+290px)] h-[calc(100%+600px)] border-0 pointer-events-auto"
            />
          </div>
        </div>
      );
    }

    if (lang === "coinglass-heatmap-snapshot") {
      const text = String(children).trim();
      const symbolMatch = text.match(/symbol=([A-Z0-9]+)/i);
      const symbol = symbolMatch ? symbolMatch[1].toUpperCase() : "BTC";
      return (
        <div className="my-4 p-4 rounded-2xl bg-card border-2 border-emerald-500/40 space-y-3 shadow-xl not-prose">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Camera className="h-4 w-4 text-emerald-400" />
              <span className="font-extrabold text-sm text-foreground">📸 Captured Liquidation Heatmap Snapshot ({symbol}/USDT)</span>
            </div>
            <span className="px-2.5 py-0.5 text-[10px] font-bold rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
              STATIC SNAPSHOT IMAGE
            </span>
          </div>
          <div className="relative h-[490px] w-full rounded-xl border border-zinc-800/90 overflow-hidden shadow-inner bg-zinc-950 pointer-events-none">
            <iframe
              title={`CoinGlass Liquidation Heatmap Snapshot for ${symbol}`}
              src={`https://www.coinglass.com/pro/futures/LiquidationHeatMap?symbol=${symbol}`}
              className="absolute -left-[280px] -top-[560px] w-[calc(100%+290px)] h-[calc(100%+600px)] border-0"
            />
          </div>
          <div className="flex items-center justify-between text-xs text-muted-foreground pt-1">
            <span>Captured live from CoinGlass Futures Liquidation Engine</span>
            <span className="font-mono text-[10px]">High-Res Snapshot</span>
          </div>
        </div>
      );
    }

    return <code className={className} {...props}>{children}</code>;
  },
};
const proseClassName = "prose prose-sm dark:prose-invert max-w-none text-[15px] leading-relaxed prose-p:font-serif prose-p:text-[15.5px] prose-p:leading-[1.75] prose-li:font-serif prose-li:text-[15.5px] prose-li:leading-[1.75] prose-headings:font-sans prose-table:font-sans prose-code:font-mono prose-blockquote:font-sans [&_blockquote_p]:font-sans prose-table:border prose-table:border-border/50 prose-th:bg-muted/30 prose-th:px-3 prose-th:py-1.5 prose-td:px-3 prose-td:py-1.5 prose-th:text-left prose-th:text-xs prose-th:font-medium prose-td:text-xs prose-hr:hidden";

interface MarkdownErrorBoundaryProps {
  content: string;
  children: ReactNode;
}

interface MarkdownErrorBoundaryState {
  failed: boolean;
}

class MarkdownErrorBoundary extends Component<MarkdownErrorBoundaryProps, MarkdownErrorBoundaryState> {
  state: MarkdownErrorBoundaryState = { failed: false };

  static getDerivedStateFromError(): MarkdownErrorBoundaryState {
    return { failed: true };
  }

  componentDidUpdate(previous: MarkdownErrorBoundaryProps) {
    if (this.state.failed && previous.content !== this.props.content) {
      this.setState({ failed: false });
    }
  }

  render() {
    if (this.state.failed) {
      return <span className="whitespace-pre-wrap">{this.props.content}</span>;
    }
    return this.props.children;
  }
}

interface MarkdownContentProps {
  content: string;
  streaming?: boolean;
  showCursor?: boolean;
}

export const MarkdownContent = memo(function MarkdownContent({
  content,
  streaming = false,
  showCursor = false,
}: MarkdownContentProps) {
  let normalized = content;
  try {
    normalized = normalizeMathDelimiters(content);
  } catch {
    normalized = content;
  }

  return (
    <div className={proseClassName}>
      <MarkdownErrorBoundary content={content}>
        <ReactMarkdown
          remarkPlugins={remarkPlugins}
          rehypePlugins={streaming ? [] : rehypePlugins}
          components={markdownComponents}
        >
          {normalized}
        </ReactMarkdown>
      </MarkdownErrorBoundary>
      {showCursor && (
        <span className="inline-block w-0.5 h-4 bg-primary ml-0.5 animate-pulse align-middle" />
      )}
    </div>
  );
});

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }, [text]);
  const label = copied ? i18n.t("messageBubble.copied") : i18n.t("messageBubble.copy");

  return (
    <button
      onClick={handleCopy}
      className="absolute top-2 right-2 p-1.5 rounded-md bg-muted/80 hover:bg-muted text-muted-foreground hover:text-foreground opacity-0 group-hover:opacity-100 focus-visible:opacity-100 transition-opacity"
      aria-label={label}
      title={label}
    >
      {copied ? <Check className="h-3.5 w-3.5 text-success" /> : <Copy className="h-3.5 w-3.5" />}
      {copied && (
        <span className="sr-only" role="status">
          {i18n.t("messageBubble.copied")}
        </span>
      )}
    </button>
  );
}

function getRetryHint(content: string): string {
  const lower = content.toLowerCase();
  if (lower.includes("timeout") || lower.includes("timed out")) {
    return i18n.t("messageBubble.timeoutHint");
  }
  if (lower.includes("api") || lower.includes("rate limit") || lower.includes("429") || lower.includes("500") || lower.includes("502") || lower.includes("503")) {
    return i18n.t("messageBubble.apiFailedHint");
  }
  return i18n.t("messageBubble.executionFailedHint");
}

interface Props {
  msg: StoredAgentMessage;
  onRetry?: (msg: AgentMessage) => void;
}

export const MessageBubble = memo(function MessageBubble({ msg, onRetry }: Props) {
  if (msg.type === "user") {
    const meta = msg.meta;
    return (
      <div className="flex justify-end group">
        <div className="max-w-[72%] max-h-[40vh] overflow-y-auto break-words rounded-[18px] bg-muted px-4 py-3 text-[15px] text-foreground leading-relaxed whitespace-pre-wrap">
          {meta && (meta.attachment || meta.swarmMode || meta.goalMode) && (
            <div className="mb-1.5 flex flex-wrap justify-end gap-1.5 text-[10px] leading-none text-muted-foreground">
              {meta.attachment && (
                <span
                  className="inline-flex max-w-full items-center gap-1 rounded-full bg-background/60 px-2 py-1 text-muted-foreground"
                  title={i18n.t("agent.attachmentChip" as never)}
                >
                  <Paperclip className="h-3 w-3 shrink-0" />
                  <span className="sr-only">{i18n.t("agent.attachmentChip" as never)}: </span>
                  <span className="truncate">{meta.attachment.filename}</span>
                </span>
              )}
              {meta.swarmMode && (
                <span className="inline-flex items-center gap-1 rounded-full bg-background/60 px-2 py-1 text-muted-foreground">
                  <Users className="h-3 w-3" />
                  {i18n.t("agent.swarmModeChip" as never)}
                </span>
              )}
              {meta.goalMode && (
                <span className="inline-flex items-center gap-1 rounded-full bg-background/60 px-2 py-1 text-muted-foreground">
                  <Target className="h-3 w-3" />
                  {i18n.t("agent.goalModeChip" as never)}
                </span>
              )}
            </div>
          )}
          {msg.content}
        </div>
      </div>
    );
  }

  if (msg.type === "answer") {
    return (
      <div className="flex gap-3 group relative">
        <AgentAvatar />
        <div className="flex-1 min-w-0 space-y-1.5">
          <CopyButton text={msg.content} />
          <MarkdownContent content={msg.content} />
        </div>
      </div>
    );
  }

  if (msg.type === "run_complete" && msg.runId) {
    return <RunCompleteCard msg={msg} />;
  }

  if (msg.type === "error") {
    const hint = getRetryHint(msg.content);
    return (
      <div className="flex gap-3">
        <AgentAvatar />
        <div className="space-y-2">
          <div className="flex items-start gap-2 rounded-xl border border-danger/30 bg-danger/5 px-4 py-3">
            <XCircle className="h-4 w-4 text-danger shrink-0 mt-0.5" />
            <p className="text-sm text-danger leading-relaxed">{msg.content}</p>
          </div>
          {onRetry && (
            <div className="space-y-1.5">
              <p className="text-xs leading-relaxed text-muted-foreground">{hint}</p>
              <button
                onClick={() => onRetry(msg)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-muted-foreground hover:text-foreground hover:bg-muted/80 border border-transparent hover:border-border transition-all"
                title={i18n.t("messageBubble.retry" as never)}
              >
                <RefreshCw className="h-3 w-3" />
                <span>{i18n.t("messageBubble.retry" as never)}</span>
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }

  // Fallback: show content for any unhandled message type
  if (msg.content) {
    return (
      <div className="flex gap-3">
        <AgentAvatar />
        <p className="text-sm text-muted-foreground leading-relaxed">{msg.content}</p>
      </div>
    );
  }

  return null;
});

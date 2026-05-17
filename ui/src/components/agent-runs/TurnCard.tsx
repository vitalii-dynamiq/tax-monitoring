import { useState } from "react";
import { ChevronDown, ChevronRight, Globe, FileCode, MessageSquare } from "lucide-react";
import Card from "../Card";
import Badge from "../Badge";
import JsonViewer from "./JsonViewer";
import TokenBreakdown from "./TokenBreakdown";
import { type AgentRunTurn } from "../../lib/api";
import { formatDateTime } from "../../lib/utils";

// Anthropic content-block shapes (loose — server may add fields we don't model)
interface ContentBlock {
  type: string;
  [k: string]: unknown;
}

interface WebSearchResult {
  url?: string;
  title?: string;
  page_age?: string;
  encrypted_content?: string;
}

function TextBlock({ text }: { text: string }) {
  return (
    <div className="text-sm leading-relaxed whitespace-pre-wrap text-text">
      {text}
    </div>
  );
}

function ToolUseBlock({ name, input }: { name: string; input: unknown }) {
  return (
    <div className="border border-accent/30 rounded-lg bg-accent-dim/30 p-3">
      <div className="flex items-center gap-2 mb-2">
        <FileCode className="w-4 h-4 text-accent" />
        <span className="text-xs font-semibold text-accent uppercase tracking-wide">
          Tool call: {name}
        </span>
      </div>
      <JsonViewer data={input} collapsed={true} maxHeight="20rem" />
    </div>
  );
}

function ServerToolUseBlock({ input }: { input?: { query?: string } }) {
  return (
    <div className="border border-warning/30 rounded-lg bg-warning/5 p-3">
      <div className="flex items-center gap-2">
        <Globe className="w-4 h-4 text-warning" />
        <span className="text-xs font-semibold text-warning uppercase tracking-wide">
          Web search
        </span>
        <span className="text-sm text-text font-mono">
          &ldquo;{input?.query ?? "—"}&rdquo;
        </span>
      </div>
    </div>
  );
}

function WebSearchResultBlock({ content }: { content?: WebSearchResult[] }) {
  if (!content || content.length === 0) {
    return <div className="text-xs text-dim italic">No results</div>;
  }
  return (
    <details className="border border-border rounded-lg bg-surface/40">
      <summary className="cursor-pointer px-3 py-2 text-xs font-semibold text-dim uppercase tracking-wide select-none hover:text-text">
        Search results ({content.length}) — click to expand
      </summary>
      <ol className="space-y-2 text-sm p-3 pt-0">
        {content.map((hit, i) => (
          <li key={i} className="border-l-2 border-border pl-3">
            <a
              href={hit.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent hover:underline font-medium"
            >
              {hit.title || hit.url || `Result ${i + 1}`}
            </a>
            {hit.url && (
              <div className="text-xs text-dim truncate font-mono mt-0.5">
                {hit.url}
              </div>
            )}
            {hit.page_age && (
              <div className="text-xs text-dim mt-0.5">{hit.page_age}</div>
            )}
          </li>
        ))}
      </ol>
    </details>
  );
}

function renderBlock(block: ContentBlock, idx: number): React.ReactNode {
  switch (block.type) {
    case "text":
      return <TextBlock key={idx} text={String(block.text ?? "")} />;
    case "tool_use":
      return (
        <ToolUseBlock
          key={idx}
          name={String(block.name ?? "")}
          input={block.input}
        />
      );
    case "server_tool_use":
      return (
        <ServerToolUseBlock
          key={idx}
          input={block.input as { query?: string } | undefined}
        />
      );
    case "web_search_tool_result":
      return (
        <WebSearchResultBlock
          key={idx}
          content={block.content as WebSearchResult[] | undefined}
        />
      );
    default:
      return (
        <div key={idx} className="text-xs text-dim">
          <span className="font-mono">[{block.type}]</span>
          <JsonViewer data={block} collapsed={true} maxHeight="12rem" />
        </div>
      );
  }
}

interface TurnCardProps {
  turn: AgentRunTurn;
}

export default function TurnCard({ turn }: TurnCardProps) {
  const [showRequest, setShowRequest] = useState(false);

  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-3 mb-3 flex-wrap">
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center justify-center w-8 h-8 rounded-full bg-accent-dim text-accent text-sm font-bold">
            {turn.turn_index + 1}
          </div>
          <div>
            <div className="flex items-center gap-2 text-sm">
              <MessageSquare className="w-4 h-4 text-dim" />
              <span className="font-semibold text-text">
                Assistant response
              </span>
              {turn.stop_reason && <Badge value={turn.stop_reason.replace(/_/g, " ")} />}
            </div>
            <div className="text-xs text-dim mt-0.5">
              {formatDateTime(turn.started_at)} · {turn.latency_ms.toLocaleString()}ms · {turn.model}
            </div>
          </div>
        </div>
        <TokenBreakdown
          inputTokens={turn.input_tokens}
          outputTokens={turn.output_tokens}
          cacheCreation={turn.cache_creation_input_tokens}
          cacheRead={turn.cache_read_input_tokens}
          webSearchCount={turn.web_search_count}
          compact
        />
      </div>

      <div className="space-y-3">
        {(turn.response_content as ContentBlock[]).map(renderBlock)}
      </div>

      <button
        className="mt-4 text-xs text-muted hover:text-text flex items-center gap-1"
        onClick={() => setShowRequest(!showRequest)}
      >
        {showRequest ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        {showRequest ? "Hide" : "Show"} request that produced this turn
      </button>
      {showRequest && (
        <div className="mt-2">
          <JsonViewer data={turn.request_messages} collapsed={false} maxHeight="20rem" />
        </div>
      )}
    </Card>
  );
}

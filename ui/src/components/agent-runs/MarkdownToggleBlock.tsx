import { useState } from "react";
import { Check, Copy } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownToggleBlockProps {
  title: string;
  text: string;
  /** Initial view mode. Default "rendered". */
  initial?: "rendered" | "raw";
}

/** Code/prompt block that renders Markdown by default, with a Raw toggle.
 *
 *  Used for system prompts and user prompts on the run-detail Overview tab.
 *  Includes a copy-to-clipboard button.
 */
export default function MarkdownToggleBlock({
  title,
  text,
  initial = "rendered",
}: MarkdownToggleBlockProps) {
  const [mode, setMode] = useState<"rendered" | "raw">(initial);
  const [copied, setCopied] = useState(false);

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      // ignore
    }
  };

  return (
    <div className="border border-border rounded-lg bg-card overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-surface/40">
        <span className="text-xs font-semibold uppercase tracking-widest text-dim">
          {title}
        </span>
        <div className="flex items-center gap-3">
          <div className="flex items-center bg-bg border border-border rounded-md overflow-hidden text-xs">
            <button
              className={
                "px-2.5 py-1 " +
                (mode === "rendered"
                  ? "bg-accent-dim text-accent"
                  : "text-muted hover:text-text")
              }
              onClick={() => setMode("rendered")}
            >
              Rendered
            </button>
            <button
              className={
                "px-2.5 py-1 border-l border-border " +
                (mode === "raw"
                  ? "bg-accent-dim text-accent"
                  : "text-muted hover:text-text")
              }
              onClick={() => setMode("raw")}
            >
              Raw
            </button>
          </div>
          <button
            className="flex items-center gap-1 text-xs text-muted hover:text-text"
            onClick={onCopy}
            title="Copy to clipboard"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-success" /> : <Copy className="w-3.5 h-3.5" />}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      </div>

      {mode === "rendered" ? (
        <div className="p-5 text-sm leading-relaxed text-text max-h-[36rem] overflow-auto prose-markdown">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
        </div>
      ) : (
        <pre className="text-sm text-text whitespace-pre-wrap p-4 max-h-[36rem] overflow-auto font-mono">
          {text}
        </pre>
      )}
    </div>
  );
}

import { useState } from "react";
import { Check, Copy } from "lucide-react";

interface JsonViewerProps {
  data: unknown;
  collapsed?: boolean;
  maxHeight?: string;
}

export default function JsonViewer({ data, collapsed = false, maxHeight = "24rem" }: JsonViewerProps) {
  const [open, setOpen] = useState(!collapsed);
  const [copied, setCopied] = useState(false);
  const text = JSON.stringify(data, null, 2);

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
    <div className="border border-border rounded-lg bg-bg/40 overflow-hidden">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-border bg-surface/40">
        <button
          className="text-xs text-muted hover:text-text font-mono uppercase tracking-wide"
          onClick={() => setOpen(!open)}
        >
          {open ? "▼" : "▶"} json ({text.length.toLocaleString()} chars)
        </button>
        <button
          className="flex items-center gap-1 text-xs text-muted hover:text-text"
          onClick={onCopy}
          title="Copy"
        >
          {copied ? <Check className="w-3.5 h-3.5 text-success" /> : <Copy className="w-3.5 h-3.5" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      {open && (
        <pre
          className="text-xs font-mono p-3 overflow-auto whitespace-pre-wrap text-muted"
          style={{ maxHeight }}
        >
          {text}
        </pre>
      )}
    </div>
  );
}

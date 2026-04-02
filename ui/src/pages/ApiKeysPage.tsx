import { useCallback, useEffect, useState, type FormEvent } from "react";
import { RiFileCopyLine, RiDeleteBinLine, RiKeyLine } from "react-icons/ri";
import Card from "../components/Card";
import Badge from "../components/Badge";
import DataTable from "../components/DataTable";
import ConfirmDialog from "../components/ConfirmDialog";
import PageTransition from "../components/PageTransition";
import { useToast } from "../hooks/useToast";
import { api, type ApiKeyResponse, type CreateApiKeyResponse } from "../lib/api";

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKeyResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [newKey, setNewKey] = useState<CreateApiKeyResponse | null>(null);
  const [copied, setCopied] = useState(false);
  const [revokeTarget, setRevokeTarget] = useState<ApiKeyResponse | null>(null);
  const [revoking, setRevoking] = useState(false);
  const { toast } = useToast();

  const fetchKeys = useCallback(async () => {
    try {
      const data = await api.apiKeys.list();
      setKeys(data);
    } catch {
      toast("Failed to load API keys", "error");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    fetchKeys();
  }, [fetchKeys]);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    try {
      const created = await api.apiKeys.create({ name: name.trim() });
      setNewKey(created);
      setName("");
      await fetchKeys();
      toast("API key created", "success");
    } catch {
      toast("Failed to create API key", "error");
    } finally {
      setCreating(false);
    }
  }

  async function handleRevoke() {
    if (!revokeTarget) return;
    setRevoking(true);
    try {
      await api.apiKeys.revoke(revokeTarget.id);
      setRevokeTarget(null);
      await fetchKeys();
      toast("API key revoked", "success");
    } catch {
      toast("Failed to revoke API key", "error");
    } finally {
      setRevoking(false);
    }
  }

  function copyKey() {
    if (!newKey) return;
    navigator.clipboard.writeText(newKey.raw_key);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const columns = [
    {
      key: "name",
      header: "Name",
      render: (row: ApiKeyResponse) => (
        <span className="font-medium text-text">{row.name}</span>
      ),
    },
    {
      key: "key_prefix",
      header: "Key",
      render: (row: ApiKeyResponse) => (
        <code className="text-xs font-mono bg-surface px-2 py-1 rounded">
          {row.key_prefix}...
        </code>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (row: ApiKeyResponse) => (
        <Badge value={row.is_active ? "active" : "revoked"} />
      ),
    },
    {
      key: "created_at",
      header: "Created",
      render: (row: ApiKeyResponse) =>
        new Date(row.created_at).toLocaleDateString(),
      hideBelow: "md" as const,
    },
    {
      key: "last_used_at",
      header: "Last Used",
      render: (row: ApiKeyResponse) =>
        row.last_used_at
          ? new Date(row.last_used_at).toLocaleDateString()
          : "Never",
      hideBelow: "md" as const,
    },
    {
      key: "actions",
      header: "",
      render: (row: ApiKeyResponse) =>
        row.is_active ? (
          <button
            onClick={(e) => {
              e.stopPropagation();
              setRevokeTarget(row);
            }}
            className="btn-ghost text-danger hover:text-danger p-1.5 rounded-md"
            title="Revoke key"
          >
            <RiDeleteBinLine className="w-4 h-4" />
          </button>
        ) : null,
      className: "w-12",
    },
  ];

  return (
    <PageTransition>
      <div className="p-6 lg:p-10 max-w-[960px] mx-auto space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-semibold text-text tracking-tight">
            API Keys
          </h1>
          <p className="text-sm text-muted mt-1">
            Create and manage API keys for programmatic access to the TaxLens
            API. Keys use the <code className="text-xs">X-API-Key</code> header.
          </p>
        </div>

        {/* Create form */}
        <Card className="p-5">
          <h2 className="card-title mb-4">Create New Key</h2>
          <form onSubmit={handleCreate} className="flex gap-3 items-end">
            <div className="flex-1">
              <label htmlFor="key-name" className="field-label">
                Key Name
              </label>
              <input
                id="key-name"
                type="text"
                className="input-field"
                placeholder="e.g., Production Integration"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                maxLength={100}
              />
            </div>
            <button
              type="submit"
              className="btn-primary whitespace-nowrap"
              disabled={creating || !name.trim()}
            >
              {creating ? "Creating..." : "Create Key"}
            </button>
          </form>
        </Card>

        {/* New key reveal */}
        {newKey && (
          <Card className="p-5 border-success/40 bg-success-dim/30 animate-slideUp">
            <div className="flex items-start gap-3">
              <RiKeyLine className="w-5 h-5 text-success mt-0.5 flex-shrink-0" />
              <div className="min-w-0 flex-1">
                <h3 className="text-sm font-semibold text-text mb-1">
                  Your new API key
                </h3>
                <p className="text-xs text-muted mb-3">
                  Copy this key now. You won't be able to see it again.
                </p>
                <div className="flex items-center gap-2">
                  <code className="flex-1 text-sm font-mono bg-card border border-border rounded px-3 py-2 break-all select-all">
                    {newKey.raw_key}
                  </code>
                  <button
                    onClick={copyKey}
                    className="btn-secondary flex items-center gap-1.5 px-3 py-2 text-sm flex-shrink-0"
                  >
                    <RiFileCopyLine className="w-4 h-4" />
                    {copied ? "Copied!" : "Copy"}
                  </button>
                </div>
                <button
                  onClick={() => setNewKey(null)}
                  className="mt-3 text-xs text-muted hover:text-text transition-colors"
                >
                  Dismiss
                </button>
              </div>
            </div>
          </Card>
        )}

        {/* Keys table */}
        <Card>
          <div className="px-5 py-4 border-b border-border">
            <h2 className="card-title">Your Keys</h2>
          </div>
          <DataTable
            columns={columns}
            data={keys}
            loading={loading}
            emptyMessage="No API keys yet. Create one above."
            emptyIcon={RiKeyLine}
          />
        </Card>

      </div>

      {/* Revoke confirmation */}
      <ConfirmDialog
        open={!!revokeTarget}
        title="Revoke API Key"
        message={`Are you sure you want to revoke "${revokeTarget?.name}"? Any integrations using this key will stop working immediately.`}
        confirmLabel="Revoke"
        variant="danger"
        loading={revoking}
        onConfirm={handleRevoke}
        onCancel={() => setRevokeTarget(null)}
      />
    </PageTransition>
  );
}

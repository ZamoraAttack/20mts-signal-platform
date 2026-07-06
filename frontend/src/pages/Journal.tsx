import { useEffect, useState } from "react";
import { Card } from "../components/Card";
import { api } from "../lib/api";
import { formatTime } from "../lib/format";
import type { JournalEntryRead } from "../lib/types";

const ENTRY_TYPES = ["observation", "note", "rule", "question"];

export function Journal() {
  const [entries, setEntries] = useState<JournalEntryRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [entryType, setEntryType] = useState("observation");
  const [body, setBody] = useState("");
  const [saving, setSaving] = useState(false);

  const refresh = () => {
    setLoading(true);
    api
      .listJournal()
      .then(setEntries)
      .finally(() => setLoading(false));
  };

  useEffect(refresh, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!body.trim()) return;
    setSaving(true);
    try {
      await api.createJournalEntry({ entry_type: entryType, body: body.trim() });
      setBody("");
      refresh();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-white">Journal</h1>
        <p className="text-sm text-gray-500">
          Freeform notes, observations, and rules captured while reviewing signals.
        </p>
      </div>

      <Card title="New Entry">
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div className="flex gap-2">
            {ENTRY_TYPES.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setEntryType(t)}
                className={`rounded-full border px-3 py-1 text-xs font-medium capitalize transition-colors ${
                  entryType === t
                    ? "border-violet-500/40 bg-violet-500/15 text-violet-300"
                    : "border-white/10 text-gray-400 hover:bg-white/5"
                }`}
              >
                {t}
              </button>
            ))}
          </div>
          <textarea
            rows={3}
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Write your note…"
            className="input resize-y"
          />
          <div>
            <button
              type="submit"
              disabled={saving || !body.trim()}
              className="rounded-lg bg-violet-500 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-violet-400 disabled:opacity-50"
            >
              {saving ? "Saving…" : "Add Entry"}
            </button>
          </div>
        </form>
      </Card>

      <Card title="Entries">
        {loading ? (
          <p className="text-sm text-gray-500">Loading…</p>
        ) : entries.length === 0 ? (
          <p className="text-sm text-gray-500">No journal entries yet.</p>
        ) : (
          <ul className="flex flex-col gap-3">
            {entries.map((entry) => (
              <li key={entry.id} className="rounded-lg border border-white/10 bg-white/[0.02] p-3 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="rounded-full border border-white/10 px-2 py-0.5 text-xs font-medium capitalize text-gray-400">
                    {entry.entry_type}
                  </span>
                  <span className="font-mono text-xs text-gray-500">
                    {new Date(entry.entry_time).toLocaleString([], { hour12: false })}
                  </span>
                </div>
                <p className="mt-2 whitespace-pre-wrap text-gray-200">{entry.body}</p>
                {entry.signal_id && (
                  <p className="mt-1 font-mono text-xs text-gray-500">
                    Signal {entry.signal_id.slice(0, 8)} · {formatTime(entry.entry_time)}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

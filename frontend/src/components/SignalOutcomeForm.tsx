import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { SignalOutcomeUpsert, SignalRead, SignalSuggestionRead } from "../lib/types";

const U_SHAPE_OPTIONS = ["none", "sub_1min", "1min", "2min", "3min"];

const EMPTY: SignalOutcomeUpsert = {
  price_at_signal: 0,
  price_peak_20min: null,
  price_at_20min: null,
  max_gain_pct: null,
  gain_at_20min_pct: null,
  seconds_to_peak: null,
  was_successful: null,
  was_red_herring: false,
  u_shape_type: "none",
  notes: "",
};

function toNumberOrNull(value: string): number | null {
  if (value.trim() === "") return null;
  const n = Number(value);
  return Number.isNaN(n) ? null : n;
}

export function SignalOutcomeForm({
  signal,
  suggestion,
}: {
  signal: SignalRead;
  suggestion?: SignalSuggestionRead;
}) {
  const [form, setForm] = useState<SignalOutcomeUpsert>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setForm({
      ...EMPTY,
      price_at_signal: signal.signal_stock_price ?? signal.divergence_stock_price ?? 0,
    });

    api
      .getSignalOutcome(signal.id)
      .then((outcome) => {
        if (!cancelled) {
          setForm({
            price_at_signal: outcome.price_at_signal,
            price_peak_20min: outcome.price_peak_20min ?? null,
            price_at_20min: outcome.price_at_20min ?? null,
            max_gain_pct: outcome.max_gain_pct ?? null,
            gain_at_20min_pct: outcome.gain_at_20min_pct ?? null,
            seconds_to_peak: outcome.seconds_to_peak ?? null,
            was_successful: outcome.was_successful ?? null,
            was_red_herring: outcome.was_red_herring,
            u_shape_type: outcome.u_shape_type ?? "none",
            notes: outcome.notes ?? "",
          });
        }
      })
      .catch(() => {
        // No outcome recorded yet — keep defaults.
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [signal]);

  const handleApplySuggestion = () => {
    if (!suggestion) return;
    // classification === "needs_review" deliberately leaves was_successful
    // untouched -- that's the genuinely ambiguous case meant to force an
    // explicit human choice, not get defaulted either way.
    const suggestedSuccess =
      suggestion.classification === "likely_success"
        ? true
        : suggestion.classification === "likely_failure"
          ? false
          : form.was_successful;
    setForm({
      ...form,
      was_successful: suggestedSuccess,
      was_red_herring: suggestion.suggested_was_red_herring ?? form.was_red_herring,
      u_shape_type: suggestion.suggested_u_shape_type ?? form.u_shape_type,
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.upsertSignalOutcome(signal.id, form);
      setSavedAt(Date.now());
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <p className="text-sm text-gray-500">Loading outcome…</p>;
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Field label="Price at Signal">
          <input
            type="number"
            step="0.0001"
            required
            value={form.price_at_signal ?? ""}
            onChange={(e) => setForm({ ...form, price_at_signal: toNumberOrNull(e.target.value) })}
            className="input"
          />
        </Field>
        <Field label="Peak (20 min)">
          <input
            type="number"
            step="0.0001"
            value={form.price_peak_20min ?? ""}
            onChange={(e) => setForm({ ...form, price_peak_20min: toNumberOrNull(e.target.value) })}
            className="input"
          />
        </Field>
        <Field label="Price at 20 min">
          <input
            type="number"
            step="0.0001"
            value={form.price_at_20min ?? ""}
            onChange={(e) => setForm({ ...form, price_at_20min: toNumberOrNull(e.target.value) })}
            className="input"
          />
        </Field>
        <Field label="Max Gain %">
          <input
            type="number"
            step="0.01"
            value={form.max_gain_pct ?? ""}
            onChange={(e) => setForm({ ...form, max_gain_pct: toNumberOrNull(e.target.value) })}
            className="input"
          />
        </Field>
        <Field label="Gain at 20 min %">
          <input
            type="number"
            step="0.01"
            value={form.gain_at_20min_pct ?? ""}
            onChange={(e) => setForm({ ...form, gain_at_20min_pct: toNumberOrNull(e.target.value) })}
            className="input"
          />
        </Field>
        <Field label="Seconds to Peak">
          <input
            type="number"
            step="1"
            value={form.seconds_to_peak ?? ""}
            onChange={(e) => setForm({ ...form, seconds_to_peak: toNumberOrNull(e.target.value) })}
            className="input"
          />
        </Field>
      </div>

      {suggestion && suggestion.suggested_u_shape_type !== null && (
        <div className="flex items-center justify-between rounded-md border border-violet-500/20 bg-violet-500/5 px-3 py-2">
          <p className="text-xs text-gray-400">
            Suggested: classification = <span className="text-gray-200">{suggestion.classification}</span>,
            {" "}red herring = <span className="text-gray-200">{String(suggestion.suggested_was_red_herring)}</span>,
            {" "}u-shape = <span className="text-gray-200">{suggestion.suggested_u_shape_type}</span>
          </p>
          <button
            type="button"
            onClick={handleApplySuggestion}
            className="rounded-md border border-violet-500/30 bg-violet-500/10 px-2 py-1 text-xs text-violet-300 hover:bg-violet-500/20"
          >
            Apply suggestion
          </button>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Field label="Was Successful">
          <select
            value={form.was_successful === null ? "unknown" : String(form.was_successful)}
            onChange={(e) =>
              setForm({
                ...form,
                was_successful: e.target.value === "unknown" ? null : e.target.value === "true",
              })
            }
            className="input"
          >
            <option value="unknown">Unknown</option>
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </Field>
        <Field label="Red Herring">
          <select
            value={String(form.was_red_herring)}
            onChange={(e) => setForm({ ...form, was_red_herring: e.target.value === "true" })}
            className="input"
          >
            <option value="false">No</option>
            <option value="true">Yes</option>
          </select>
        </Field>
        <Field label="U-Shape Type">
          <select
            value={form.u_shape_type ?? "none"}
            onChange={(e) => setForm({ ...form, u_shape_type: e.target.value })}
            className="input"
          >
            {U_SHAPE_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        </Field>
      </div>

      <Field label="Notes">
        <textarea
          rows={3}
          value={form.notes ?? ""}
          onChange={(e) => setForm({ ...form, notes: e.target.value })}
          className="input resize-y"
        />
      </Field>

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={saving}
          className="rounded-lg bg-violet-500 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-violet-400 disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save Outcome"}
        </button>
        {savedAt && <span className="text-xs text-emerald-400">Saved</span>}
      </div>
    </form>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-xs text-gray-400">
      {label}
      {children}
    </label>
  );
}

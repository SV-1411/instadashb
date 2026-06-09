import { useState } from "react";
import { postGroundInput, type GroundInputResult } from "../lib/api";
import { usePolitician } from "../lib/PoliticianContext";

// WP11: manual ground-intelligence entry (fills the WhatsApp gap — no API exists).
export function GroundInput() {
  const { selected } = usePolitician();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<GroundInputResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!selected) return <p className="text-slate-500">No connected account.</p>;

  async function submit() {
    if (!text.trim() || !selected) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const r = await postGroundInput(selected.id, text.trim());
      setResult(r);
      setText("");
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-xl space-y-4">
      <div>
        <h2 className="text-2xl font-semibold text-ink">Ground Intelligence</h2>
        <p className="text-slate-500">
          Log what your team hears on the ground (WhatsApp, door-to-door, local press). It flows
          through the same sentiment, topic and geo pipeline as social mentions.
        </p>
      </div>

      <textarea
        className="h-32 w-full rounded-lg border border-slate-300 p-3 text-sm"
        placeholder="e.g. Angry crowd about water shortage in Pune ward 12 today"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <button
        onClick={submit}
        disabled={busy || !text.trim()}
        className="rounded-lg bg-pulse px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        {busy ? "Saving…" : "Add ground report"}
      </button>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {result && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-slate-700">
          ✓ Saved. Sentiment: <strong>{result.sentiment_label}</strong>
          {result.inferred_city && (
            <>
              {" "}
              · city: <strong>{result.inferred_city}</strong>
            </>
          )}
          {result.topics.length > 0 && <> · topics: {result.topics.join(", ")}</>}
        </div>
      )}
    </div>
  );
}

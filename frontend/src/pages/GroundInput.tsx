import { useState } from "react";
import { postGroundInput, type GroundInputResult } from "../lib/api";
import { usePolitician } from "../lib/PoliticianContext";

export function GroundInput() {
  const { selected } = usePolitician();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<GroundInputResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!selected) return <p className="text-mocha">No connected account.</p>;

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
    <div className="max-w-xl space-y-5">
      <div>
        <h2 className="text-2xl font-extrabold text-ink">Ground Intelligence</h2>
        <p className="text-coffee/70">
          Log what your team hears on the ground (WhatsApp, door-to-door, local press). It flows
          through the same sentiment, topic and geo pipeline as social mentions.
        </p>
      </div>

      <div className="glass-card sheen p-4">
        <textarea
          className="h-32 w-full rounded-xl border border-white/50 bg-white/40 p-3 text-sm text-ink outline-none placeholder:text-mocha/70 focus:bg-white/60"
          placeholder="e.g. Angry crowd about water shortage in Pune ward 12 today"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <button
          onClick={submit}
          disabled={busy || !text.trim()}
          className="mt-3 rounded-xl bg-pulse px-4 py-2 text-sm font-semibold text-white shadow-glass transition hover:opacity-90 disabled:opacity-50"
        >
          {busy ? "Saving…" : "Add ground report"}
        </button>
      </div>

      {error && <p className="text-sm text-red-700">{error}</p>}
      {result && (
        <div className="glass-card sheen border-green-300/50 p-3 text-sm text-ink">
          ✓ Saved. Sentiment: <strong>{result.sentiment_label}</strong>
          {result.inferred_city && (
            <>
              {" "}
              · city: <strong>{result.inferred_city}</strong>
            </>
          )}
          {result.topics.length > 0 && <> · topics: {result.topics.map((t) => `#${t}`).join(" ")}</>}
        </div>
      )}
    </div>
  );
}

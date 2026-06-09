// Reusable stub for a not-yet-built module (WP1). Real modules replace these.
export function ModulePlaceholder({ title, blurb, wp }: { title: string; blurb: string; wp: string }) {
  return (
    <div className="max-w-2xl">
      <h2 className="text-2xl font-semibold text-ink">{title}</h2>
      <p className="mt-1 text-slate-500">{blurb}</p>
      <div className="mt-6 rounded-lg border border-dashed border-slate-300 bg-white p-8 text-center">
        <p className="text-slate-400">Module shell — wired in {wp}.</p>
      </div>
    </div>
  );
}

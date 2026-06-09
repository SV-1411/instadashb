import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getTrends } from "../lib/api";
import { usePolitician } from "../lib/PoliticianContext";
import { useData } from "../lib/useData";

export function Trends() {
  const { selected } = usePolitician();
  const { data, loading, error } = useData(() => getTrends(selected!.id), selected?.id);

  if (!selected) return <p className="text-slate-500">No connected account.</p>;
  if (loading) return <p className="text-slate-500">Loading trends…</p>;
  if (error || !data) return <p className="text-red-600">Could not load: {error}</p>;

  const topics = data.top_topics.map((t) => ({ topic: t.topic, count: t.count }));
  const series = data.series.map((s) => ({
    t: new Date(s.bucket_hour).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit" }),
    negative: s.negative,
    total: s.total,
  }));

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-ink">Trends</h2>
        <p className="text-slate-500">Topics and volume over the last 48h for {selected.name}</p>
      </div>

      <div className="glass-card sheen p-4">
        <div className="mb-3 text-sm font-medium text-slate-600">Top topics</div>
        {topics.length ? (
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={topics} layout="vertical" margin={{ left: 24 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis type="number" tick={{ fontSize: 12 }} />
              <YAxis type="category" dataKey="topic" tick={{ fontSize: 12 }} width={90} />
              <Tooltip />
              <Bar dataKey="count" fill="#2563eb" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-sm text-slate-400">No topics tagged yet.</p>
        )}
      </div>

      <div className="glass-card sheen p-4">
        <div className="mb-3 text-sm font-medium text-slate-600">Mention volume (negative vs total)</div>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={series}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
            <XAxis dataKey="t" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Line type="monotone" dataKey="total" stroke="#2563eb" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="negative" stroke="#dc2626" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

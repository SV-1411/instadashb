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

const ACCENT = "#A9764E";
const NEG = "#c0392b";
const GRID = "rgba(111,78,55,0.12)";
const AXIS = "#6F4E37";

export function Trends() {
  const { selected } = usePolitician();
  const { data, loading, error } = useData(() => getTrends(selected!.id), selected?.id);

  if (!selected) return <p className="text-mocha">No connected account.</p>;
  if (loading) return <p className="text-mocha">Loading trends…</p>;
  if (error || !data) return <p className="text-red-700">Could not load: {error}</p>;

  const topics = data.top_topics.map((t) => ({ topic: t.topic, count: t.count }));
  const series = data.series.map((s) => ({
    t: new Date(s.bucket_hour).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit" }),
    negative: s.negative,
    total: s.total,
  }));

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-2xl font-extrabold text-ink">Trends</h2>
        <p className="text-coffee/70">Topics and volume over the last 48h for {selected.name}</p>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {topics.slice(0, 6).map((t) => (
          <div key={t.topic} className="kpi sheen">
            <div className="text-2xl font-extrabold text-pulse">{t.count}</div>
            <div className="truncate text-xs uppercase tracking-wide text-mocha">#{t.topic}</div>
          </div>
        ))}
      </div>

      <div className="glass-card sheen p-4">
        <div className="mb-3 text-sm font-semibold text-coffee/80">Top topics</div>
        {topics.length ? (
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={topics} layout="vertical" margin={{ left: 24 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
              <XAxis type="number" tick={{ fontSize: 12, fill: AXIS }} />
              <YAxis type="category" dataKey="topic" tick={{ fontSize: 12, fill: AXIS }} width={90} />
              <Tooltip />
              <Bar dataKey="count" fill={ACCENT} radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <p className="text-sm text-mocha">No topics tagged yet.</p>
        )}
      </div>

      <div className="glass-card sheen p-4">
        <div className="mb-3 text-sm font-semibold text-coffee/80">
          Mention volume (negative vs total)
        </div>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={series}>
            <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
            <XAxis dataKey="t" tick={{ fontSize: 11, fill: AXIS }} />
            <YAxis tick={{ fontSize: 12, fill: AXIS }} />
            <Tooltip />
            <Line type="monotone" dataKey="total" stroke={ACCENT} strokeWidth={3} dot={false} />
            <Line type="monotone" dataKey="negative" stroke={NEG} strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

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
import { IndiaMap } from "../components/IndiaMap";
import { exportCsvUrl, getGeo, getGrowth, getIdentity } from "../lib/api";
import { usePolitician } from "../lib/PoliticianContext";
import { useData } from "../lib/useData";

export function YourIdentity() {
  const { selected } = usePolitician();
  const id = selected?.id;
  const { data, loading, error } = useData(() => getIdentity(id!), id);
  const { data: geo } = useData(() => getGeo(id!), id);
  const { data: growth } = useData(() => getGrowth(id!), id);

  if (!selected) return <p className="text-slate-500">No connected account.</p>;
  if (loading) return <p className="text-slate-500">Loading identity…</p>;
  if (error || !data) return <p className="text-red-600">Could not load: {error}</p>;

  const growthSeries = (growth?.series ?? []).map((s) => ({
    day: s.day.slice(5),
    reach: s.reach,
    engagement: s.engagement,
  }));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-ink">Your Identity</h2>
          <p className="text-slate-500">Reach, audience and top posts for {selected.name}</p>
        </div>
        <a
          href={exportCsvUrl(selected.id)}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
        >
          ⬇ Export CSV
        </a>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="glass-card sheen p-4">
          <div className="mb-2 text-sm font-medium text-slate-600">Where the conversation is</div>
          <IndiaMap cities={geo?.cities ?? []} />
        </div>
        <div className="glass-card sheen p-4">
          <div className="mb-3 text-sm font-medium text-slate-600">Reach &amp; engagement (14d)</div>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={growthSeries}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis dataKey="day" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Line type="monotone" dataKey="reach" stroke="#2563eb" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="engagement" stroke="#16a34a" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
          <div className="mt-4 text-sm font-medium text-slate-600">Audience by city (follower %)</div>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={data.audience.map((c) => ({ city: c.city, pct: c.follower_pct }))}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis dataKey="city" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="pct" fill="#2563eb" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="glass-card sheen p-4">
        <div className="mb-3 text-sm font-medium text-slate-600">Top posts by engagement</div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase text-slate-400">
              <th className="py-2">Post</th>
              <th>Platform</th>
              <th className="text-right">Likes</th>
              <th className="text-right">Comments</th>
              <th className="text-right">Reach</th>
              <th className="text-right">Engagement</th>
            </tr>
          </thead>
          <tbody>
            {data.top_posts.map((p) => (
              <tr key={p.post_id} className="border-t">
                <td className="py-2 font-mono text-xs text-slate-500">{p.post_id.slice(0, 16)}…</td>
                <td className="uppercase">{p.platform}</td>
                <td className="text-right">{p.likes.toLocaleString()}</td>
                <td className="text-right">{p.comments_count.toLocaleString()}</td>
                <td className="text-right">{p.reach.toLocaleString()}</td>
                <td className="text-right font-semibold text-pulse">
                  {p.engagement.toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

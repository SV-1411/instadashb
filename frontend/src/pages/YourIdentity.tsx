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

const ACCENT = "#A9764E";
const POS = "#4f8a5b";
const GRID = "rgba(111,78,55,0.12)";
const AXIS = "#6F4E37";

export function YourIdentity() {
  const { selected } = usePolitician();
  const id = selected?.id;
  const { data, loading, error } = useData(() => getIdentity(id!), id);
  const { data: geo } = useData(() => getGeo(id!), id);
  const { data: growth } = useData(() => getGrowth(id!), id);

  if (!selected) return <p className="text-mocha">No connected account.</p>;
  if (loading) return <p className="text-mocha">Loading identity…</p>;
  if (error || !data) return <p className="text-red-700">Could not load: {error}</p>;

  const growthSeries = (growth?.series ?? []).map((s) => ({
    day: s.day.slice(5),
    reach: s.reach,
    engagement: s.engagement,
  }));

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-extrabold text-ink">Your Identity</h2>
          <p className="text-coffee/70">Reach, audience and top posts for {selected.name}</p>
        </div>
        <a
          href={exportCsvUrl(selected.id)}
          className="glass-soft rounded-xl px-3 py-1.5 text-sm font-medium text-coffee hover:bg-white/60"
        >
          ⬇ Export CSV
        </a>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <div className="glass-card sheen p-4">
          <div className="mb-2 text-sm font-semibold text-coffee/80">Where the conversation is</div>
          <IndiaMap cities={geo?.cities ?? []} />
        </div>
        <div className="space-y-5">
          <div className="glass-card sheen p-4">
            <div className="mb-3 text-sm font-semibold text-coffee/80">Reach &amp; engagement (14d)</div>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={growthSeries}>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                <XAxis dataKey="day" tick={{ fontSize: 11, fill: AXIS }} />
                <YAxis tick={{ fontSize: 11, fill: AXIS }} />
                <Tooltip />
                <Line type="monotone" dataKey="reach" stroke={ACCENT} strokeWidth={3} dot={false} />
                <Line type="monotone" dataKey="engagement" stroke={POS} strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="glass-card sheen p-4">
            <div className="mb-3 text-sm font-semibold text-coffee/80">Audience by city (follower %)</div>
            <ResponsiveContainer width="100%" height={170}>
              <BarChart data={data.audience.map((c) => ({ city: c.city, pct: c.follower_pct }))}>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                <XAxis dataKey="city" tick={{ fontSize: 10, fill: AXIS }} />
                <YAxis tick={{ fontSize: 11, fill: AXIS }} />
                <Tooltip />
                <Bar dataKey="pct" fill={ACCENT} radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="glass-card sheen p-4">
        <div className="mb-3 text-sm font-semibold text-coffee/80">Top posts by engagement</div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase text-mocha">
              <th className="py-2">Post</th>
              <th>Platform</th>
              <th className="text-right">Likes</th>
              <th className="text-right">Comments</th>
              <th className="text-right">Reach</th>
              <th className="text-right">Engagement</th>
            </tr>
          </thead>
          <tbody className="text-coffee/90">
            {data.top_posts.map((p) => (
              <tr key={p.post_id} className="border-t border-coffee/10">
                <td className="py-2 font-mono text-xs text-mocha">{p.post_id.slice(0, 16)}…</td>
                <td className="uppercase">{p.platform}</td>
                <td className="text-right">{p.likes.toLocaleString()}</td>
                <td className="text-right">{p.comments_count.toLocaleString()}</td>
                <td className="text-right">{p.reach.toLocaleString()}</td>
                <td className="text-right font-bold text-pulse">{p.engagement.toLocaleString()}</td>
              </tr>
            ))}
            {!data.top_posts.length && (
              <tr>
                <td colSpan={6} className="py-3 text-center text-mocha">
                  No posts ingested yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

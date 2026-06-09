import { useState } from "react";

export interface MapCity {
  city: string;
  lat: number;
  lon: number;
  mentions: number;
  negative: number;
  avg_sentiment: number; // -1..1
}

const W = 360;
const H = 420;
const LON_MIN = 68;
const LON_MAX = 98;
const LAT_MIN = 6;
const LAT_MAX = 37;

function project(lat: number, lon: number): [number, number] {
  const x = ((lon - LON_MIN) / (LON_MAX - LON_MIN)) * W;
  const y = ((LAT_MAX - lat) / (LAT_MAX - LAT_MIN)) * H;
  return [x, y];
}

function tone(negRatio: number): string {
  if (negRatio >= 0.5) return "#c0392b";
  if (negRatio >= 0.25) return "#cf8a3b";
  return "#4f8a5b";
}

function sentimentLabel(s: number): string {
  if (s > 0.15) return "Positive";
  if (s < -0.15) return "Negative";
  return "Neutral";
}

export function IndiaMap({ cities }: { cities: MapCity[] }) {
  const [zoom, setZoom] = useState(1);
  const [hover, setHover] = useState<MapCity | null>(null);
  const max = Math.max(1, ...cities.map((c) => c.mentions));

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-[420px] w-full select-none">
        <defs>
          <radialGradient id="seaGlow" cx="35%" cy="20%">
            <stop offset="0%" stopColor="rgba(255,255,255,0.5)" />
            <stop offset="100%" stopColor="rgba(201,162,126,0.10)" />
          </radialGradient>
        </defs>
        <rect x={0} y={0} width={W} height={H} rx={16} fill="url(#seaGlow)" />
        <g
          style={{ transition: "transform 0.25s ease" }}
          transform={`translate(${W / 2} ${H / 2}) scale(${zoom}) translate(${-W / 2} ${-H / 2})`}
        >
          {cities.map((c) => {
            const [x, y] = project(c.lat, c.lon);
            const negRatio = c.mentions ? c.negative / c.mentions : 0;
            const r = (6 + (c.mentions / max) * 26) * (hover?.city === c.city ? 1.25 : 1);
            const col = tone(negRatio);
            return (
              <g
                key={c.city}
                onMouseEnter={() => setHover(c)}
                onMouseLeave={() => setHover(null)}
                style={{ cursor: "pointer" }}
              >
                <circle
                  cx={x}
                  cy={y}
                  r={r}
                  fill={col}
                  fillOpacity={hover?.city === c.city ? 0.65 : 0.4}
                  stroke={col}
                  strokeWidth={hover?.city === c.city ? 2 : 1}
                  style={{ transition: "all 0.15s ease" }}
                />
                <text x={x} y={y - r - 4} fontSize={10 / Math.sqrt(zoom)} textAnchor="middle" fill="#6F4E37">
                  {c.city}
                </text>
              </g>
            );
          })}
        </g>
        {!cities.length && (
          <text x={W / 2} y={H / 2} textAnchor="middle" fill="#9A7B5B" fontSize={12}>
            No geo-tagged mentions yet
          </text>
        )}
      </svg>

      {/* Zoom controls */}
      <div className="absolute bottom-2 right-2 flex gap-1">
        {[
          { l: "−", f: () => setZoom((z) => Math.max(1, +(z - 0.5).toFixed(1))) },
          { l: "⟳", f: () => setZoom(1) },
          { l: "+", f: () => setZoom((z) => Math.min(4, +(z + 0.5).toFixed(1))) },
        ].map((b) => (
          <button
            key={b.l}
            onClick={b.f}
            className="glass-soft h-7 w-7 rounded-lg text-coffee hover:bg-white/60"
          >
            {b.l}
          </button>
        ))}
      </div>

      {/* Hover detail panel */}
      <div className="glass-soft absolute left-2 top-2 w-44 rounded-xl p-3 text-xs">
        {hover ? (
          <>
            <div className="text-sm font-bold text-ink">{hover.city}</div>
            <div className="mt-1 text-coffee/80">{hover.mentions} mentions tracked</div>
            <div className="text-coffee/80">{hover.negative} negative</div>
            <div className="mt-1 flex items-center gap-2">
              <span className="font-medium" style={{ color: tone(hover.mentions ? hover.negative / hover.mentions : 0) }}>
                {sentimentLabel(hover.avg_sentiment)}
              </span>
              <span className="text-mocha">({hover.avg_sentiment.toFixed(2)})</span>
            </div>
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-white/50">
              <div
                className="h-full"
                style={{
                  width: `${Math.round((hover.mentions ? hover.negative / hover.mentions : 0) * 100)}%`,
                  background: "#c0392b",
                }}
              />
            </div>
          </>
        ) : (
          <span className="text-mocha">Hover a city · zoom with + / −</span>
        )}
      </div>
    </div>
  );
}

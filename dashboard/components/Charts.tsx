"use client";
// SVG charts ported from the Broadcast moodboard (concept C): smooth area lines, rings, sparklines, bars.
import { useId, useMemo, useRef, useState } from "react";

type Pt = [number, number];

export function smooth(p: Pt[]): string {
  if (!p.length) return "";
  let d = `M${p[0][0]},${p[0][1]}`;
  for (let i = 0; i < p.length - 1; i++) {
    const a = p[i - 1] ?? p[i], b = p[i], c = p[i + 1], e = p[i + 2] ?? c;
    d += `C${b[0] + (c[0] - a[0]) / 6},${b[1] + (c[1] - a[1]) / 6} ${c[0] - (e[0] - b[0]) / 6},${c[1] - (e[1] - b[1]) / 6} ${c[0]},${c[1]}`;
  }
  return d;
}

export function Ring({ pct, size = 52, w = 5, color = "var(--acc)", label, text }: {
  pct: number; size?: number; w?: number; color?: string; label: string; text?: string;
}) {
  const p = Math.max(0, Math.min(100, pct));
  const r = (size - w) / 2, L = 2 * Math.PI * r;
  return (
    <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} role="img" aria-label={label}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" className="rtrack" strokeWidth={w} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" style={{ stroke: color, transition: "stroke-dasharray .6s" }} strokeWidth={w}
        strokeLinecap="round" strokeDasharray={`${(L * p) / 100} ${L}`} transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      <text x="50%" y="50%" textAnchor="middle" dominantBaseline="central" className="rt" fontSize={size * (text && text.length > 4 ? 0.17 : 0.24)}>
        {text ?? `${Math.round(p)}%`}
      </text>
    </svg>
  );
}

export function Spark({ data, color = "var(--acc)" }: { data: number[]; color?: string }) {
  if (data.length < 2) return null;
  const W = 96, H = 28, mx = Math.max(...data), mn = Math.min(...data);
  const p = data.map((v, i): Pt => [(W * i) / (data.length - 1), H - 3 - ((H - 6) * (v - mn)) / (mx - mn || 1)]);
  return <svg viewBox={`0 0 ${W} ${H}`} aria-hidden="true"><path d={smooth(p)} fill="none" style={{ stroke: color }} strokeWidth={1.8} strokeLinecap="round" /></svg>;
}

export type Series = { name: string; color: string; values: number[] };

/** Area line chart with hover readout. `labels` has one entry per point ("" hides the tick). */
export function LineChart({ series, labels, height = 240, fmt = (v) => String(v), empty = "No data yet" }: {
  series: Series[]; labels: string[]; height?: number; fmt?: (v: number) => string; empty?: string;
}) {
  const id = useId().replace(/:/g, "");
  const ref = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const W = 640, H = height, pl = 44, pr = 12, pt = 18, pb = 26, iw = W - pl - pr, ih = H - pt - pb;
  const n = Math.max(0, ...series.map((s) => s.values.length));
  const all = series.flatMap((s) => s.values);
  const { mx, mn } = useMemo(() => {
    if (!all.length) return { mx: 1, mn: 0 };
    const hi = Math.max(...all), lo = Math.min(...all);
    const pad = (hi - lo) * 0.12 || hi * 0.1 || 1;
    return { mx: hi + pad, mn: Math.max(0, lo - pad) };
  }, [all]);
  if (n < 2) {
    return <div className="ch"><svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={empty}><text x={W / 2} y={H / 2} textAnchor="middle" className="empty">{empty}</text></svg></div>;
  }
  const X = (i: number) => pl + (iw * i) / (n - 1);
  const Y = (v: number) => pt + ih * (1 - (v - mn) / (mx - mn || 1));
  const move = (e: React.PointerEvent) => {
    const r = ref.current?.getBoundingClientRect();
    if (!r) return;
    const x = ((e.clientX - r.left) / r.width) * W;
    setHover(Math.max(0, Math.min(n - 1, Math.round(((x - pl) / iw) * (n - 1)))));
  };
  const s0 = series[0];
  return (
    <div className="ch">
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${series.map((s) => s.name).join(" and ")} chart`}
        onPointerMove={move} onPointerLeave={() => setHover(null)}>
        <defs>
          {series.map((s, j) => (
            <linearGradient key={j} id={`g${id}${j}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" style={{ stopColor: s.color, stopOpacity: j ? 0.12 : 0.34 }} />
              <stop offset="1" style={{ stopColor: s.color, stopOpacity: 0 }} />
            </linearGradient>
          ))}
        </defs>
        {[0, 1, 2, 3, 4].map((i) => {
          const y = pt + (ih * i) / 4;
          return <g key={i}><line x1={pl} x2={W - pr} y1={y} y2={y} className="gl" />
            <text x={pl - 8} y={y + 4} textAnchor="end" className="ax">{fmt(mx - ((mx - mn) * i) / 4)}</text></g>;
        })}
        {labels.map((t, i) => (t ? <text key={i} x={X(i)} y={H - 7} textAnchor="middle" className="ax">{t}</text> : null))}
        {series.map((s, j) => {
          const p = s.values.map((v, i): Pt => [X(i), Y(v)]);
          const d = smooth(p), e = p[p.length - 1];
          return (
            <g key={j}>
              <path d={`${d}L${X(s.values.length - 1)},${pt + ih}L${X(0)},${pt + ih}Z`} fill={`url(#g${id}${j})`} />
              <path d={d} fill="none" style={{ stroke: s.color }} strokeWidth={j ? 1.6 : 2.4} strokeLinecap="round" />
              {j === 0 && <circle cx={e[0]} cy={e[1]} r={4.5} style={{ fill: s.color }} className="dot" />}
            </g>
          );
        })}
        {hover != null && s0.values[hover] != null && (
          <g>
            <line x1={X(hover)} x2={X(hover)} y1={pt} y2={pt + ih} className="gl" />
            <circle cx={X(hover)} cy={Y(s0.values[hover])} r={5} className="dot" style={{ fill: s0.color }} />
            <text className="tip" textAnchor="middle" y={pt - 4} x={Math.min(W - 60, Math.max(pl + 50, X(hover)))}>
              {series.map((s) => fmt(s.values[hover] ?? 0)).join(" · ")}{labels[hover] ? ` · ${labels[hover]}` : ""}
            </text>
          </g>
        )}
      </svg>
    </div>
  );
}

export function Bars({ data, height = 200 }: { data: { label: string; value: number; color?: string }[]; height?: number }) {
  const W = 640, H = height, pl = 8, pb = 26, n = data.length;
  if (!n) return null;
  const bw = Math.min(54, ((W - pl * 2) / n) * 0.56), mx = Math.max(1, ...data.map((d) => d.value)) * 1.15;
  return (
    <div className="ch">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="bar chart">
        {data.map((d, i) => {
          const cx = pl + ((W - pl * 2) * (i + 0.5)) / n, h = ((H - pb - 18) * d.value) / mx, y = H - pb - h;
          return (
            <g key={d.label}>
              <rect x={cx - bw / 2} y={y} width={bw} height={Math.max(0, h)} rx={Math.min(10, bw / 2)} style={{ fill: d.color ?? "var(--acc)" }} />
              <text x={cx} y={y - 6} textAnchor="middle" className="ax v">{d.value}</text>
              <text x={cx} y={H - 8} textAnchor="middle" className="ax">{d.label}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

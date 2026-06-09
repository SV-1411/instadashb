import { NavLink } from "react-router-dom";
import { MODULES } from "../lib/modules";

const navClass = (isActive: boolean) =>
  `block rounded-xl px-3 py-2 text-sm font-medium transition ${
    isActive
      ? "bg-pulse/90 text-white shadow-glass"
      : "text-coffee/80 hover:bg-white/50 hover:text-coffee"
  }`;

export function Sidebar() {
  return (
    <aside className="glass sheen m-3 w-60 shrink-0 rounded-3xl p-4">
      <div className="mb-6 px-2 text-xl font-extrabold tracking-tight text-ink">
        Civic<span className="text-pulse">Pulse</span>
      </div>
      <nav className="space-y-1">
        {MODULES.map((m) => (
          <NavLink key={m.path} to={m.path} end={m.path === "/"} className={({ isActive }) => navClass(isActive)}>
            {m.label}
          </NavLink>
        ))}
      </nav>

      <div className="my-4 h-px bg-coffee/15" />

      <NavLink to="/ground" className={({ isActive }) => navClass(isActive)}>
        + Ground report
      </NavLink>
      <NavLink to="/connect" className={({ isActive }) => navClass(isActive)}>
        + Connect Instagram
      </NavLink>

      <p className="mt-6 px-2 text-xs text-mocha/70">CivicPulse · social intelligence</p>
    </aside>
  );
}

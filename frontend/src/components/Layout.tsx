import { useQuery } from "@tanstack/react-query";
import { clsx } from "clsx";
import { Activity, FlaskConical, LayoutDashboard, ListChecks, Menu, Monitor, Moon, Plus, Sun, X } from "lucide-react";
import { useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router";

import { api } from "../lib/api";
import { usePreferences } from "../lib/preferences";
import type { ThemeChoice } from "../lib/preferences";
import type { Workspace } from "../lib/types";
import { SegmentedControl, buttonTone } from "./ui";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/decisions", label: "Decisions", icon: ListChecks, end: false },
  { to: "/evals", label: "Evals", icon: FlaskConical, end: false },
  { to: "/traces", label: "Traces", icon: Activity, end: false },
];

function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2.5">
      <img src="/favicon.svg" alt="" className="size-8" />
      <div className="leading-tight">
        <div className="text-[15px] font-semibold text-ink">Hindsight</div>
        <div className="text-[11px] text-ink-3">grade your judgment</div>
      </div>
    </Link>
  );
}

function ProviderStatus() {
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, staleTime: 60_000 });
  if (!health.data) return null;
  const { offline, model } = health.data;
  return (
    <div
      className="flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-2 text-xs text-ink-2"
      title={offline ? "No GEMINI_API_KEY set, so audits use the offline rule-based baseline." : `Audits run on ${model}`}
    >
      <span className={clsx("size-2 rounded-full", offline ? "bg-warning" : "bg-good")} aria-hidden />
      <span className="truncate">{offline ? "Offline mode · rules" : `Gemini · ${model}`}</span>
    </div>
  );
}

function Controls() {
  const { workspace, setWorkspace, theme, setTheme } = usePreferences();
  const navigate = useNavigate();
  const location = useLocation();

  const switchWorkspace = (ws: Workspace) => {
    setWorkspace(ws);
    // A decision page belongs to one workspace; don't strand the user on a 404.
    if (location.pathname.startsWith("/decisions/")) navigate("/decisions");
  };

  return (
    <div className="space-y-3">
      <div>
        <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-ink-3">Workspace</div>
        <SegmentedControl<Workspace>
          label="Workspace"
          value={workspace}
          onChange={switchWorkspace}
          options={[
            { value: "demo", label: "Demo" },
            { value: "personal", label: "Personal" },
          ]}
        />
      </div>
      <SegmentedControl<ThemeChoice>
        label="Theme"
        size="sm"
        value={theme}
        onChange={setTheme}
        options={[
          { value: "system", label: <Monitor className="size-3.5" aria-label="System theme" />, title: "System" },
          { value: "light", label: <Sun className="size-3.5" aria-label="Light theme" />, title: "Light" },
          { value: "dark", label: <Moon className="size-3.5" aria-label="Dark theme" />, title: "Dark" },
        ]}
      />
      <ProviderStatus />
    </div>
  );
}

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="space-y-0.5" aria-label="Main">
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={onNavigate}
          className={({ isActive }) =>
            clsx(
              "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition",
              isActive ? "bg-surface-2 text-ink" : "text-ink-2 hover:bg-surface-2 hover:text-ink",
            )
          }
        >
          <Icon className="size-4" aria-hidden />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}

function NewDecisionLink({ className, onNavigate }: { className?: string; onNavigate?: () => void }) {
  return (
    <Link
      to="/new"
      onClick={onNavigate}
      className={clsx("inline-flex h-10 items-center justify-center gap-2 rounded-lg px-4 text-sm font-medium", buttonTone("primary"), className)}
    >
      <Plus className="size-4" aria-hidden /> Log a decision
    </Link>
  );
}

export function Layout() {
  const [menuOpen, setMenuOpen] = useState(false);
  const close = () => setMenuOpen(false);

  return (
    <div className="min-h-screen">
      <aside className="fixed inset-y-0 left-0 hidden w-64 flex-col gap-6 border-r border-line bg-surface px-4 py-6 lg:flex">
        <Logo />
        <NewDecisionLink className="w-full" />
        <NavItems />
        <div className="mt-auto">
          <Controls />
        </div>
      </aside>

      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-line bg-surface/95 px-4 py-3 backdrop-blur lg:hidden">
        <Logo />
        <button
          type="button"
          className="rounded-lg p-2 text-ink-2 hover:bg-surface-2"
          aria-label={menuOpen ? "Close menu" : "Open menu"}
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((open) => !open)}
        >
          {menuOpen ? <X className="size-5" /> : <Menu className="size-5" />}
        </button>
      </header>
      {menuOpen && (
        <div className="sticky top-[57px] z-10 space-y-4 border-b border-line bg-surface px-4 py-4 lg:hidden">
          <NewDecisionLink className="w-full" onNavigate={close} />
          <NavItems onNavigate={close} />
          <Controls />
        </div>
      )}

      <main className="lg:pl-64">
        <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-10 lg:py-10">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

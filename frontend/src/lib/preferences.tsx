import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import type { Workspace } from "./types";

export type ThemeChoice = "system" | "light" | "dark";

interface Preferences {
  workspace: Workspace;
  setWorkspace: (ws: Workspace) => void;
  theme: ThemeChoice;
  setTheme: (theme: ThemeChoice) => void;
}

const PreferencesContext = createContext<Preferences | null>(null);

// Browser storage can throw (private windows, blocked site data); preferences are conveniences.
function read<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const value = localStorage.getItem(key);
    return allowed.includes(value as T) ? (value as T) : fallback;
  } catch {
    return fallback;
  }
}

function write(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* ignore */
  }
}

export function PreferencesProvider({ children }: { children: ReactNode }) {
  const [workspace, setWorkspaceState] = useState<Workspace>(() =>
    read("hindsight.workspace", ["demo", "personal"] as const, "demo"),
  );
  const [theme, setThemeState] = useState<ThemeChoice>(() =>
    read("hindsight.theme", ["system", "light", "dark"] as const, "system"),
  );

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") delete root.dataset.theme;
    else root.dataset.theme = theme;
  }, [theme]);

  const setWorkspace = useCallback((ws: Workspace) => {
    setWorkspaceState(ws);
    write("hindsight.workspace", ws);
  }, []);

  const setTheme = useCallback((next: ThemeChoice) => {
    setThemeState(next);
    write("hindsight.theme", next);
  }, []);

  const value = useMemo(
    () => ({ workspace, setWorkspace, theme, setTheme }),
    [workspace, setWorkspace, theme, setTheme],
  );
  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>;
}

export function usePreferences(): Preferences {
  const value = useContext(PreferencesContext);
  if (!value) throw new Error("usePreferences must be used inside PreferencesProvider");
  return value;
}

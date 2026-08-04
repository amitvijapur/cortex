// Cortex Command — first-load project picker. An input with /api/projects/suggest
// autocomplete plus a recent list kept in localStorage. Choosing a project POSTs
// a new session, which App makes active.

import { useEffect, useRef, useState } from "react";
import { api, type ProjectSuggestion } from "../lib/api";
import { Logomark } from "./Logomark";

const RECENTS_KEY = "cortex-command:recent-projects";
const MAX_RECENTS = 8;

function loadRecents(): string[] {
  try {
    const raw = localStorage.getItem(RECENTS_KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr.filter((x): x is string => typeof x === "string") : [];
  } catch {
    return [];
  }
}

export function pushRecent(path: string): void {
  try {
    const cur = loadRecents().filter((p) => p !== path);
    cur.unshift(path);
    localStorage.setItem(RECENTS_KEY, JSON.stringify(cur.slice(0, MAX_RECENTS)));
  } catch {
    /* ignore */
  }
}

export function ProjectPicker({
  onPick,
  busy,
  error,
}: {
  onPick: (path: string) => void;
  busy: boolean;
  error: string | null;
}): React.ReactNode {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<ProjectSuggestion[]>([]);
  const [recents] = useState<string[]>(() => loadRecents());
  const debounceRef = useRef<number | null>(null);

  useEffect(() => {
    if (debounceRef.current !== null) clearTimeout(debounceRef.current);
    const q = query.trim();
    debounceRef.current = window.setTimeout(() => {
      api
        .suggestProjects(q)
        .then(setSuggestions)
        .catch(() => setSuggestions([]));
    }, 180);
    return () => {
      if (debounceRef.current !== null) clearTimeout(debounceRef.current);
    };
  }, [query]);

  function submit(path: string): void {
    const p = path.trim();
    if (!p || busy) return;
    onPick(p);
  }

  return (
    <div className="wrap picker-wrap">
      <section className="panel picker">
        <div className="picker-brand">
          <Logomark size={22} />
          <span className="wordmark">Cortex Command</span>
        </div>
        <div className="picker-sub mono">Open a project to start a session</div>

        <form
          className="picker-form"
          onSubmit={(e) => {
            e.preventDefault();
            submit(query);
          }}
        >
          <input
            className="picker-input mono"
            placeholder="/absolute/path/to/project"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
            spellCheck={false}
          />
          <button className="picker-go" type="submit" disabled={busy || query.trim() === ""}>
            {busy ? "Opening…" : "Open"}
          </button>
        </form>

        {error && <div className="picker-error mono">{error}</div>}

        {suggestions.length > 0 && (
          <div className="picker-group">
            <div className="picker-glabel mono">suggestions</div>
            <div className="picker-list">
              {suggestions.map((s) => (
                <button
                  className="picker-row"
                  key={s.path}
                  onClick={() => submit(s.path)}
                  disabled={busy}
                >
                  <span className="picker-row-label mono">{s.label ?? s.path}</span>
                  <span className="picker-row-path mono">{s.path}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {recents.length > 0 && (
          <div className="picker-group">
            <div className="picker-glabel mono">recent</div>
            <div className="picker-list">
              {recents.map((p) => (
                <button
                  className="picker-row"
                  key={p}
                  onClick={() => submit(p)}
                  disabled={busy}
                >
                  <span className="picker-row-path mono">{p}</span>
                </button>
              ))}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

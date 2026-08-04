// Cortex Command — RunsView (M1): the run-queue lane scaffold using the kanban
// CSS, with an empty state. The live queue (composer, streaming run cards,
// resume) is M2 — this proves the lane layout belongs to the same system.

import { EmptyMark } from "./Logomark";

const LANES: Array<{ key: string; label: string }> = [
  { key: "queued", label: "Queued" },
  { key: "running", label: "Running" },
  { key: "done", label: "Done" },
  { key: "failed", label: "Failed" },
  { key: "interrupted", label: "Interrupted" },
];

export function RunsView(): React.ReactNode {
  return (
    <div className="wrap runsview">
      <section className="panel">
        <div className="panel-h">
          <h2>Run Queue</h2>
          <span className="panel-sub">autonomous runs · M2</span>
        </div>
        <div className="empty">
          <EmptyMark />
          <div className="empty-t">Runs land in M2</div>
          <div className="empty-s">
            The autonomous run-queue — autopilot / ralph / GSD presets, streaming run
            cards, and one-click resume — arrives in the next milestone. The lanes below
            are the shape it will fill.
          </div>
        </div>
      </section>

      <div className="kanban">
        {LANES.map((lane) => (
          <div className="kcol" key={lane.key}>
            <div className="kcol-h">
              <span className="t">{lane.label}</span>
              <span className="n">0</span>
            </div>
            <div className="kcards">
              <div className="lane-empty mono">—</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

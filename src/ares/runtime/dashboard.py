"""Static read-only HTML operations report from local SQLite incidents.

No web server, JavaScript, remote resources or authentication surface.
"""

import argparse
import html
from collections.abc import Mapping, Sequence
from pathlib import Path

from ares.runtime.multi_agent_mvp import IncidentReport, SqliteTaskStore


def _safe(value: object) -> str:
    return html.escape(str(value), quote=True)


def render_dashboard(
    reports: Sequence[IncidentReport], statuses: Mapping[str, int]
) -> str:
    """Return an escaped, self-contained, static incident overview."""
    counts = {
        key: sum(report.severity == key for report in reports)
        for key in ("normal", "warning", "critical")
    }
    cards = "".join(
        f'<div class="metric"><strong>{_safe(value)}</strong><span>{_safe(key)}</span></div>'
        for key, value in (
            ("Completed tasks shown", len(reports)),
            ("Normal", counts["normal"]),
            ("Warning", counts["warning"]),
            ("Critical", counts["critical"]),
            ("Failed tasks", statuses.get("failed", 0)),
            ("Unfinished tasks", statuses.get("running", 0)),
        )
    )
    items: list[str] = []
    for report in reports:
        rows = "".join(
            "<tr>"
            f"<td>{_safe(role.role)}</td>"
            f"<td>{_safe(role.finding)}</td>"
            f"<td>{_safe(role.recommendation)}</td>"
            "</tr>"
            for role in report.handoffs
        )
        items.append(
            f'<section class="incident {report.severity}">'
            f'<h2>{_safe(report.task_id)}</h2>'
            f'<p><b>Device:</b> {_safe(report.device_id)}'
            f' · <b>Step:</b> {_safe(report.observed_step)}'
            f' · <b>Temperature:</b> {_safe(report.temperature_c)} °C'
            f' · <b>Severity:</b> {_safe(report.severity)}'
            f' · <b>Outcome:</b> {_safe(report.outcome)}</p>'
            '<details><summary>Inspect agent handoffs</summary>'
            '<table><thead><tr><th>Role</th><th>Finding</th>'
            '<th>Recommendation</th></tr></thead><tbody>'
            f'{rows}</tbody></table></details></section>'
        )
    body = "\n".join(items) if items else "<p>No completed incidents recorded.</p>"
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" '
        'content="default-src \'none\'; style-src \'unsafe-inline\';">'
        "<title>ARES · Offline Operations</title>"
        "<style>"
        ":root{font-family:system-ui,sans-serif;color:#16233b;background:#f3f5f9}"
        "body{max-width:1100px;margin:3rem auto;padding:0 1rem}"
        "h1{font-size:2rem;margin-bottom:.3rem}p{line-height:1.6}"
        ".metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:1rem}"
        ".metric,.incident{background:white;border:1px solid #dce1e9;"
        "border-radius:12px;padding:1rem}"
        ".metric strong{display:block;font-size:1.75rem}.metric span{color:#526075}"
        ".incident{margin-top:1rem;border-left:5px solid #7e8ba0}"
        ".incident.critical{border-left-color:#cf4b45}"
        ".incident.warning{border-left-color:#d99c25}"
        ".incident.normal{border-left-color:#32926e}"
        "table{width:100%;border-collapse:collapse;margin-top:1rem}"
        "th,td{text-align:left;border-bottom:1px solid #dce1e9;padding:.65rem}"
        "summary{cursor:pointer;font-weight:600}"
        "</style></head><body><h1>ARES / Operations</h1>"
        "<p>Local, read-only export. No equipment writes or live telemetry. "
        "Model advice is never an authorization.</p>"
        f'<div class="metrics">{cards}</div><main>{body}</main>'
        "<footer><p>Static snapshot only · Not a live service</p></footer>"
        "</body></html>"
    )


def run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render static local ARES incident dashboard")
    parser.add_argument("--db", type=Path, default=Path(".ares-incident-tasks.sqlite3"))
    parser.add_argument("--output", type=Path, default=Path("ares-operations.html"))
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args(argv)
    store = SqliteTaskStore(args.db)
    report = render_dashboard(store.completed_reports(limit=args.limit), store.summary())
    args.output.write_text(report, encoding="utf-8")
    print(f"Static operations report created: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())

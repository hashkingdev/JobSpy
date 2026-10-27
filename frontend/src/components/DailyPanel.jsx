import { useCallback, useEffect, useMemo, useState } from "react";
import { getDailyLinks, getDailyStatus, runDaily } from "../api.js";
import {
  Badge,
  Banner,
  Button,
  Card,
  CopyButton,
  DomainPill,
  EmptyState,
  Icon,
  JobLink,
  SkeletonRows,
  StatCard,
  formatDateTime,
  hostOf,
  relativeTime,
} from "./ui.jsx";

const STATUS_TONE = { done: "success", short: "warn", error: "danger", running: "info" };
const STATUS_LABEL = { done: "Target reached", short: "Finished short", error: "Failed", running: "Running" };

function csvCell(value) {
  const text = value == null ? "" : String(value);
  return `"${text.replace(/"/g, '""')}"`;
}

function downloadCsv(links, day) {
  const header = ["title", "company", "site", "location", "job_url"];
  const rows = links.map((link) =>
    [link.title, link.company, link.site, link.location, link.job_url].map(csvCell).join(","),
  );
  const blob = new Blob([[header.join(","), ...rows].join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `job-links-${day}.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}

function ProgressRing({ value, max, size = 120, stroke = 10 }) {
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const ratio = max ? Math.min(1, value / max) : 0;
  return (
    <svg className="ring" width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`${value} of ${max}`}>
      <circle className="ring-track" cx={size / 2} cy={size / 2} r={radius} strokeWidth={stroke} />
      <circle
        className={`ring-fill${ratio >= 1 ? " is-complete" : ""}`}
        cx={size / 2}
        cy={size / 2}
        r={radius}
        strokeWidth={stroke}
        strokeDasharray={circumference}
        strokeDashoffset={circumference * (1 - ratio)}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
      <text x="50%" y="50%" className="ring-value" textAnchor="middle" dominantBaseline="central">
        {Math.round(ratio * 100)}%
      </text>
    </svg>
  );
}

export default function DailyPanel() {
  const [status, setStatus] = useState(null);
  const [links, setLinks] = useState([]);
  const [loadingLinks, setLoadingLinks] = useState(true);
  const [day, setDay] = useState("today");
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState(null);
  const [query, setQuery] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [nextStatus, nextLinks] = await Promise.all([getDailyStatus(), getDailyLinks(day)]);
      setStatus(nextStatus);
      setLinks(nextLinks.links || []);
      setRunning(Boolean(nextStatus.running));
    } catch (error) {
      setMessage({ tone: "danger", text: error.message });
    } finally {
      setLoadingLinks(false);
    }
  }, [day]);

  useEffect(() => {
    setLoadingLinks(true);
    refresh();
    const timer = setInterval(refresh, 30000);
    return () => clearInterval(timer);
  }, [refresh]);

  const handleRun = async () => {
    setRunning(true);
    setMessage(null);
    try {
      const result = await runDaily();
      const text =
        result.status === "done"
          ? `Target reached. Saved ${result.saved} new links, ${result.today_count} of ${result.target} today.`
          : result.status === "short"
            ? `All roles and sources searched. Saved ${result.saved} new links, ${result.today_count} of ${result.target} today. Add more roles in DAILY_ROLES to widen the search.`
            : `The run stopped with an error after saving ${result.saved} links.`;
      setMessage({ tone: result.status === "error" ? "danger" : result.status === "short" ? "warn" : "success", text });
    } catch (error) {
      setMessage({ tone: "danger", text: error.message });
    } finally {
      setRunning(false);
      refresh();
    }
  };

  const copyAll = async () => {
    try {
      await navigator.clipboard.writeText(filtered.map((link) => link.job_url).join("\n"));
      setMessage({ tone: "success", text: `Copied ${filtered.length} links to the clipboard.` });
    } catch {
      setMessage({ tone: "danger", text: "Clipboard is not available in this browser." });
    }
  };

  const target = status?.target || 100;
  const today = status?.today;
  const isToday = day === "today" || day === today;
  const count = isToday ? status?.today_count ?? links.length : links.length;
  const dayLabel = isToday ? today || "today" : day;
  const lastRun = status?.last_run;
  const remaining = Math.max(0, target - count);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return links;
    return links.filter((link) =>
      [link.title, link.company, link.location, link.site, hostOf(link.job_url)]
        .filter(Boolean)
        .some((value) => value.toLowerCase().includes(needle)),
    );
  }, [links, query]);

  const hosts = useMemo(() => {
    const counts = new Map();
    for (const link of links) {
      const host = hostOf(link.job_url);
      counts.set(host, (counts.get(host) || 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6);
  }, [links]);

  const sourceNotes = (lastRun?.notes || []).filter((note) => note.source);
  const maxFound = Math.max(1, ...sourceNotes.map((note) => note.found || 0));

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <p className="eyebrow">Overview</p>
          <h1>Daily 100</h1>
          <p className="page-subtitle">
            {status
              ? `Collects ${target} job links that open without a login, every day at ${status.run_at}.`
              : "Loading collection status…"}
          </p>
        </div>
        <div className="page-actions">
          <Button icon="refresh" onClick={refresh} aria-label="Refresh">
            Refresh
          </Button>
          <Button variant="primary" icon="play" loading={running} onClick={handleRun}>
            {running ? "Collecting…" : "Run now"}
          </Button>
        </div>
      </header>

      {message ? (
        <Banner tone={message.tone} onClose={() => setMessage(null)}>
          {message.text}
        </Banner>
      ) : null}
      {running ? (
        <Banner tone="info">Searching every source and role. This usually takes under a minute.</Banner>
      ) : null}

      <div className="stats-grid">
        <div className="stat stat-hero">
          <ProgressRing value={count} max={target} />
          <div>
            <span className="stat-label">Links on {dayLabel}</span>
            <div className="stat-value stat-value-lg">
              {count}
              <span className="stat-denom"> / {target}</span>
            </div>
            <div className="stat-hint">
              {remaining === 0 ? (
                <Badge tone="success" icon="check">
                  Target reached
                </Badge>
              ) : (
                `${remaining} more to reach today's target`
              )}
            </div>
          </div>
        </div>
        <StatCard
          label="Next scheduled run"
          icon="clock"
          value={!status ? "—" : status.enabled ? formatDateTime(status.next_run_at) : "Disabled"}
          hint={!status ? "Loading…" : status.enabled ? relativeTime(status.next_run_at) : "Set DAILY_ENABLED=true to schedule"}
        />
        <StatCard
          label="Last run"
          icon="bolt"
          value={
            lastRun ? (
              <Badge tone={STATUS_TONE[lastRun.status] || "neutral"}>{STATUS_LABEL[lastRun.status] || lastRun.status}</Badge>
            ) : (
              "No runs yet"
            )
          }
          hint={
            lastRun
              ? `${formatDateTime(lastRun.started_at)} · ${lastRun.trigger} · saved ${lastRun.saved}, found ${lastRun.found}`
              : "Press Run now to collect today's links"
          }
        />
        <StatCard
          label="No-login filter"
          icon="shield"
          value={status?.no_login_strict ? "Strict" : "Standard"}
          hint={
            status?.no_login_strict
              ? "Also drops ATSs that need an account to apply"
              : "Drops LinkedIn, Indeed, Glassdoor, ZipRecruiter, Dice and similar"
          }
        />
      </div>

      <div className="two-col">
        <Card
          className="links-card"
          title={`Links on ${dayLabel}`}
          subtitle={`${filtered.length} of ${links.length} shown`}
          actions={
            <>
              <label className="search-box">
                <Icon name="search" size={15} />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Filter by title, company, domain"
                  aria-label="Filter links"
                />
              </label>
              <input
                className="input input-date"
                type="date"
                value={isToday ? today || "" : day}
                max={today}
                onChange={(event) => setDay(event.target.value === today ? "today" : event.target.value)}
                aria-label="Day"
              />
              <Button icon="copy" onClick={copyAll} disabled={!filtered.length}>
                Copy
              </Button>
              <Button icon="download" onClick={() => downloadCsv(filtered, dayLabel)} disabled={!filtered.length}>
                CSV
              </Button>
            </>
          }
        >
          {!loadingLinks && !filtered.length ? (
            <EmptyState
              icon={query ? "search" : "calendar"}
              title={query ? "No links match that filter" : `No links saved on ${dayLabel}`}
              text={
                query
                  ? "Try a different title, company or domain."
                  : isToday
                    ? "Run the collector now or wait for the scheduled run."
                    : "Pick another day to view its links."
              }
              action={
                isToday && !query ? (
                  <Button variant="primary" icon="play" onClick={handleRun} loading={running}>
                    Run now
                  </Button>
                ) : null
              }
            />
          ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Job</th>
                  <th>Company</th>
                  <th>Domain</th>
                  <th className="col-actions" />
                </tr>
              </thead>
              <tbody>
                {loadingLinks ? (
                  <SkeletonRows rows={8} cols={4} />
                ) : (
                  filtered.map((link, index) => (
                    <tr key={link.id}>
                      <td className="col-job">
                        <JobLink url={link.job_url} title={link.title} />
                        <div className="cell-sub">
                          <span className="muted mono">{filtered.length - index}</span> · {link.site || "—"}
                        </div>
                      </td>
                      <td className="col-company">
                        <div className="truncate">{link.company || <span className="muted">—</span>}</div>
                        <div className="cell-sub truncate">{link.location || "—"}</div>
                      </td>
                      <td>
                        <DomainPill url={link.job_url} />
                      </td>
                      <td className="col-actions">
                        <CopyButton text={link.job_url} />
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          )}
        </Card>

        <div className="side-stack">
          <Card title="Last run by source" subtitle={lastRun ? formatDateTime(lastRun.started_at) : "No runs yet"} padded>
            {sourceNotes.length ? (
              <ul className="source-list">
                {sourceNotes.map((note, index) => (
                  <li key={index} className="source-row">
                    <div className="source-head">
                      <span className="source-name">{note.source}</span>
                      {note.error ? (
                        <Badge tone="danger" icon="alert">
                          error
                        </Badge>
                      ) : (
                        <span className="muted">
                          +{note.new} new · {note.no_login}/{note.found} no-login
                        </span>
                      )}
                    </div>
                    {note.error ? (
                      <p className="source-error">{note.error}</p>
                    ) : (
                      <div className="bar">
                        <span className="bar-fill" style={{ width: `${((note.found || 0) / maxFound) * 100}%` }} />
                        <span className="bar-fill bar-fill-strong" style={{ width: `${((note.new || 0) / maxFound) * 100}%` }} />
                      </div>
                    )}
                    <div className="cell-sub">{note.role}</div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">Per-source results appear here after the first run.</p>
            )}
            {lastRun ? (
              <div className="legend">
                <span>
                  <i className="legend-swatch" /> found
                </span>
                <span>
                  <i className="legend-swatch is-strong" /> saved as new
                </span>
                <span className="muted">
                  {lastRun.filtered} login-only dropped · {lastRun.duplicates} duplicates
                </span>
              </div>
            ) : null}
          </Card>

          <Card title="Top domains" subtitle={`On ${dayLabel}`} padded>
            {hosts.length ? (
              <ul className="host-list">
                {hosts.map(([host, n]) => (
                  <li key={host}>
                    <DomainPill url={`https://${host}`} />
                    <span className="host-count">{n}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">No links yet.</p>
            )}
          </Card>

          <Card title="Collection settings" subtitle="From backend/.env" padded>
            <dl className="kv">
              <dt>Roles</dt>
              <dd>
                <div className="chip-row">
                  {(status?.roles || []).map((role) => (
                    <span key={role} className="chip">
                      {role}
                    </span>
                  ))}
                </div>
              </dd>
              <dt>Sources</dt>
              <dd className="muted">{(status?.sources || []).join(", ") || "—"}</dd>
              <dt>Filters</dt>
              <dd className="muted">
                {status ? `${status.location_type} · United States · posted ${status.date_posted}` : "—"}
              </dd>
            </dl>
          </Card>
        </div>
      </div>
    </div>
  );
}

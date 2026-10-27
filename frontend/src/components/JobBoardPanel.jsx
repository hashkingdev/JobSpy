import { useEffect, useMemo, useRef, useState } from "react";
import { saveJobs, searchJobs } from "../api.js";
import SettingsModal from "./SettingsModal.jsx";
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
  Pagination,
  SkeletonRows,
} from "./ui.jsx";
import { JOB_TYPES, countryLabel, dateLabel, loadSettings, locationLabel, saveSettings } from "../settings.js";

const PAGE_SIZES = [10, 25, 50];

function newId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export default function JobBoardPanel({ tab }) {
  const [settings, setSettings] = useState(loadSettings);
  const [role, setRole] = useState(settings.role);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [selected, setSelected] = useState(() => new Set());
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [searched, setSearched] = useState(false);
  const [message, setMessage] = useState(null);
  const [lastStatus, setLastStatus] = useState([]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const headerCheckRef = useRef(null);

  const totalPages = Math.max(1, Math.ceil(jobs.length / pageSize) || 1);
  const currentPage = Math.min(page, totalPages);
  const pageStart = jobs.length ? (currentPage - 1) * pageSize : 0;
  const pageJobs = jobs.slice(pageStart, pageStart + pageSize);
  const pageAllSelected = pageJobs.length > 0 && pageJobs.every((job) => selected.has(job.id));
  const pageSomeSelected = pageJobs.some((job) => selected.has(job.id));
  const selectedCount = selected.size;

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  useEffect(() => {
    if (headerCheckRef.current) {
      headerCheckRef.current.indeterminate = pageSomeSelected && !pageAllSelected;
    }
  }, [pageSomeSelected, pageAllSelected]);

  const jobTypeLabel = useMemo(
    () => JOB_TYPES.find((type) => type.id === (settings.job_type || ""))?.label || "Any type",
    [settings.job_type],
  );

  const persist = (next) => {
    setSettings(next);
    saveSettings(next);
  };

  const handleSearch = async (event) => {
    event?.preventDefault();
    const trimmed = role.trim();
    if (!trimmed) return;
    const next = { ...settings, role: trimmed };
    persist(next);
    setLoading(true);
    setMessage(null);
    try {
      const data = await searchJobs({
        ...next,
        source: tab.id,
        job_type: next.job_type || null,
        results_wanted: next.results_wanted || 100,
        num_pages: Math.min(20, Math.max(1, Math.ceil((next.results_wanted || 100) / 10))),
        sites: [],
      });
      const nextJobs = (data.jobs || []).map((job) => ({ ...job, id: newId() }));
      setJobs(nextJobs);
      setSelected(new Set());
      setPage(1);
      setSearched(true);
      setLastStatus(data.site_status || []);
      const errors = (data.site_status || []).filter((item) => item.error);
      const dropped = (data.site_status || []).find((item) => item.dropped)?.dropped || 0;
      if (!nextJobs.length) {
        setMessage({
          tone: "warn",
          text: errors.length
            ? errors.map((item) => `${item.site}: ${item.error}`).join(" · ")
            : dropped
              ? `All ${dropped} results needed a login and were dropped.`
              : "No job links found for these settings.",
        });
      } else if (dropped || errors.length) {
        setMessage({
          tone: "info",
          text: [
            dropped ? `Dropped ${dropped} login-only link${dropped === 1 ? "" : "s"}.` : null,
            ...errors.map((item) => `${item.site}: ${item.error}`),
          ]
            .filter(Boolean)
            .join(" · "),
        });
      }
    } catch (error) {
      setMessage({ tone: "danger", text: error.message });
    } finally {
      setLoading(false);
    }
  };

  const toggleRow = (id) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const togglePage = (checked) => {
    setSelected((current) => {
      const next = new Set(current);
      for (const job of pageJobs) {
        if (checked) next.add(job.id);
        else next.delete(job.id);
      }
      return next;
    });
  };

  const removeIds = (ids) => {
    setJobs((current) => current.filter((job) => !ids.has(job.id)));
    setSelected((current) => {
      const next = new Set(current);
      ids.forEach((id) => next.delete(id));
      return next;
    });
  };

  const handleSave = async (onlySelected) => {
    const toSave = onlySelected ? jobs.filter((job) => selected.has(job.id)) : jobs;
    if (!toSave.length) return;
    setSaving(true);
    setMessage(null);
    try {
      const result = await saveJobs(toSave.map(({ id, ...job }) => job));
      setMessage({
        tone: "success",
        text: `Saved ${result.saved} job link${result.saved === 1 ? "" : "s"} to the database${
          result.skipped ? `, skipped ${result.skipped} duplicate${result.skipped === 1 ? "" : "s"}` : ""
        }.`,
      });
    } catch (error) {
      setMessage({ tone: "danger", text: error.message });
    } finally {
      setSaving(false);
    }
  };

  const filterChips = [
    { icon: "globe", text: countryLabel(settings.country) },
    { icon: "layers", text: locationLabel(settings.location_type) },
    { icon: "calendar", text: dateLabel(settings.date_posted) },
    { icon: "bolt", text: jobTypeLabel === "Any" ? "Any type" : jobTypeLabel },
    {
      icon: settings.no_login_only === false ? "unlock" : "lock",
      text: settings.no_login_only === false ? "All links" : "No-login only",
      tone: settings.no_login_only === false ? "warn" : "brand",
    },
  ];

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <p className="eyebrow">Source</p>
          <h1>{tab.label}</h1>
          <p className="page-subtitle">{tab.description}</p>
        </div>
        <div className="page-actions">
          <Button icon="settings" onClick={() => setSettingsOpen(true)}>
            Settings
          </Button>
        </div>
      </header>

      <Card className="search-card" padded>
        <form className="search-form" onSubmit={handleSearch}>
          <label className="search-box search-box-lg">
            <Icon name="search" size={18} />
            <input
              value={role}
              onChange={(event) => setRole(event.target.value)}
              placeholder="Role or query, e.g. full stack software engineer"
              aria-label="Role"
            />
          </label>
          <label className="select-inline">
            <span className="muted">Links</span>
            <select
              value={settings.results_wanted || 100}
              onChange={(event) => persist({ ...settings, results_wanted: Number(event.target.value) })}
            >
              {[25, 50, 100].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <Button type="submit" variant="primary" icon="search" loading={loading} disabled={!role.trim()}>
            {loading ? "Searching…" : "Get job links"}
          </Button>
        </form>
        <div className="chip-row">
          {filterChips.map((chip) => (
            <button
              key={chip.text}
              type="button"
              className={`chip chip-button${chip.tone ? ` chip-${chip.tone}` : ""}`}
              onClick={() => setSettingsOpen(true)}
              title="Change in settings"
            >
              <Icon name={chip.icon} size={13} />
              {chip.text}
            </button>
          ))}
        </div>
      </Card>

      {message ? (
        <Banner tone={message.tone} onClose={() => setMessage(null)}>
          {message.text}
        </Banner>
      ) : null}

      <Card
        className="results-card"
        title="Results"
        subtitle={
          jobs.length
            ? `${jobs.length} link${jobs.length === 1 ? "" : "s"}${selectedCount ? ` · ${selectedCount} selected` : ""}`
            : searched
              ? "Nothing to show"
              : "Run a search to see job links"
        }
        actions={
          jobs.length ? (
            <>
              {selectedCount ? (
                <>
                  <Button icon="trash" onClick={() => removeIds(new Set(selected))}>
                    Remove {selectedCount}
                  </Button>
                  <Button icon="database" variant="secondary" loading={saving} onClick={() => handleSave(true)}>
                    Save {selectedCount}
                  </Button>
                </>
              ) : (
                <Button icon="trash" onClick={() => removeIds(new Set(jobs.map((job) => job.id)))}>
                  Clear
                </Button>
              )}
              <Button icon="database" variant="primary" loading={saving} onClick={() => handleSave(false)}>
                Save all
              </Button>
            </>
          ) : null
        }
      >
        {!loading && !pageJobs.length ? (
          <EmptyState
            icon={searched ? "alert" : "search"}
            title={searched ? "No job links found" : "Search for job links"}
            text={
              searched
                ? "Try a broader role, or turn off the no-login filter in settings."
                : `Enter a role above and press Get job links to query ${tab.label}.`
            }
          />
        ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th className="col-check">
                  <input
                    ref={headerCheckRef}
                    type="checkbox"
                    checked={pageAllSelected}
                    onChange={(event) => togglePage(event.target.checked)}
                    disabled={!pageJobs.length}
                    aria-label="Select rows on this page"
                  />
                </th>
                <th>Job</th>
                <th>Company</th>
                <th>Location</th>
                <th>Domain</th>
                <th>Posted</th>
                <th className="col-actions" />
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <SkeletonRows rows={8} cols={7} />
              ) : (
                pageJobs.map((job) => (
                  <tr key={job.id} className={selected.has(job.id) ? "is-selected" : ""}>
                    <td className="col-check">
                      <input
                        type="checkbox"
                        checked={selected.has(job.id)}
                        onChange={() => toggleRow(job.id)}
                        aria-label={`Select ${job.title || job.job_url}`}
                      />
                    </td>
                    <td className="col-job">
                      <JobLink url={job.job_url} title={job.title} />
                      <div className="cell-sub">
                        {job.site || "—"}
                        {job.job_type ? ` · ${String(job.job_type).toLowerCase()}` : ""}
                      </div>
                    </td>
                    <td className="col-company">
                      <div className="truncate">{job.company || <span className="muted">—</span>}</div>
                    </td>
                    <td className="col-company">
                      <div className="truncate">{job.location || <span className="muted">—</span>}</div>
                    </td>
                    <td>
                      <DomainPill url={job.job_url} />
                    </td>
                    <td className="muted nowrap">{job.date_posted ? String(job.date_posted).slice(0, 10) : "—"}</td>
                    <td className="col-actions">
                      <span className="row-actions">
                        <CopyButton text={job.job_url} />
                        <button
                          type="button"
                          className="icon-btn is-danger"
                          onClick={() => removeIds(new Set([job.id]))}
                          aria-label="Remove"
                          title="Remove"
                        >
                          <Icon name="close" size={15} />
                        </button>
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        )}
        {jobs.length ? (
          <div className="card-foot">
            <Pagination
              page={currentPage}
              totalPages={totalPages}
              pageSize={pageSize}
              pageSizes={PAGE_SIZES}
              total={jobs.length}
              rangeStart={pageStart + 1}
              rangeEnd={pageStart + pageJobs.length}
              onPage={setPage}
              onPageSize={(size) => {
                setPageSize(size);
                setPage(1);
              }}
            />
          </div>
        ) : null}
      </Card>

      {lastStatus.length ? (
        <div className="status-row">
          {lastStatus.map((item, index) => (
            <Badge
              key={`${item.site}-${index}`}
              tone={item.error ? "danger" : item.dropped ? "warn" : "success"}
              icon={item.error ? "alert" : "check"}
            >
              {item.site}: {item.error ? item.error : item.dropped ? `dropped ${item.dropped}` : `${item.count} links`}
            </Badge>
          ))}
        </div>
      ) : null}

      <SettingsModal
        open={settingsOpen}
        initialSettings={settings}
        onClose={() => setSettingsOpen(false)}
        onSave={(next) => {
          persist(next);
          setRole(next.role);
          setSettingsOpen(false);
        }}
      />
    </div>
  );
}

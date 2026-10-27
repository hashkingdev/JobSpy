import { useEffect, useMemo, useRef, useState } from "react";
import { saveJobs, searchJobs } from "../api.js";
import SettingsModal from "./SettingsModal.jsx";
import {
  countryLabel,
  dateLabel,
  loadSettings,
  locationLabel,
  queryPreview,
  saveSettings,
} from "../settings.js";

const PAGE_SIZES = [10, 25, 50];

function newId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function pageItems(current, total) {
  if (total <= 7) {
    return Array.from({ length: total }, (_, index) => index + 1);
  }
  const pages = new Set([1, total, current - 1, current, current + 1]);
  if (current <= 3) {
    pages.add(2);
    pages.add(3);
    pages.add(4);
  }
  if (current >= total - 2) {
    pages.add(total - 3);
    pages.add(total - 2);
    pages.add(total - 1);
  }
  return [...pages]
    .filter((page) => page >= 1 && page <= total)
    .sort((left, right) => left - right)
    .reduce((items, page) => {
      if (items.length && page - items[items.length - 1] > 1) {
        items.push("…");
      }
      items.push(page);
      return items;
    }, []);
}

export default function JobBoardPanel({ tab }) {
  const [settings, setSettings] = useState(loadSettings);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [jobs, setJobs] = useState([]);
  const [selected, setSelected] = useState(() => new Set());
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);
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
  const rangeStart = jobs.length ? pageStart + 1 : 0;
  const rangeEnd = pageStart + pageJobs.length;

  const summary = useMemo(() => {
    if (!tab.ready) {
      return `${tab.label} is not connected yet.`;
    }
    const method = settings.job_type || "any type";
    return `${queryPreview(settings)} · ${locationLabel(settings.location_type)} · ${countryLabel(settings.country)} · ${dateLabel(settings.date_posted)} · ${method} · ${settings.results_wanted || 100} links`;
  }, [settings, tab]);

  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages]);

  useEffect(() => {
    if (headerCheckRef.current) {
      headerCheckRef.current.indeterminate = pageSomeSelected && !pageAllSelected;
    }
  }, [pageSomeSelected, pageAllSelected]);

  const showMessage = (type, text) => {
    setMessage({ type, text });
  };

  const handleSearch = async () => {
    if (!tab.ready) {
      showMessage("error", `${tab.label} is not connected yet.`);
      return;
    }
    setLoading(true);
    setMessage(null);
    try {
      const data = await searchJobs({
        ...settings,
        source: tab.id,
        job_type: settings.job_type || null,
        results_wanted: settings.results_wanted || 100,
        num_pages: Math.min(20, Math.max(1, Math.ceil((settings.results_wanted || 100) / 10))),
        sites: [],
      });
      const nextJobs = (data.jobs || []).map((job) => ({ ...job, id: newId() }));
      setJobs(nextJobs);
      setSelected(new Set());
      setPage(1);
      const statusNotes = (data.site_status || [])
        .filter((item) => item.error)
        .map((item) => `${item.site}: ${item.error}`)
        .join(" · ");
      const found = nextJobs.length
        ? `Found ${nextJobs.length} job link${nextJobs.length === 1 ? "" : "s"}.`
        : "No job links found for these settings.";
      const extra = statusNotes ? ` ${statusNotes}.` : "";
      showMessage(nextJobs.length ? "success" : "error", found + extra);
    } catch (error) {
      showMessage("error", error.message);
    } finally {
      setLoading(false);
    }
  };

  const toggleRow = (id) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const selectAll = () => {
    setSelected(new Set(jobs.map((job) => job.id)));
  };

  const togglePage = (checked) => {
    setSelected((current) => {
      const next = new Set(current);
      for (const job of pageJobs) {
        if (checked) {
          next.add(job.id);
        } else {
          next.delete(job.id);
        }
      }
      return next;
    });
  };

  const removeSelected = () => {
    if (!selected.size) {
      return;
    }
    setJobs((current) => current.filter((job) => !selected.has(job.id)));
    setSelected(new Set());
  };

  const removeAll = () => {
    setJobs([]);
    setSelected(new Set());
    setPage(1);
  };

  const removeOne = (id) => {
    setJobs((current) => current.filter((job) => job.id !== id));
    setSelected((current) => {
      const next = new Set(current);
      next.delete(id);
      return next;
    });
  };

  const handleSave = async () => {
    if (!jobs.length) {
      showMessage("error", "There are no job links on screen to save.");
      return;
    }
    setSaving(true);
    setMessage(null);
    try {
      const payload = jobs.map(({ id, ...job }) => job);
      const result = await saveJobs(payload);
      showMessage(
        "success",
        `Saved ${result.saved} job link${result.saved === 1 ? "" : "s"} to the database.`,
      );
    } catch (error) {
      showMessage("error", error.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <section>
      <header className="topbar">
        <div>
          <h1>{tab.label}</h1>
          <p className="summary">{summary}</p>
        </div>
        {tab.ready ? (
          <button
            type="button"
            className="button ghost"
            onClick={() => setSettingsOpen(true)}
          >
            Settings
          </button>
        ) : null}
      </header>

      <section className="toolbar">
        <button
          type="button"
          className="button primary"
          onClick={handleSearch}
          disabled={loading}
        >
          {loading ? "Getting job links…" : "Get job links"}
        </button>
        <button type="button" className="button" onClick={selectAll} disabled={!jobs.length}>
          Select all
        </button>
        <button
          type="button"
          className="button"
          onClick={removeSelected}
          disabled={!selectedCount}
        >
          Remove{selectedCount ? ` (${selectedCount})` : ""}
        </button>
        <button type="button" className="button danger" onClick={removeAll} disabled={!jobs.length}>
          Remove all
        </button>
      </section>

      {message ? <div className={`banner ${message.type}`}>{message.text}</div> : null}
      {loading ? <p className="hint">Searching. This can take a minute.</p> : null}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="check-col">
                <input
                  ref={headerCheckRef}
                  type="checkbox"
                  checked={pageAllSelected}
                  onChange={(event) => togglePage(event.target.checked)}
                  disabled={!pageJobs.length}
                  aria-label="Select rows on this page"
                />
              </th>
              <th>Title</th>
              <th>Company</th>
              <th>Site</th>
              <th>Location</th>
              <th>Job link</th>
              <th className="action-col"></th>
            </tr>
          </thead>
          <tbody>
            {pageJobs.length ? (
              pageJobs.map((job) => (
                <tr key={job.id} className={selected.has(job.id) ? "selected" : ""}>
                  <td>
                    <input
                      type="checkbox"
                      checked={selected.has(job.id)}
                      onChange={() => toggleRow(job.id)}
                      aria-label={`Select ${job.title || job.job_url}`}
                    />
                  </td>
                  <td>{job.title || "—"}</td>
                  <td>{job.company || "—"}</td>
                  <td>{job.site || "—"}</td>
                  <td>{job.location || "—"}</td>
                  <td>
                    <a href={job.job_url} target="_blank" rel="noreferrer">
                      {job.job_url}
                    </a>
                  </td>
                  <td>
                    <button type="button" className="text-button" onClick={() => removeOne(job.id)}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="7" className="empty">
                  {tab.ready
                    ? "No job links on screen. Press Get job links to search."
                    : `${tab.label} is not connected yet.`}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {jobs.length ? (
        <div className="pagination">
          <span className="pagination-info">
            Showing {rangeStart}–{rangeEnd} of {jobs.length}
          </span>
          <div className="pagination-controls">
            <label className="page-size">
              Rows
              <select
                value={pageSize}
                onChange={(event) => {
                  setPageSize(Number(event.target.value));
                  setPage(1);
                }}
                aria-label="Rows per page"
              >
                {PAGE_SIZES.map((size) => (
                  <option key={size} value={size}>
                    {size}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="button"
              onClick={() => setPage(currentPage - 1)}
              disabled={currentPage <= 1}
            >
              Previous
            </button>
            {pageItems(currentPage, totalPages).map((item, index) =>
              item === "…" ? (
                <span key={`ellipsis-${index}`} className="page-ellipsis">
                  …
                </span>
              ) : (
                <button
                  key={item}
                  type="button"
                  className={`page-button${item === currentPage ? " active" : ""}`}
                  onClick={() => setPage(item)}
                  aria-current={item === currentPage ? "page" : undefined}
                >
                  {item}
                </button>
              ),
            )}
            <button
              type="button"
              className="button"
              onClick={() => setPage(currentPage + 1)}
              disabled={currentPage >= totalPages}
            >
              Next
            </button>
          </div>
        </div>
      ) : null}

      <div className="footer-actions">
        <button
          type="button"
          className="button primary"
          onClick={handleSave}
          disabled={saving || !jobs.length}
        >
          {saving ? "Saving…" : "Save"}
        </button>
      </div>

      {tab.ready ? (
        <SettingsModal
          open={settingsOpen}
          initialSettings={settings}
          onClose={() => setSettingsOpen(false)}
          onSave={(next) => {
            setSettings(next);
            saveSettings(next);
            setSettingsOpen(false);
          }}
        />
      ) : null}
    </section>
  );
}

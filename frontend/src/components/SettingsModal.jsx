import { useEffect, useState } from "react";
import {
  COUNTRIES,
  DATE_OPTIONS,
  JOB_TYPES,
  LOCATION_TYPES,
  queryPreview,
} from "../settings.js";

export default function SettingsModal({ open, initialSettings, onClose, onSave }) {
  const [draft, setDraft] = useState(initialSettings);

  useEffect(() => {
    if (open) {
      setDraft(initialSettings);
    }
  }, [open, initialSettings]);

  if (!open) {
    return null;
  }

  const handleSubmit = (event) => {
    event.preventDefault();
    if (!draft.role.trim()) {
      return;
    }
    onSave({
      ...draft,
      role: draft.role.trim(),
      results_wanted: Math.min(100, Math.max(1, Number(draft.results_wanted) || 100)),
    });
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-labelledby="settings-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <h2 id="settings-title">JSearch settings</h2>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <form onSubmit={handleSubmit}>
          <label className="field">
            <span>Query / role</span>
            <input
              value={draft.role}
              onChange={(event) => setDraft({ ...draft, role: event.target.value })}
              placeholder="full stack software engineer"
            />
            <small className="field-hint">JSearch query: {queryPreview(draft)}</small>
          </label>
          <label className="field">
            <span>Country</span>
            <select
              value={draft.country}
              disabled
              onChange={(event) => setDraft({ ...draft, country: event.target.value })}
            >
              {COUNTRIES.map((country) => (
                <option key={country.id} value={country.id}>
                  {country.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Work from home</span>
            <select
              value={draft.location_type}
              disabled
              onChange={(event) => setDraft({ ...draft, location_type: event.target.value })}
            >
              {LOCATION_TYPES.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Date posted</span>
            <select
              value={draft.date_posted}
              disabled
              onChange={(event) => setDraft({ ...draft, date_posted: event.target.value })}
            >
              {DATE_OPTIONS.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Employment type</span>
            <select
              value={draft.job_type}
              onChange={(event) => setDraft({ ...draft, job_type: event.target.value })}
            >
              {JOB_TYPES.map((type) => (
                <option key={type.id} value={type.id}>
                  {type.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Job links</span>
            <input
              type="number"
              min="1"
              max="100"
              value={draft.results_wanted}
              onChange={(event) => setDraft({ ...draft, results_wanted: event.target.value })}
            />
            <small className="field-hint">How many job links to fetch at once (1–100).</small>
          </label>
          <div className="modal-actions">
            <button type="button" className="button ghost" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="button primary">
              Save settings
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

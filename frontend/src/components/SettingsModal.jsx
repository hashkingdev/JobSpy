import { useEffect, useState } from "react";
import { COUNTRIES, DATE_OPTIONS, JOB_TYPES, LOCATION_TYPES, queryPreview } from "../settings.js";
import { Button, Icon } from "./ui.jsx";

function Field({ label, hint, locked, children }) {
  return (
    <label className="field">
      <span className="field-label">
        {label}
        {locked ? (
          <span className="field-lock" title="Fixed for this plan">
            <Icon name="lock" size={12} /> fixed
          </span>
        ) : null}
      </span>
      {children}
      {hint ? <small className="field-hint">{hint}</small> : null}
    </label>
  );
}

export default function SettingsModal({ open, initialSettings, onClose, onSave }) {
  const [draft, setDraft] = useState(initialSettings);

  useEffect(() => {
    if (open) setDraft(initialSettings);
  }, [open, initialSettings]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const handleSubmit = (event) => {
    event.preventDefault();
    if (!draft.role.trim()) return;
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
        aria-modal="true"
        aria-labelledby="settings-title"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="modal-head">
          <div>
            <h2 id="settings-title">Search settings</h2>
            <p className="muted">Applies to every source tab.</p>
          </div>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close">
            <Icon name="close" />
          </button>
        </header>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            <Field label="Role or query" hint={`Query sent: ${queryPreview(draft)}`}>
              <input
                className="input"
                value={draft.role}
                onChange={(event) => setDraft({ ...draft, role: event.target.value })}
                placeholder="full stack software engineer"
                autoFocus
              />
            </Field>

            <div className="field-grid">
              <Field label="Employment type">
                <select
                  className="input"
                  value={draft.job_type}
                  onChange={(event) => setDraft({ ...draft, job_type: event.target.value })}
                >
                  {JOB_TYPES.map((type) => (
                    <option key={type.id} value={type.id}>
                      {type.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Links per search" hint="1 to 100">
                <input
                  className="input"
                  type="number"
                  min="1"
                  max="100"
                  value={draft.results_wanted}
                  onChange={(event) => setDraft({ ...draft, results_wanted: event.target.value })}
                />
              </Field>
              <Field label="Country" locked>
                <select className="input" value={draft.country} disabled>
                  {COUNTRIES.map((country) => (
                    <option key={country.id} value={country.id}>
                      {country.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Work location" locked>
                <select className="input" value={draft.location_type} disabled>
                  {LOCATION_TYPES.map((option) => (
                    <option key={option.id} value={option.id}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Date posted" locked>
                <select className="input" value={draft.date_posted} disabled>
                  {DATE_OPTIONS.map((option) => (
                    <option key={option.id} value={option.id}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </Field>
            </div>

            <label className="switch-row">
              <span className="switch-text">
                <span className="field-label">Only links that open without a login</span>
                <small className="field-hint">
                  Drops LinkedIn, Indeed, Glassdoor, ZipRecruiter, Dice and other boards that need an account.
                </small>
              </span>
              <span className={`switch${draft.no_login_only !== false ? " is-on" : ""}`}>
                <input
                  type="checkbox"
                  checked={draft.no_login_only !== false}
                  onChange={(event) => setDraft({ ...draft, no_login_only: event.target.checked })}
                />
                <span className="switch-knob" />
              </span>
            </label>
          </div>

          <footer className="modal-foot">
            <Button onClick={onClose}>Cancel</Button>
            <Button type="submit" variant="primary" icon="check">
              Save settings
            </Button>
          </footer>
        </form>
      </div>
    </div>
  );
}

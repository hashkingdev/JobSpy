import { useEffect, useState } from "react";

const ICONS = {
  search: "M11 4a7 7 0 1 1 0 14 7 7 0 0 1 0-14zm9 17-4.3-4.3",
  calendar: "M8 3v3M16 3v3M4 9h16M6 5h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z",
  play: "M7 5v14l11-7z",
  refresh: "M20 11a8 8 0 1 0 2 5.3M20 4v7h-7",
  settings:
    "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm8.4-3 1.6-1.2-2-3.5-1.9.8a7 7 0 0 0-1.8-1L16 4h-4l-.3 2.1a7 7 0 0 0-1.8 1l-1.9-.8-2 3.5L7.6 11a7 7 0 0 0 0 2l-1.6 1.2 2 3.5 1.9-.8a7 7 0 0 0 1.8 1L12 20h4l.3-2.1a7 7 0 0 0 1.8-1l1.9.8 2-3.5-1.6-1.2a7 7 0 0 0 0-2z",
  download: "M12 3v12m0 0 4-4m-4 4-4-4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2",
  copy: "M9 9h10v12H9zM5 15V3h10",
  external: "M14 4h6v6M20 4l-9 9M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5",
  trash: "M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6",
  check: "M5 12.5 10 17l9-10",
  close: "M6 6l12 12M18 6 6 18",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zm0-13v5l3 2",
  link: "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
  globe: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18",
  layers: "m12 3 9 5-9 5-9-5 9-5zM3 13l9 5 9-5M3 17l9 5 9-5",
  bolt: "M13 2 4 14h7l-1 8 9-12h-7l1-8z",
  info: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zm0-5v-5m0-3h.01",
  alert: "M12 3 2 21h20L12 3zm0 7v5m0 3h.01",
  shield: "M12 3 4 6v6c0 5 3.4 8.4 8 9 4.6-.6 8-4 8-9V6l-8-3zm-3 9 2 2 4-4",
  chevronLeft: "m15 5-7 7 7 7",
  chevronRight: "m9 5 7 7-7 7",
  database: "M12 3c4.4 0 8 1.3 8 3s-3.6 3-8 3-8-1.3-8-3 3.6-3 8-3zm-8 3v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3",
  sparkle: "M12 3v4m0 10v4M3 12h4m10 0h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6",
  lock: "M7 11V8a5 5 0 0 1 10 0v3M6 11h12v10H6z",
  unlock: "M7 11V8a5 5 0 0 1 9.6-2M6 11h12v10H6z",
};

export function Icon({ name, size = 16, className = "", ...rest }) {
  const d = ICONS[name];
  if (!d) {
    return null;
  }
  return (
    <svg
      className={`icon ${className}`.trim()}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...rest}
    >
      <path d={d} />
    </svg>
  );
}

export function Button({
  variant = "secondary",
  size = "md",
  icon,
  loading = false,
  children,
  className = "",
  ...rest
}) {
  return (
    <button
      type="button"
      className={`btn btn-${variant} btn-${size} ${className}`.trim()}
      disabled={rest.disabled || loading}
      {...rest}
    >
      {loading ? <span className="spinner" aria-hidden="true" /> : icon ? <Icon name={icon} /> : null}
      {children ? <span>{children}</span> : null}
    </button>
  );
}

export function Badge({ tone = "neutral", icon, children }) {
  return (
    <span className={`badge badge-${tone}`}>
      {icon ? <Icon name={icon} size={12} /> : null}
      {children}
    </span>
  );
}

export function hostOf(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url || "";
  }
}

export function DomainPill({ url }) {
  const host = hostOf(url);
  return (
    <span className="domain-pill" title={url}>
      <img
        className="domain-favicon"
        src={`https://www.google.com/s2/favicons?domain=${encodeURIComponent(host)}&sz=32`}
        alt=""
        width="16"
        height="16"
        loading="lazy"
        onError={(event) => {
          event.currentTarget.style.visibility = "hidden";
        }}
      />
      <span>{host}</span>
    </span>
  );
}

export function JobLink({ url, title }) {
  return (
    <a className="job-link" href={url} target="_blank" rel="noreferrer" title={url}>
      <span className="job-link-text">{title || url}</span>
      <Icon name="external" size={13} />
    </a>
  );
}

export function CopyButton({ text, label = "Copy link" }) {
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!copied) {
      return undefined;
    }
    const timer = setTimeout(() => setCopied(false), 1500);
    return () => clearTimeout(timer);
  }, [copied]);
  return (
    <button
      type="button"
      className={`icon-btn${copied ? " is-success" : ""}`}
      aria-label={label}
      title={label}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
        } catch {
          /* clipboard unavailable */
        }
      }}
    >
      <Icon name={copied ? "check" : "copy"} size={15} />
    </button>
  );
}

export function Banner({ tone = "info", children, onClose }) {
  const icon = tone === "success" ? "check" : tone === "danger" ? "alert" : "info";
  return (
    <div className={`banner banner-${tone}`} role="status">
      <Icon name={icon} size={16} />
      <div className="banner-text">{children}</div>
      {onClose ? (
        <button type="button" className="icon-btn" onClick={onClose} aria-label="Dismiss">
          <Icon name="close" size={14} />
        </button>
      ) : null}
    </div>
  );
}

export function StatCard({ label, value, hint, icon, tone = "neutral", children }) {
  return (
    <div className={`stat stat-${tone}`}>
      <div className="stat-head">
        <span className="stat-label">{label}</span>
        {icon ? (
          <span className="stat-icon">
            <Icon name={icon} size={16} />
          </span>
        ) : null}
      </div>
      <div className="stat-value">{value}</div>
      {hint ? <div className="stat-hint">{hint}</div> : null}
      {children}
    </div>
  );
}

export function Card({ title, subtitle, actions, children, className = "", padded = false }) {
  return (
    <section className={`card ${className}`.trim()}>
      {title || actions ? (
        <header className="card-head">
          <div>
            {title ? <h2 className="card-title">{title}</h2> : null}
            {subtitle ? <p className="card-subtitle">{subtitle}</p> : null}
          </div>
          {actions ? <div className="card-actions">{actions}</div> : null}
        </header>
      ) : null}
      <div className={padded ? "card-body" : ""}>{children}</div>
    </section>
  );
}

export function EmptyState({ icon = "search", title, text, action }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <Icon name={icon} size={22} />
      </div>
      <h3>{title}</h3>
      {text ? <p>{text}</p> : null}
      {action ? <div className="empty-action">{action}</div> : null}
    </div>
  );
}

export function SkeletonRows({ rows = 6, cols = 5 }) {
  return Array.from({ length: rows }, (_, row) => (
    <tr key={row} className="skeleton-row">
      {Array.from({ length: cols }, (_, col) => (
        <td key={col}>
          <span className="skeleton" style={{ width: `${55 + ((row * 7 + col * 13) % 40)}%` }} />
        </td>
      ))}
    </tr>
  ));
}

export function pageItems(current, total) {
  if (total <= 7) {
    return Array.from({ length: total }, (_, index) => index + 1);
  }
  const pages = new Set([1, total, current - 1, current, current + 1]);
  if (current <= 3) {
    [2, 3, 4].forEach((page) => pages.add(page));
  }
  if (current >= total - 2) {
    [total - 3, total - 2, total - 1].forEach((page) => pages.add(page));
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

export function Pagination({ page, totalPages, pageSize, pageSizes, total, rangeStart, rangeEnd, onPage, onPageSize }) {
  return (
    <div className="pagination">
      <span className="muted">
        Showing <strong>{rangeStart}–{rangeEnd}</strong> of <strong>{total}</strong>
      </span>
      <div className="pagination-controls">
        <label className="select-inline">
          <span className="muted">Rows</span>
          <select value={pageSize} onChange={(event) => onPageSize(Number(event.target.value))}>
            {pageSizes.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="icon-btn"
          onClick={() => onPage(page - 1)}
          disabled={page <= 1}
          aria-label="Previous page"
        >
          <Icon name="chevronLeft" />
        </button>
        {pageItems(page, totalPages).map((item, index) =>
          item === "…" ? (
            <span key={`e-${index}`} className="page-ellipsis">
              …
            </span>
          ) : (
            <button
              key={item}
              type="button"
              className={`page-btn${item === page ? " is-active" : ""}`}
              onClick={() => onPage(item)}
              aria-current={item === page ? "page" : undefined}
            >
              {item}
            </button>
          ),
        )}
        <button
          type="button"
          className="icon-btn"
          onClick={() => onPage(page + 1)}
          disabled={page >= totalPages}
          aria-label="Next page"
        >
          <Icon name="chevronRight" />
        </button>
      </div>
    </div>
  );
}

export function formatDateTime(iso) {
  if (!iso) {
    return "—";
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function relativeTime(iso) {
  if (!iso) {
    return "";
  }
  const diff = new Date(iso).getTime() - Date.now();
  if (Number.isNaN(diff)) {
    return "";
  }
  const abs = Math.abs(diff);
  const minutes = Math.round(abs / 60000);
  const hours = Math.round(abs / 3600000);
  const text =
    minutes < 1 ? "now" : minutes < 60 ? `${minutes} min` : hours < 48 ? `${hours} h` : `${Math.round(hours / 24)} d`;
  if (text === "now") {
    return text;
  }
  return diff > 0 ? `in ${text}` : `${text} ago`;
}

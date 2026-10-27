import { useEffect, useMemo, useState } from "react";
import { getHealth } from "./api.js";
import DailyPanel from "./components/DailyPanel.jsx";
import JobBoardPanel from "./components/JobBoardPanel.jsx";
import { Icon } from "./components/ui.jsx";
import { TABS, loadActiveTab, onHashTab, saveActiveTab } from "./tabs.js";
import "./App.css";

function useHealth() {
  const [online, setOnline] = useState(null);
  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        await getHealth();
        if (!cancelled) setOnline(true);
      } catch {
        if (!cancelled) setOnline(false);
      }
    };
    check();
    const timer = setInterval(check, 30000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);
  return online;
}

export default function App() {
  const [activeTab, setActiveTab] = useState(loadActiveTab);
  const online = useHealth();
  const current = useMemo(
    () => TABS.find((tab) => tab.id === activeTab) || TABS[0],
    [activeTab],
  );

  const selectTab = (tabId) => {
    setActiveTab(tabId);
    saveActiveTab(tabId);
  };

  useEffect(() => onHashTab(setActiveTab), []);

  const groups = useMemo(() => {
    const map = new Map();
    for (const tab of TABS) {
      if (!map.has(tab.group)) map.set(tab.group, []);
      map.get(tab.group).push(tab);
    }
    return [...map.entries()];
  }, []);

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">
            <Icon name="link" size={18} />
          </span>
          <span className="brand-text">
            <strong>JobSpy</strong>
            <span>Job link collector</span>
          </span>
        </div>

        <nav className="nav" aria-label="Sections">
          {groups.map(([group, tabs]) => (
            <div key={group} className="nav-group">
              <p className="nav-label">{group}</p>
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  className={`nav-item${tab.id === current.id ? " is-active" : ""}`}
                  onClick={() => selectTab(tab.id)}
                  aria-current={tab.id === current.id ? "page" : undefined}
                >
                  <Icon name={tab.icon} size={17} />
                  <span>{tab.label}</span>
                </button>
              ))}
            </div>
          ))}
        </nav>

        <div className="sidebar-foot">
          <span className={`status-dot ${online === null ? "is-pending" : online ? "is-on" : "is-off"}`} />
          <span className="muted">
            {online === null ? "Checking API…" : online ? "API connected" : "API offline"}
          </span>
        </div>
      </aside>

      <main className="main">
        {current.kind === "daily" ? (
          <DailyPanel key={current.id} />
        ) : (
          <JobBoardPanel key={current.id} tab={current} />
        )}
      </main>
    </div>
  );
}

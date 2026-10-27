import { useMemo, useState } from "react";
import JobBoardPanel from "./components/JobBoardPanel.jsx";
import { TABS, loadActiveTab, saveActiveTab } from "./tabs.js";
import "./App.css";

export default function App() {
  const [activeTab, setActiveTab] = useState(loadActiveTab);
  const current = useMemo(
    () => TABS.find((tab) => tab.id === activeTab) || TABS[0],
    [activeTab],
  );

  const selectTab = (tabId) => {
    setActiveTab(tabId);
    saveActiveTab(tabId);
  };

  return (
    <div className="page">
      <nav className="tabs" aria-label="Job APIs">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`tab${tab.id === current.id ? " active" : ""}`}
            onClick={() => selectTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>
      <JobBoardPanel key={current.id} tab={current} />
    </div>
  );
}

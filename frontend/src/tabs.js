export const TABS = [
  {
    id: "daily",
    label: "Daily 100",
    kind: "daily",
    icon: "calendar",
    group: "Overview",
    description: "Automatic daily collection of no-login job links.",
  },
  {
    id: "jsearch",
    label: "JSearch",
    icon: "search",
    group: "Sources",
    description: "Google for Jobs aggregator. Broad coverage, many links are login-walled.",
  },
  {
    id: "jobs-api",
    label: "Jobs API",
    icon: "layers",
    group: "Sources",
    description: "Indeed and Bing feeds with direct employer apply links.",
  },
  {
    id: "job-posting-feed",
    label: "Job Posting Feed",
    icon: "bolt",
    group: "Sources",
    description: "Active ATS postings straight from company career pages.",
  },
  {
    id: "daily-international",
    label: "Daily International",
    icon: "globe",
    group: "Sources",
    description: "Daily international postings with structured JSON-LD data.",
  },
];

const TAB_KEY = "jobspy.activeTab";

function tabFromHash() {
  const id = window.location.hash.replace(/^#\/?/, "");
  return TABS.some((tab) => tab.id === id) ? id : null;
}

export function loadActiveTab() {
  const fromHash = tabFromHash();
  if (fromHash) {
    return fromHash;
  }
  try {
    const saved = localStorage.getItem(TAB_KEY);
    if (TABS.some((tab) => tab.id === saved)) {
      return saved;
    }
  } catch {
    /* storage unavailable */
  }
  return TABS[0].id;
}

export function saveActiveTab(tabId) {
  try {
    localStorage.setItem(TAB_KEY, tabId);
  } catch {
    /* storage unavailable */
  }
  if (window.location.hash !== `#/${tabId}`) {
    window.history.replaceState(null, "", `#/${tabId}`);
  }
}

export function onHashTab(callback) {
  const handler = () => {
    const id = tabFromHash();
    if (id) callback(id);
  };
  window.addEventListener("hashchange", handler);
  return () => window.removeEventListener("hashchange", handler);
}

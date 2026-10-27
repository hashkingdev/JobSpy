export const TABS = [
  { id: "jsearch", label: "JSearch", ready: true },
  { id: "jobs-api", label: "Jobs API", ready: true },
  { id: "job-posting-feed", label: "Job Posting Feed API", ready: true },
  { id: "daily-international", label: "Daily International Job Postings", ready: true },
];

const TAB_KEY = "jobspy.activeTab";

export function loadActiveTab() {
  const saved = localStorage.getItem(TAB_KEY);
  if (TABS.some((tab) => tab.id === saved)) {
    return saved;
  }
  return TABS[0].id;
}

export function saveActiveTab(tabId) {
  localStorage.setItem(TAB_KEY, tabId);
}

function formatApiError(data, fallback) {
  if (typeof data?.detail === "string") {
    return data.detail;
  }
  if (Array.isArray(data?.detail) && data.detail[0]?.msg) {
    return data.detail[0].msg;
  }
  return fallback;
}

const OFFLINE_MESSAGE =
  "Cannot reach the backend. Start it with `py run.py` inside backend/ and keep the Vite dev server running, then refresh.";

async function request(url, options, fallback) {
  let response;
  try {
    response = await fetch(url, options);
  } catch {
    // A network-level failure ("Failed to fetch") means the dev server that
    // served this page is gone, so the request never reached the API.
    throw new Error(OFFLINE_MESSAGE);
  }
  const text = await response.text().catch(() => "");
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = {};
  }
  if (!response.ok) {
    if (response.status >= 500 && !text.trim()) {
      // Vite answers with an empty 5xx when its proxy cannot connect to port 8000.
      throw new Error(OFFLINE_MESSAGE);
    }
    throw new Error(formatApiError(data, fallback));
  }
  return data;
}

function post(url, body, fallback) {
  return request(
    url,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    fallback,
  );
}

export function searchJobs(settings) {
  return post("/api/jobs/search", settings, "Job search failed");
}

export function saveJobs(jobs) {
  return post("/api/jobs/save", { jobs }, "Save failed");
}

export function getDailyStatus() {
  return request("/api/daily/status", undefined, "Could not load daily status");
}

export function runDaily() {
  return post("/api/daily/run", {}, "Daily run failed");
}

export function getDailyLinks(date = "today") {
  return request(
    `/api/daily/links?date=${encodeURIComponent(date)}`,
    undefined,
    "Could not load today's links",
  );
}

export function getHealth() {
  return request("/api/health", undefined, "API is not reachable");
}

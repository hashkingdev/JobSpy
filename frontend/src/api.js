function formatApiError(data, fallback) {
  if (typeof data?.detail === "string") {
    return data.detail;
  }
  if (Array.isArray(data?.detail) && data.detail[0]?.msg) {
    return data.detail[0].msg;
  }
  return fallback;
}

async function request(url, options, fallback) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
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

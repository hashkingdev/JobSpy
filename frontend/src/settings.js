const STORAGE_KEY = "jobspy.settings.v6";

export const DEFAULT_SETTINGS = {
  role: "full stack software engineer",
  location_type: "remote",
  country: "usa",
  job_type: "",
  date_posted: "today",
  results_wanted: 100,
  no_login_only: true,
};

export const JOB_TYPES = [
  { id: "", label: "Any" },
  { id: "fulltime", label: "Full-time" },
  { id: "parttime", label: "Part-time" },
  { id: "contract", label: "Contract" },
  { id: "internship", label: "Internship" },
];

export const LOCATION_TYPES = [
  { id: "remote", label: "Remote (work from home)" },
];

export const DATE_OPTIONS = [
  { id: "today", label: "Today" },
];

export const COUNTRIES = [
  { id: "usa", label: "United States" },
];

export function countryLabel(countryId) {
  return COUNTRIES.find((country) => country.id === countryId)?.label || countryId;
}

export function dateLabel(dateId) {
  return DATE_OPTIONS.find((option) => option.id === dateId)?.label || dateId;
}

export function locationLabel(locationId) {
  return LOCATION_TYPES.find((option) => option.id === locationId)?.label || locationId;
}

export function queryPreview(settings) {
  const role = (settings.role || "full stack software engineer").trim();
  const place = countryLabel(settings.country);
  if (settings.location_type === "hybrid") {
    return `${role} hybrid in ${place}`;
  }
  if (settings.location_type === "onsite") {
    return `${role} onsite in ${place}`;
  }
  return `${role} in ${place}`;
}

export function loadSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return { ...DEFAULT_SETTINGS };
    }
    const parsed = { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
    parsed.country = DEFAULT_SETTINGS.country;
    parsed.location_type = DEFAULT_SETTINGS.location_type;
    parsed.date_posted = DEFAULT_SETTINGS.date_posted;
    if (!parsed.role || parsed.role === "software engineer") {
      parsed.role = DEFAULT_SETTINGS.role;
    }
    parsed.results_wanted = Math.min(100, Math.max(1, Number(parsed.results_wanted) || 100));
    parsed.no_login_only = parsed.no_login_only !== false;
    delete parsed.num_pages;
    delete parsed.sites;
    delete parsed.custom_boards;
    return parsed;
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

export function saveSettings(settings) {
  const { sites, custom_boards, ...rest } = settings;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(rest));
}

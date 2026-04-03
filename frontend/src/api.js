import axios from "axios";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

/** Backend origin (same as axios baseURL). Use for links to Swagger, ReDoc, and `/api/schema/`. */
export function getApiBaseUrl() {
  return API_BASE.replace(/\/$/, "");
}

export const api = axios.create({
  baseURL: API_BASE,
});

/** DRF list: either a JSON array or paginated `{ results: [...] }` (when pagination is enabled). */
export function normalizeListResponse(data) {
  if (data == null) return [];
  if (Array.isArray(data)) return data;
  if (Array.isArray(data.results)) return data.results;
  return [];
}

/** Turn axios/DRF errors into a single string for UI messages. */
export function formatApiError(err) {
  const d = err?.response?.data;
  if (d == null) return err?.message || String(err);
  if (typeof d.detail === "string") return d.detail;
  if (Array.isArray(d.detail)) {
    return d.detail.map((x) => (typeof x === "string" ? x : JSON.stringify(x))).join(" ");
  }
  if (typeof d.detail === "object" && d.detail !== null) return JSON.stringify(d.detail);
  if (typeof d === "object") return JSON.stringify(d);
  return String(d);
}

export function setAuthToken(token) {
  if (token) {
    api.defaults.headers.common.Authorization = `Bearer ${token}`;
    localStorage.setItem("accessToken", token);
  } else {
    delete api.defaults.headers.common.Authorization;
    localStorage.removeItem("accessToken");
  }
}

export function setRefreshToken(token) {
  if (token) {
    localStorage.setItem("refreshToken", token);
  } else {
    localStorage.removeItem("refreshToken");
  }
}

const existing = localStorage.getItem("accessToken");
if (existing) setAuthToken(existing);

let refreshPromise = null;

async function refreshAccessToken() {
  const refreshToken = localStorage.getItem("refreshToken");
  if (!refreshToken) {
    throw new Error("Missing refresh token");
  }
  if (!refreshPromise) {
    refreshPromise = axios
      .post(`${API_BASE}/api/auth/token/refresh`, { refresh: refreshToken })
      .then(({ data }) => {
        setAuthToken(data.access);
        if (data.refresh) {
          setRefreshToken(data.refresh);
        }
        return data.access;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

/**
 * Download form responses (CSV or JSON) using the logged-in session.
 * Plain browser navigation to /api/.../export does not send the Authorization header.
 */
export async function downloadFormExport(formId, exportFormat = "csv") {
  try {
    const res = await api.get(`/api/forms/${formId}/export`, {
      params: { export_format: exportFormat },
      responseType: "blob",
    });
    const cd = res.headers["content-disposition"] || res.headers["Content-Disposition"] || "";
    const ext = exportFormat === "json" ? "json" : "csv";
    let filename = `form_${formId}_responses.${ext}`;
    const mStar = /filename\*=UTF-8''([^;\n]+)/i.exec(cd);
    const mQuoted = /filename="([^"]+)"/i.exec(cd);
    if (mStar) {
      try {
        filename = decodeURIComponent(mStar[1].trim());
      } catch {
        filename = mStar[1].trim();
      }
    } else if (mQuoted) {
      filename = mQuoted[1];
    }

    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (e) {
    const data = e.response?.data;
    if (data instanceof Blob) {
      const text = await data.text();
      let detail = text;
      try {
        const j = JSON.parse(text);
        detail = j.detail || j.message || text;
      } catch {
        /* keep text */
      }
      throw new Error(typeof detail === "string" ? detail : "Export failed");
    }
    const d = e.response?.data;
    if (typeof d === "object" && d !== null && d.detail) {
      throw new Error(d.detail);
    }
    throw new Error(e.message || "Export failed");
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    const status = error.response?.status;
    const requestUrl = original?.url || "";
    const isAuthEndpoint = requestUrl.includes("/api/auth/login") || requestUrl.includes("/api/auth/token/refresh");

    if (status === 401 && !original?._retried && !isAuthEndpoint) {
      original._retried = true;
      try {
        const access = await refreshAccessToken();
        original.headers = original.headers || {};
        original.headers.Authorization = `Bearer ${access}`;
        return api(original);
      } catch {
        setAuthToken(null);
        setRefreshToken(null);
      }
    }
    return Promise.reject(error);
  }
);

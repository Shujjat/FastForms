import axios from "axios";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: API_BASE,
});

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

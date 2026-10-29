import axios from "axios";
import {
  AUTH_EXPIRED_EVENT,
  tokenExpiresSoon,
} from "../../features/auth/session-token";

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
  timeout: 60_000,
  headers: {
    "Content-Type": "application/json",
  },
});

const renewalClient = axios.create({
  baseURL: apiClient.defaults.baseURL,
  timeout: 10_000,
});
let renewal: { token: string; promise: Promise<void> } | null = null;

function expireSession(token: string) {
  if (localStorage.getItem("auth_token") !== token) return;
  localStorage.removeItem("auth_token");
  window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
}

async function renewActiveSession(token: string) {
  if (renewal?.token === token) return renewal.promise;
  const promise = renewalClient
    .post<{ access_token: string }>("/api/auth/refresh", null, {
      headers: { Authorization: `Bearer ${token}` },
    })
    .then(({ data }) => {
      // A response from an old account must never overwrite sign-out or a new login.
      if (localStorage.getItem("auth_token") === token)
        localStorage.setItem("auth_token", data.access_token);
    })
    .catch((error: unknown) => {
      if (axios.isAxiosError(error) && error.response?.status === 401) {
        expireSession(token);
        throw error;
      }
      // Transient renewal failures can still use the existing, valid access token.
    })
    .finally(() => {
      if (renewal?.token === token) renewal = null;
    });
  renewal = { token, promise };
  return promise;
}

apiClient.interceptors.request.use(async (config) => {
  let token = localStorage.getItem("auth_token");
  if (
    token &&
    tokenExpiresSoon(token) &&
    !["/api/auth/login", "/api/auth/signup"].includes(config.url ?? "")
  ) {
    await renewActiveSession(token);
    token = localStorage.getItem("auth_token");
  }

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (
      axios.isAxiosError(error) &&
      error.response?.status === 401 &&
      error.config?.url !== "/api/auth/login"
    ) {
      const authorization = String(error.config?.headers.Authorization ?? "");
      if (authorization.startsWith("Bearer "))
        expireSession(authorization.slice(7));
    }
    return Promise.reject(error);
  },
);

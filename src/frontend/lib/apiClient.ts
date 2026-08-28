'use client';

import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from 'axios';

type RetryableRequestConfig = InternalAxiosRequestConfig & {
  _retry?: boolean;
};

type QueueEntry = {
  resolve: () => void;
  reject: (error: unknown) => void;
};

let isRefreshing = false;
let refreshPromise: Promise<void> | null = null;
let interceptorsInstalled = false;

const requestQueue: QueueEntry[] = [];

function flushQueue(error?: unknown) {
  while (requestQueue.length > 0) {
    const entry = requestQueue.shift();
    if (!entry) continue;

    if (error) {
      entry.reject(error);
    } else {
      entry.resolve();
    }
  }
}

// The dashboard authenticates with an HttpOnly session cookie. It no longer
// sends the hardcoded development API key, which did not match any backend key
// and caused protected endpoints to reject otherwise valid sessions.

export const apiClient: AxiosInstance = axios.create({
  baseURL: '',
  withCredentials: true,
  timeout: 30000, // /api/jobs re-reads job reports from disk on a cold cache and can take >15s
});

async function refreshAuthSession() {
  await apiClient.post('/api/auth/refresh');
}

export function installAuthInterceptors(onSessionExpired: () => Promise<void> | void) {
  if (interceptorsInstalled) return;

  apiClient.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
      const originalRequest = error.config as RetryableRequestConfig | undefined;
      const status = error.response?.status;

      if (!originalRequest || status !== 401) {
        return Promise.reject(error);
      }

      const requestUrl = originalRequest.url || '';

      if (
        requestUrl.includes('/api/auth/login') ||
        requestUrl.includes('/api/auth/logout') ||
        requestUrl.includes('/api/auth/refresh') ||
        requestUrl.includes('/api/auth/bootstrap-admin')
      ) {
        return Promise.reject(error);
      }

      if (originalRequest._retry) {
        await onSessionExpired();
        return Promise.reject(error);
      }

      originalRequest._retry = true;

      if (isRefreshing && refreshPromise) {
        return new Promise((resolve, reject) => {
          requestQueue.push({
            resolve: async () => {
              try {
                resolve(apiClient(originalRequest));
              } catch (queueError) {
                reject(queueError);
              }
            },
            reject,
          });
        });
      }

      isRefreshing = true;
      refreshPromise = refreshAuthSession();

      try {
        await refreshPromise;
        flushQueue();
        return apiClient(originalRequest);
      } catch (refreshError) {
        flushQueue(refreshError);
        await onSessionExpired();
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
        refreshPromise = null;
      }
    },
  );

  interceptorsInstalled = true;
}

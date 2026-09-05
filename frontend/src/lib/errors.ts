import axios from "axios";

/**
 * Convert an unknown request failure into a message that is safe and useful for
 * operators. Backend detail strings are only surfaced when they are short,
 * human-readable validation messages; anything else falls back to a generic
 * message so stack traces, paths and internal errors never reach the UI.
 */
export function friendlyError(error: unknown, fallback: string): string {
  if (!axios.isAxiosError(error)) return fallback;

  const status = error.response?.status;
  if (status === 401) return "Your session has expired. Please sign in again.";
  if (status === 403) return "You do not have permission to perform this action.";
  if (status === 404) return "The requested item could not be found.";
  if (status === 409) return "This document is already being processed.";
  if (status === 413) return "The document is too large to upload.";
  if (status === 429) return "Too many requests. Please wait a moment and try again.";
  if (status && status >= 500) return "The service is temporarily unavailable. Please try again shortly.";
  if (!error.response) {
    return error.code === "ECONNABORTED"
      ? "The request timed out. Check the document status before trying again."
      : "Cannot reach the server. Check your connection and try again.";
  }

  const detail = error.response?.data?.detail;
  if (typeof detail === "string" && detail.length > 0 && detail.length <= 200 && !/traceback|exception|[\\/](?:home|usr|var|app)[\\/]/i.test(detail)) {
    return detail;
  }
  return fallback;
}

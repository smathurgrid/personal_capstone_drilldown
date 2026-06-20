import type { ApiErrorResponse } from "@shared/types";

/** Consistent user-facing error messages from unknown thrown values. */

export function getErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof Error) return err.message;
  return fallback;
}

export function parseApiErrorBody(text: string): ApiErrorResponse | null {
  try {
    const parsed = JSON.parse(text) as ApiErrorResponse;
    return parsed?.error?.code ? parsed : null;
  } catch {
    return null;
  }
}

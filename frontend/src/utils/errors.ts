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

/** Human-readable message from a failed fetch response body. */
export function responseErrorMessage(text: string, statusText: string): string {
  const parsed = parseApiErrorBody(text);
  if (parsed?.error?.message) return parsed.error.message;
  if (text) return text;
  return statusText;
}

export async function throwIfResponseNotOk(res: Response): Promise<void> {
  if (res.ok) return;
  const text = await res.text();
  throw new Error(responseErrorMessage(text, res.statusText));
}

// src/services/api.ts
import * as Sentry from "@sentry/browser";

export const askAgent = async (message: string) => {
  const maxRetries = 1;
  const baseDelayMs = 600;
  const timeoutMs = 15000;

  const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(
        "https://northstar-api-deri-99.azurewebsites.net/api/chat",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message }),
          signal: controller.signal,
        },
      );

      if (!response.ok) {
        const body = await response.text().catch(() => "");
        const bodyPreview = body.slice(0, 500);
        const error = new Error(`Backend error ${response.status}`);
        Sentry.captureException(error, {
          tags: { source: "askAgent", status: String(response.status) },
          extra: { bodyPreview, attempt },
        });

        if (
          (response.status >= 500 || response.status === 429) &&
          attempt < maxRetries
        ) {
          const delay = baseDelayMs * Math.pow(2, attempt);
          await sleep(delay);
          continue;
        }
        throw error;
      }

      return response.json();
    } catch (err: any) {
      const isAbort = err?.name === "AbortError";
      Sentry.captureException(err, {
        tags: {
          source: "askAgent",
          attempt: String(attempt),
          timeout: String(isAbort),
        },
      });

      if (attempt < maxRetries) {
        const delay = baseDelayMs * Math.pow(2, attempt);
        await sleep(delay);
        continue;
      }
      throw err;
    } finally {
      clearTimeout(timeout);
    }
  }
};

// src/services/api.ts
import * as Sentry from "@sentry/browser";

export const askAgent = async (message: string) => {
  try {
    const response = await fetch(
      "https://northstar-api-deri-99.azurewebsites.net/api/chat",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      },
    );

    if (!response.ok) {
      const body = await response.text().catch(() => "");
      const bodyPreview = body.slice(0, 500);
      const error = new Error(`Backend error ${response.status}`);
      Sentry.captureException(error, {
        tags: { source: "askAgent", status: String(response.status) },
        extra: { bodyPreview },
      });
      throw error;
    }

    return response.json();
  } catch (err) {
    Sentry.captureException(err, {
      tags: { source: "askAgent" },
    });
    throw err;
  }
};

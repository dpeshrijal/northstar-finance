// src/services/api.ts
export const askAgent = async (message: string) => {
  const response = await fetch(
    "https://northstar-api-deri-99.azurewebsites.net/api/chat",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    },
  );
  return response.json();
};

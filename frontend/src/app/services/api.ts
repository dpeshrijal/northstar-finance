// src/services/api.ts
export const askAgent = async (message: string) => {
  const response = await fetch("http://localhost:7071/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  return response.json();
};

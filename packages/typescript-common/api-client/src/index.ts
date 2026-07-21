import type { ServiceHealth } from "@ai-enterprise-os/types";

export async function getHealth(baseUrl: string): Promise<ServiceHealth> {
  const response = await fetch(`${baseUrl}/healthz`);
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.status}`);
  }
  return (await response.json()) as ServiceHealth;
}

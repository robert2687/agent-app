/** SSE (Server-Sent Events) subscription helper for swarm job streams. */

import type { SwarmEvent } from "@/types";

export interface StreamHandlers {
  onEvent: (event: SwarmEvent) => void;
  onOpen?: () => void;
  onError?: (error: Error) => void;
  onEnd?: () => void;
}

const TERMINAL_TYPES = new Set([
  "job.completed",
  "job.failed",
  "job.cancelled",
  "stream.end",
]);

/**
 * Subscribe to a job's live SSE stream.
 * Returns an unsubscribe function (idempotent).
 */
export function subscribeJobStream(jobId: string, handlers: StreamHandlers): () => void {
  const base = (import.meta.env.VITE_NEXUS_API_BASE as string | undefined) ?? "/api";
  const source = new EventSource(`${base}/swarm/jobs/${jobId}/stream`);
  let closed = false;

  const close = () => {
    if (!closed) {
      closed = true;
      source.close();
    }
  };

  source.onopen = () => handlers.onOpen?.();

  const handle = (type: string) => (messageEvent: MessageEvent<string>) => {
    if (TERMINAL_TYPES.has(type)) {
      close();
      handlers.onEnd?.();
    }
    let data: Record<string, unknown> = {};
    try {
      data = messageEvent.data ? (JSON.parse(messageEvent.data) as Record<string, unknown>) : {};
    } catch {
      data = { raw: messageEvent.data };
    }
    handlers.onEvent({
      type,
      agent: (data.agent as string | undefined) ?? null,
      data,
    });
  };

  const EVENT_TYPES = [
    "job.update",
    "context.built",
    "agent.start",
    "agent.token",
    "agent.complete",
    "edits.applied",
    "validation.result",
    "repair.loop",
    "job.diff",
    "job.completed",
    "job.failed",
    "job.cancelled",
    "stream.end",
  ];
  for (const type of EVENT_TYPES) {
    source.addEventListener(type, handle(type) as EventListener);
  }
  source.addEventListener("message", handle("message") as EventListener);

  source.onerror = () => {
    if (closed) return;
    // EventSource auto-reconnects; surface the error but keep the stream.
    handlers.onError?.(new Error("SSE connection error (auto-reconnecting)"));
  };

  return close;
}

/** React hook managing a live SSE job stream with replay-safe state. */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { subscribeJobStream } from "@/api/stream";
import { api } from "@/api/client";
import type { AgentRole, SwarmEvent } from "@/types";

export type AgentState = "pending" | "running" | "done";

export interface AgentSnapshot {
  role: AgentRole;
  state: AgentState;
  summary: string | null;
  startedAt: string | null;
}

export interface JobStreamState {
  connected: boolean;
  ended: boolean;
  status: string | null;
  currentAgent: string | null;
  agents: Record<string, AgentSnapshot>;
  /** Live token text per agent (accumulated deltas). */
  tokenText: Record<string, string>;
  /** Persisted milestones (non-token events), newest last. */
  timeline: SwarmEvent[];
  repairs: number;
  lastValidationPassed: boolean | null;
  diffFiles: number | null;
  error: string | null;
}

const AGENT_ORDER: AgentRole[] = [
  "planner",
  "architect",
  "coder",
  "reviewer",
  "patcher",
];

const initialState: JobStreamState = {
  connected: false,
  ended: false,
  status: null,
  currentAgent: null,
  agents: Object.fromEntries(
    AGENT_ORDER.map((role) => [
      role,
      { role, state: "pending" as AgentState, summary: null, startedAt: null },
    ]),
  ),
  tokenText: {},
  timeline: [],
  repairs: 0,
  lastValidationPassed: null,
  diffFiles: null,
  error: null,
};

export function useJobStream(jobId: string | null) {
  const [state, setState] = useState<JobStreamState>(initialState);
  const unsubscribeRef = useRef<(() => void) | null>(null);

  // Backfill persisted events once per job (replay when reconnecting mid-job).
  useEffect(() => {
    if (!jobId) return;
    let cancelled = false;
    api
      .listJobEvents(jobId)
      .then((events) => {
        if (cancelled || events.length === 0) return;
        setState((previous) => {
          const next = { ...previous, timeline: [...events] };
          for (const event of events) {
            applyEvent(next, event);
          }
          return next;
        });
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  useEffect(() => {
    unsubscribeRef.current?.();
    unsubscribeRef.current = null;
    if (!jobId) {
      setState(initialState);
      return;
    }

    const unsubscribe = subscribeJobStream(jobId, {
      onOpen: () => setState((previous) => ({ ...previous, connected: true })),
      onEnd: () =>
        setState((previous) => ({ ...previous, connected: false, ended: true })),
      onError: () =>
        setState((previous) => ({ ...previous, connected: false })),
      onEvent: (event) =>
        setState((previous) => {
          const next: JobStreamState = {
            ...previous,
            timeline:
              event.type === "agent.token"
                ? previous.timeline
                : [...previous.timeline, event],
          };
          applyEvent(next, event);
          return next;
        }),
    });
    unsubscribeRef.current = unsubscribe;
    return () => {
      unsubscribe();
      unsubscribeRef.current = null;
    };
  }, [jobId]);

  const reset = useCallback(() => setState(initialState), []);

  return useMemo(() => ({ ...state, reset }), [state, reset]);
}

function applyEvent(state: JobStreamState, event: SwarmEvent): void {
  const agent = event.agent ?? undefined;
  switch (event.type) {
    case "job.update":
      state.status = (event.data.status as string) ?? state.status;
      state.currentAgent = (event.data.current_agent as string) ?? null;
      break;
    case "agent.start":
      if (agent) {
        state.agents = {
          ...state.agents,
          [agent]: {
            ...state.agents[agent],
            state: "running",
            startedAt: new Date().toISOString(),
          },
        };
        state.currentAgent = agent;
      }
      break;
    case "agent.token":
      if (agent) {
        state.tokenText = {
          ...state.tokenText,
          [agent]: (state.tokenText[agent] ?? "") + String(event.data.delta ?? ""),
        };
      }
      break;
    case "agent.complete":
      if (agent) {
        const artifact = event.data.artifact as Record<string, unknown> | undefined;
        state.agents = {
          ...state.agents,
          [agent]: {
            ...state.agents[agent],
            state: "done",
            summary: artifact ? JSON.stringify(artifact) : null,
          },
        };
      }
      break;
    case "edits.applied":
      if (agent && state.agents[agent]) {
        state.agents = {
          ...state.agents,
          [agent]: {
            ...state.agents[agent],
            summary: (event.data.summary as string) ?? null,
          },
        };
      }
      break;
    case "repair.loop":
      state.repairs = Number(event.data.iteration ?? state.repairs + 1);
      break;
    case "validation.result":
      state.lastValidationPassed = Boolean(event.data.passed);
      break;
    case "job.diff":
      state.diffFiles = Number(event.data.files ?? 0);
      break;
    case "job.failed":
      state.error = (event.data.error as string) ?? "Job failed";
      state.status = "failed";
      break;
    case "job.completed":
      state.status = "completed";
      break;
    case "job.cancelled":
      state.status = "cancelled";
      break;
    default:
      break;
  }
}

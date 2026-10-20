// Calls the FastAPI backend with the signed-in user's Firebase ID token.
// The backend's API key is never used in the browser.
import { firebaseAuth } from "@/lib/firebase";
import type {
  AssessResult,
  AssessmentRow,
  ChatReply,
  DemoInput,
  DemoResult,
  Labs,
  Me,
  PatientStatus,
  Profile,
  Reading,
} from "@/lib/types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string, public body?: unknown) {
    super(message);
  }
}

function errorMessage(body: unknown, status: number): string {
  if (body && typeof body === "object") {
    const b = body as { detail?: unknown; errors?: { message?: string }[] };
    if (typeof b.detail === "string") return b.detail;
    if (Array.isArray(b.errors) && b.errors.length) return b.errors.map((e) => e.message).join(" ");
  }
  return `Request failed (${status}).`;
}

async function request<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const token = await firebaseAuth().currentUser?.getIdToken();
  const res = await fetch(`${BASE}${path}`, {
    method: init.method ?? "GET",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
  });
  const body = await res.json().catch(() => undefined);
  if (!res.ok) throw new ApiError(res.status, errorMessage(body, res.status), body);
  return body as T;
}

export interface SignupInput {
  display_name: string;
  age: number;
  sex: string;
  copd: 0 | 1;
  heart_failure: 0 | 1;
  renal: 0 | 1;
  asthma: 0 | 1;
  diabetes: 0 | 1;
  hypertension: 0 | 1;
}

export interface CheckAnswers {
  respiratory_distress: 0 | 1;
  cough: 0 | 1;
  fever: 0 | 1;
  weakness: 0 | 1;
}

export const api = {
  /** Fire-and-forget: starts a sleeping API while Firebase restores the session. */
  wake: () => {
    fetch(`${BASE}/ping`).catch(() => {});
  },
  me: () => request<Me>("/me"),
  signup: (uid: string, input: SignupInput) =>
    request<Profile>("/patients", { method: "POST", body: { patient_id: uid, ...input } }),
  registerDoctor: (display_name: string) => request("/doctors", { method: "POST", body: { display_name } }),
  updateProfile: (id: string, changes: Partial<SignupInput>) =>
    request<Profile>(`/patients/${id}`, { method: "PATCH", body: changes }),
  linkDoctor: (id: string, email: string) =>
    request<{ doctor_ids: string[]; linked: { display_name: string } }>(`/patients/${id}/doctors`, {
      method: "POST",
      body: { email },
    }),
  unlinkDoctor: (id: string, doctorUid: string) =>
    request<{ doctor_ids: string[] }>(`/patients/${id}/doctors/${doctorUid}`, { method: "DELETE" }),
  patients: () => request<{ patients: { patient_id: string; display_name: string }[] }>("/patients"),
  status: (id: string) => request<PatientStatus>(`/patients/${id}`),
  assess: (id: string, answers: CheckAnswers) =>
    request<AssessResult>(`/patients/${id}/assess`, { method: "POST", body: answers }),
  assessments: (id: string, limit = 60) =>
    request<{ assessments: AssessmentRow[] }>(`/patients/${id}/assessments?limit=${limit}`),
  readings: (id: string, days = 7) => request<{ readings: Reading[] }>(`/patients/${id}/readings?days=${days}`),
  uploadLabs: (id: string, labs: Omit<Labs, "taken_at"> & { taken_at?: string }) =>
    request<Labs>(`/patients/${id}/labs`, { method: "POST", body: labs }),
  chat: (message: string, conversationId?: string, patientId?: string) =>
    request<ChatReply>("/chat", {
      method: "POST",
      body: { message, conversation_id: conversationId, patient_id: patientId },
    }),
  demoRun: (input: DemoInput) => request<DemoResult>("/demo/run", { method: "POST", body: input }),
};

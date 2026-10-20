import type { Band, Condition, Vital } from "@/lib/types";

// How each result is shown to patients: plain words, no jargon.
export const BAND_INFO: Record<Band, { label: string; summary: string; tone: string; dot: string }> = {
  Low: {
    label: "No concern right now",
    summary: "Your latest check found no signs of concern.",
    tone: "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-100",
    dot: "bg-emerald-500",
  },
  Pending: {
    label: "More information needed",
    summary: "The check needs a little more information to finish.",
    tone: "border-slate-200 bg-slate-50 text-slate-900 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100",
    dot: "bg-slate-400",
  },
  Moderate: {
    label: "Keep an eye on it",
    summary: "Some readings are outside the usual range.",
    tone: "border-amber-200 bg-amber-50 text-amber-950 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-100",
    dot: "bg-amber-500",
  },
  Watch: {
    label: "Possible concern: re-checking",
    summary: "The check flagged a possible concern and will confirm it soon.",
    tone: "border-orange-200 bg-orange-50 text-orange-950 dark:border-orange-900 dark:bg-orange-950 dark:text-orange-100",
    dot: "bg-orange-500",
  },
  High: {
    label: "See a doctor today",
    summary: "Your results suggest a raised risk of a chest infection.",
    tone: "border-red-200 bg-red-50 text-red-950 dark:border-red-900 dark:bg-red-950 dark:text-red-100",
    dot: "bg-red-600",
  },
};

export const BAND_ORDER: Band[] = ["Low", "Pending", "Moderate", "Watch", "High"];

export const VITAL_INFO: Record<Vital, { label: string; unit: string; digits: number }> = {
  heart_rate: { label: "Heart rate", unit: "bpm", digits: 0 },
  respiratory_rate: { label: "Breathing rate", unit: "/min", digits: 0 },
  sbp: { label: "Blood pressure (top)", unit: "mmHg", digits: 0 },
  spo2: { label: "Blood oxygen", unit: "%", digits: 0 },
  temperature: { label: "Temperature", unit: "°F", digits: 1 },
};

export const VITALS: Vital[] = ["heart_rate", "respiratory_rate", "sbp", "spo2", "temperature"];

export const CONDITION_LABELS: Record<Condition, string> = {
  copd: "COPD (chronic lung disease)",
  asthma: "Asthma",
  heart_failure: "Heart failure",
  renal: "Kidney disease",
  diabetes: "Diabetes",
  hypertension: "High blood pressure",
};

export const CONDITIONS = Object.keys(CONDITION_LABELS) as Condition[];

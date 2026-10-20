import {
  Activity,
  CircleCheck,
  Droplet,
  Eye,
  Heart,
  Hourglass,
  type LucideIcon,
  RefreshCw,
  Stethoscope,
  Thermometer,
  Wind,
} from "lucide-react";

import type { Band, Condition, Vital } from "@/lib/types";

// How each result is shown to patients: plain words, no jargon. Colours are Apple's system colours.
export const BAND_INFO: Record<
  Band,
  { label: string; summary: string; color: string; tone: string; dot: string; icon: LucideIcon; badge: string }
> = {
  Low: {
    label: "No concern right now",
    summary: "Your latest check found no signs of concern.",
    color: "#16a34a",
    tone: "bg-[#16a34a]/10 text-[#15803d]",
    dot: "bg-[#16a34a]",
    icon: CircleCheck,
    badge: "bg-[#16a34a]/15 text-[#15803d]",
  },
  Pending: {
    label: "More information needed",
    summary: "The check needs a little more information to finish.",
    color: "#64748b",
    tone: "bg-[#64748b]/10 text-[#475569]",
    dot: "bg-[#64748b]",
    icon: Hourglass,
    badge: "bg-[#64748b]/15 text-[#475569]",
  },
  Moderate: {
    label: "Keep an eye on it",
    summary: "Some readings are outside the usual range.",
    color: "#ca8a04",
    tone: "bg-[#ca8a04]/15 text-[#a16207]",
    dot: "bg-[#ca8a04]",
    icon: Eye,
    badge: "bg-[#ca8a04]/20 text-[#a16207]",
  },
  Watch: {
    label: "Possible concern: re-checking",
    summary: "The check flagged a possible concern and will confirm it soon.",
    color: "#ea580c",
    tone: "bg-[#ea580c]/10 text-[#c2410c]",
    dot: "bg-[#ea580c]",
    icon: RefreshCw,
    badge: "bg-[#ea580c]/15 text-[#c2410c]",
  },
  High: {
    label: "See a doctor today",
    summary: "Your results suggest a raised risk of a chest infection.",
    color: "#dc2626",
    tone: "bg-[#dc2626]/10 text-[#b91c1c]",
    dot: "bg-[#dc2626]",
    icon: Stethoscope,
    badge: "bg-[#dc2626]/15 text-[#b91c1c]",
  },
};

export const BAND_ORDER: Band[] = ["Low", "Pending", "Moderate", "Watch", "High"];

// Each vital's icon and colour (widgets and charts), and the usual resting range for an adult, shown as
// "Typical" next to the reading. The range is for orientation only; the alerts and the models decide risk.
export const VITAL_INFO: Record<
  Vital,
  { label: string; unit: string; digits: number; icon: LucideIcon; color: string; range: [number, number] }
> = {
  heart_rate: { label: "Heart rate", unit: "bpm", digits: 0, icon: Heart, color: "#e11d48", range: [60, 100] },
  respiratory_rate: { label: "Breathing rate", unit: "/min", digits: 0, icon: Wind, color: "#0891b2", range: [12, 20] },
  sbp: { label: "Blood pressure (top)", unit: "mmHg", digits: 0, icon: Activity, color: "#dc2626", range: [90, 120] },
  spo2: { label: "Blood oxygen", unit: "%", digits: 0, icon: Droplet, color: "#2563eb", range: [95, 100] },
  temperature: { label: "Temperature", unit: "°F", digits: 1, icon: Thermometer, color: "#ea580c", range: [97, 99] },
};

export const VITALS: Vital[] = ["heart_rate", "respiratory_rate", "sbp", "spo2", "temperature"];

export const LAB_COLOR = "#7c3aed";

export const CONDITION_LABELS: Record<Condition, string> = {
  copd: "COPD (chronic lung disease)",
  asthma: "Asthma",
  heart_failure: "Heart failure",
  renal: "Kidney disease",
  diabetes: "Diabetes",
  hypertension: "High blood pressure",
};

export const CONDITIONS = Object.keys(CONDITION_LABELS) as Condition[];

export type Band = "Low" | "Pending" | "Moderate" | "Watch" | "High";
export type Vital = "heart_rate" | "respiratory_rate" | "sbp" | "spo2" | "temperature";
export type Condition = "copd" | "heart_failure" | "renal" | "asthma" | "diabetes" | "hypertension";
export type Sex = "female" | "male" | "other" | "prefer_not_to_say";

export interface Alert {
  code: string;
  message: string;
  value: number;
}

export interface Labs {
  wbc: number;
  neutrophils: number;
  lymphocytes: number;
  crp: number;
  taken_at: string;
}

export interface Profile {
  patient_id: string;
  display_name: string;
  age: number | null;
  sex: Sex | null;
  doctor_ids: string[];
  history_flags: Record<Condition, 0 | 1 | null>;
}

export interface Me {
  kind: "user" | "service";
  uid?: string;
  email?: string | null;
  role?: "patient" | "doctor" | null;
  profile?: Profile | null;
}

export interface Reading {
  vital: Vital;
  value: number;
  taken_at: string;
  entered_by?: string;
}

export interface PatientStatus {
  patient_id: string;
  display_name: string;
  age: number | null;
  sex: Sex | null;
  alerts: Alert[];
  critical_notice: string | null;
  lead_text: string | null;
  stage1_ready: boolean;
  missing_for_stage1: Vital[];
  history_flags: Record<Condition, 0 | 1 | null>;
  labs: Labs | null;
  latest_readings: Partial<Record<Vital, Reading>>;
  reading_counts: Record<"24h" | "7d", Record<Vital, number>>;
}

export interface MissingItem {
  item: string;
  type: "reading" | "input" | "history_flag" | "profile" | "symptom" | "labs";
  message: string;
}

export interface AssessResult {
  patient_id: string;
  stage: 1 | 2 | null;
  band: Band | null;
  alerts: Alert[];
  critical_notice: string | null;
  lead_text: string | null;
  recommendation: string | null;
  missing: MissingItem[];
  persistence: { status: string; reassess_after?: string; reassess_before?: string } | null;
  disclaimer: string;
  note?: string;
  assessed_at: string;
}

export interface AssessmentRow {
  assessment_id: string;
  created_at: string;
  stage: 1 | 2;
  band: Band;
  risk_score_stage1: number | null;
  risk_score_stage2: number | null;
  alerts: Alert[];
}

export interface ChatReply {
  conversation_id: string;
  reply: string;
  error: boolean;
  latest_result: AssessResult | null;
}

export interface DemoInput {
  readings: Partial<Record<Vital, number[]>>;
  age: number;
  sex: Sex;
  copd: 0 | 1;
  heart_failure: 0 | 1;
  renal: 0 | 1;
  asthma: 0 | 1;
  diabetes: 0 | 1;
  hypertension: 0 | 1;
  respiratory_distress: 0 | 1;
  hypoxemia: 0 | 1;
  cough: 0 | 1;
  fever: 0 | 1;
  weakness: 0 | 1;
  labs: Omit<Labs, "taken_at"> | null;
}

/** /demo/run: the usual result plus the raw scores and the features each model saw. */
export interface DemoResult extends AssessResult {
  risk_score_stage1: number | null;
  risk_score_stage2: number | null;
  demo: {
    p_stage1: number | null;
    p_stage2: number | null;
    stage2_shadow: boolean;
    threshold_stage1: number;
    threshold_stage2: number;
    amber_zone: [number, number];
    pneumonia_percentage: number | null;
    risk_zone: "green" | "amber" | "red" | null;
    features_stage1: Record<string, number> | null;
    features_stage2: Record<string, number> | null;
  };
}

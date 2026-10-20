"use client";

import { PageHeader } from "@/components/app-shell";
import { PatientHistory } from "@/components/patient-history";
import { useAuth } from "@/lib/auth-context";

export default function HistoryPage() {
  const { me } = useAuth();
  return (
    <>
      <PageHeader title="History" />
      <PatientHistory patientId={me!.uid!} />
    </>
  );
}

"use client";

import { PatientHistory } from "@/components/patient-history";
import { useAuth } from "@/lib/auth-context";

export default function HistoryPage() {
  const { me } = useAuth();
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">History</h1>
      <PatientHistory patientId={me!.uid!} />
    </div>
  );
}

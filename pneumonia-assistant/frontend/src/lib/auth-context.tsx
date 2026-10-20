"use client";

import { onAuthStateChanged, signOut, type User } from "firebase/auth";
import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { api } from "@/lib/api";
import { firebaseAuth, firebaseConfigured } from "@/lib/firebase";
import type { Me } from "@/lib/types";

interface AuthState {
  user: User | null;
  me: Me | null;            // the API's view: role and profile
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(firebaseConfigured);   // nothing to wait for without Firebase
  const [error, setError] = useState<string | null>(null);

  const loadMe = useCallback(async (u: User | null) => {
    if (!u) {
      setMe(null);
      return;
    }
    try {
      setMe(await api.me());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not reach the server.");
    }
  }, []);

  useEffect(() => {
    if (!firebaseConfigured) return;
    api.wake();
    return onAuthStateChanged(firebaseAuth(), async (u) => {
      setUser(u);
      await loadMe(u);
      setLoading(false);
    });
  }, [loadMe]);

  const value: AuthState = {
    user,
    me,
    loading,
    error,
    refresh: () => loadMe(firebaseAuth().currentUser),
    logout: () => signOut(firebaseAuth()),
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

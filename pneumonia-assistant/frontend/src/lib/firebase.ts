// Firebase web config is public by design (it identifies the project; access is
// controlled by Firebase Auth and the API). Values come from .env.local.
// Initialised lazily in the browser, so pre-rendering at build time never touches it.
import { getApp, getApps, initializeApp } from "firebase/app";
import { getAuth, type Auth } from "firebase/auth";

const config = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

export const firebaseConfigured = Boolean(config.apiKey && config.authDomain && config.projectId);

let auth: Auth | null = null;

export function firebaseAuth(): Auth {
  if (!firebaseConfigured) throw new Error("Firebase is not configured: fill in .env.local.");
  if (!auth) auth = getAuth(getApps().length ? getApp() : initializeApp(config));
  return auth;
}

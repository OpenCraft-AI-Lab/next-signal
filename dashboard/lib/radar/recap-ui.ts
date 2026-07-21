/**
 * Cookie persisting the Smart Recap collapse preference. Lives in a plain
 * (non-"use client") module so BOTH the server radar page (which reads it via
 * `cookies()`) and the client `SmartRecapSection` (which writes it) can import
 * the same constant. Importing a runtime value from a "use client" module into
 * a server component yields a client reference, not the string — so the name
 * must not live in the component file.
 */
export const RECAP_COLLAPSED_COOKIE = "paca_recap_collapsed";

import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Compose className strings; latter Tailwind utility wins on conflict. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

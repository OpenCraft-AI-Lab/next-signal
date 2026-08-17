/**
 * GBrain's supported embedding providers, mirroring
 * `next_signal.integrations.gbrain.EMBEDDING_PROVIDERS` (sorted keys of its
 * `_PROVIDER_CREDENTIAL` map). The credential each hosted provider reads is
 * the exact env-var name GBrain's own subprocess expects — an external
 * contract this file does not choose and must not rename.
 *
 * Pure constants/types/helpers only — no `"use server"` here. A file with
 * that directive may only export async functions (every export becomes a
 * callable Server Action reference), so the plain lookup below lives outside
 * `lib/actions/knowledge-embedding.ts`, mirroring the existing
 * `lib/secrets.ts` (pure) vs `lib/actions/secrets.ts` (`"use server"`) split.
 */
export const KNOWLEDGE_EMBEDDING_PROVIDERS = [
  "google",
  "llama-server",
  "lmstudio",
  "ollama",
  "openai",
  "voyage",
] as const;

export type KnowledgeEmbeddingProvider = (typeof KNOWLEDGE_EMBEDDING_PROVIDERS)[number];

export const PROVIDER_CREDENTIAL: Record<KnowledgeEmbeddingProvider, string | null> = {
  openai: "OPENAI_API_KEY",
  voyage: "VOYAGE_API_KEY",
  google: "GOOGLE_GENERATIVE_AI_API_KEY",
  ollama: null,
  lmstudio: null,
  "llama-server": null,
};

export function knowledgeEmbeddingCredential(
  provider: KnowledgeEmbeddingProvider,
): string | null {
  return PROVIDER_CREDENTIAL[provider];
}

export type GbrainReadinessState =
  | "not_initialized"
  | "credential_missing"
  | "ready"
  | "indeterminate";

export interface GbrainReadiness {
  state: GbrainReadinessState;
  /** The provider half of the configured `<provider>:<model>`, if initialized. */
  provider: string | null;
  model: string | null;
}

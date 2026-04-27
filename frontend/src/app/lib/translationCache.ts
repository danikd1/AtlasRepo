import type { TranslationResult } from "../components/TranslateButton";

const cache = new Map<number, TranslationResult>();

export const translationCache = {
  get: (articleId: number): TranslationResult | null => cache.get(articleId) ?? null,
  set: (articleId: number, result: TranslationResult) => cache.set(articleId, result),
  has: (articleId: number): boolean => cache.has(articleId),
};

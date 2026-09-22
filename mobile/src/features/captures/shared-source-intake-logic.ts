import type { MentionedShareDeepLinkParseResult } from '@/utils/shared-source-url';

export type IncomingShareLinkDecision =
  | { type: 'non-share-link' }
  | { type: 'invalid-share-link' }
  | { type: 'duplicate' }
  | { type: 'accept'; sourceUrl: string; sourceKey: string; immediate: boolean };

export type IncomingShareLinkContext = {
  handledSharedSourceKeys: ReadonlySet<string>;
  pendingSourceKey: string | null;
  inFlightShareKey: string | null;
  isAuthLoading: boolean;
  isSignedIn: boolean;
};

// Pure decision for what to do with an incoming share deep link, extracted
// out of useSharedSourceIntake so the branching can be unit tested without
// mounting the hook. Side effects (storage writes, state updates) stay in
// the hook; this only decides which branch applies.
export function decideIncomingShareLink(
  result: MentionedShareDeepLinkParseResult,
  context: IncomingShareLinkContext,
): IncomingShareLinkDecision {
  if (result.type === 'non-share-link') {
    return { type: 'non-share-link' };
  }

  if (result.type === 'invalid-share-link') {
    return { type: 'invalid-share-link' };
  }

  const sourceKey = result.sourceUrl;
  if (
    context.handledSharedSourceKeys.has(sourceKey) ||
    context.pendingSourceKey === sourceKey ||
    context.inFlightShareKey === sourceKey
  ) {
    return { type: 'duplicate' };
  }

  return {
    type: 'accept',
    sourceUrl: result.sourceUrl,
    sourceKey,
    immediate: !context.isAuthLoading && context.isSignedIn,
  };
}

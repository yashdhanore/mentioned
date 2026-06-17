// Platform-resolved at bundle time: auth-signin.native.ts (iOS/Android native
// ID-token flow) or auth-signin.web.ts (browser OAuth flow). This declaration
// gives tsc the shared interface since it does not resolve platform extensions.
export function signInWithApple(): Promise<void>;
export function signInWithGoogle(): Promise<void>;

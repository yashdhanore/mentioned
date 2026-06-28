import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const root = process.cwd();
const hook = readFileSync(join(root, 'src/features/auth/use-auth-session.ts'), 'utf8');
const app = readFileSync(join(root, 'App.tsx'), 'utf8');

assert.match(hook, /export function useAuthSession/);
assert.match(hook, /setAccessTokenProvider/);
assert.match(hook, /clearAccessTokenProvider/);
assert.match(hook, /isDevAuthEnabled/);
assert.match(hook, /supabase\.auth\.onAuthStateChange/);
assert.match(hook, /signInWithApple/);
assert.match(hook, /signInWithGoogle/);
assert.match(hook, /disableRegisteredPushToken/);
assert.doesNotMatch(app, /supabase\.auth\.onAuthStateChange/);
assert.doesNotMatch(app, /setAccessTokenProvider/);
assert.match(app, /useAuthSession/);

console.log('auth session hook check passed');

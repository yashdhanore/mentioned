import assert from 'node:assert/strict';

import {
  isUnsafeSupabasePublicKey,
  validateSupabaseMobileConfig,
} from '../src/supabase-runtime-config';

const anonPayload = Buffer.from(JSON.stringify({ role: 'anon' })).toString('base64url');
const serviceRolePayload = Buffer.from(JSON.stringify({ role: 'service_role' })).toString(
  'base64url',
);
const legacyAnonJwt = `header.${anonPayload}.signature`;
const legacyServiceRoleJwt = `header.${serviceRolePayload}.signature`;

assert.equal(isUnsafeSupabasePublicKey('sb_publishable_abc'), false);
assert.equal(isUnsafeSupabasePublicKey(legacyAnonJwt), false);
assert.equal(isUnsafeSupabasePublicKey('sb_secret_abc'), true);
assert.equal(isUnsafeSupabasePublicKey(legacyServiceRoleJwt), true);

assert.doesNotThrow(() =>
  validateSupabaseMobileConfig({
    appEnv: 'production',
    supabaseUrl: 'https://project-ref.supabase.co',
    supabasePublishableKey: 'sb_publishable_abc',
    authRedirectUrlOverride: '',
  }),
);

assert.throws(() =>
  validateSupabaseMobileConfig({
    appEnv: 'production',
    supabaseUrl: 'http://127.0.0.1:54321',
    supabasePublishableKey: 'sb_publishable_abc',
    authRedirectUrlOverride: '',
  }),
);

assert.throws(() =>
  validateSupabaseMobileConfig({
    appEnv: 'production',
    supabaseUrl: 'https://project-ref.supabase.co',
    supabasePublishableKey: 'sb_secret_abc',
    authRedirectUrlOverride: '',
  }),
);

assert.throws(() =>
  validateSupabaseMobileConfig({
    appEnv: 'production',
    supabaseUrl: 'https://project-ref.supabase.co',
    supabasePublishableKey: legacyServiceRoleJwt,
    authRedirectUrlOverride: '',
  }),
);

assert.throws(() =>
  validateSupabaseMobileConfig({
    appEnv: 'production',
    supabaseUrl: 'https://project-ref.supabase.co',
    supabasePublishableKey: 'sb_publishable_abc',
    authRedirectUrlOverride: 'exp://localhost:8081/--/auth/callback',
  }),
);

assert.doesNotThrow(() =>
  validateSupabaseMobileConfig({
    appEnv: 'development',
    supabaseUrl: '',
    supabasePublishableKey: '',
    authRedirectUrlOverride: 'exp://localhost:8081/--/auth/callback',
  }),
);

console.log('supabase config tests passed');

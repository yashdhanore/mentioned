import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const root = process.cwd();
const hook = readFileSync(join(root, 'src/features/captures/use-shared-source-intake.ts'), 'utf8');
const app = readFileSync(join(root, 'App.tsx'), 'utf8');

assert.match(hook, /export function useSharedSourceIntake/);
assert.match(hook, /parseMentionedShareDeepLink/);
assert.match(hook, /createPendingSharedSourceStore/);
assert.match(hook, /initialShareUrlProcessedRef/);
assert.match(hook, /inFlightShareKeyRef/);
assert.match(hook, /submitPendingSharedSource/);
assert.match(hook, /discardPendingSharedSource/);
assert.doesNotMatch(app, /parseMentionedShareDeepLink/);
assert.doesNotMatch(app, /createPendingSharedSourceStore/);
assert.match(app, /useSharedSourceIntake/);

console.log('shared source intake hook check passed');

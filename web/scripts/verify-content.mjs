import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

const requiredFiles = [
  'src/data/landing-content.ts',
  'src/components/FeedToShelf.astro',
  'src/components/WaitlistSignup.astro',
  'src/pages/index.astro',
  'src/styles/global.css',
  'src/scripts/landing-motion.ts'
];

for (const file of requiredFiles) {
  assert.equal(existsSync(join(root, file)), true, `${file} must exist`);
}

const read = (file) => readFileSync(join(root, file), 'utf8');
const source = requiredFiles.map(read).join('\n');
const css = read('src/styles/global.css');
const motion = read('src/scripts/landing-motion.ts');

const requiredCopy = [
  'Turn BookTok into your reading list.',
  'Send Mentioned a Reel or TikTok.',
  'How a Reel becomes a reading list.',
  'Send it to Mentioned.',
  'Mentioned looks for books.',
  'Your list gets updated.',
  'No clear title?',
  'The post stays with the books.',
  'Mentioned pulls the book rec out of the Reel',
  'Join the BookTok-to-TBR waitlist.',
  'Get the iOS share-sheet build first.',
  'Save your first Reel when invites open.',
  'Never lose a book rec in the feed again.'
];

for (const copy of requiredCopy) {
  assert.equal(source.includes(copy), true, `Missing required copy: ${copy}`);
}

const bannedPatterns = [
  [/1\.2M/i, 'fake social metric'],
  [/testimonial/i, 'testimonial claim'],
  [/App Store/i, 'store badge or store claim'],
  [/Google Play/i, 'Android store claim'],
  [/Inter/i, 'banned font'],
  [/Roboto/i, 'banned font'],
  [/Arial/i, 'banned font'],
  [/Open Sans/i, 'banned font'],
  [/Helvetica/i, 'banned font'],
  [/ease-in-out/i, 'banned default motion curve']
];

for (const [pattern, label] of bannedPatterns) {
  assert.equal(pattern.test(source), false, `Remove ${label}`);
}

assert.match(css, /\.double-bezel/, 'global CSS must define double-bezel card architecture');
assert.match(css, /\.magnetic-button__orb/, 'CTA must use nested icon orb architecture');
assert.match(css, /prefers-reduced-motion:\s*reduce/, 'CSS must include reduced-motion handling');
assert.match(css, /cubic-bezier\(0\.32,\s*0\.72,\s*0,\s*1\)/, 'CSS must use custom spring-like easing');
assert.match(motion, /ScrollTrigger/, 'motion script must use ScrollTrigger for desktop scroll choreography');
assert.match(motion, /matchMedia/, 'motion script must use media queries for desktop-only behavior');
assert.match(motion, /prefers-reduced-motion/, 'motion script must respect reduced-motion preferences');
assert.match(motion, /autoAlpha/, 'motion should animate opacity with GSAP autoAlpha');
assert.doesNotMatch(motion, /addEventListener\(['"]scroll['"]/, 'do not use continuous scroll listeners');

console.log('landing content verification passed');

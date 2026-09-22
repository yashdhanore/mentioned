// One-off generator for public/og-image.png. Run with `node scripts/generate-og-image.mjs`
// after changing the OG copy or mark; commit the regenerated PNG, not this script's output.
import sharp from 'sharp';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const WIDTH = 1200;
const HEIGHT = 630;
const PAPER = '#f4efe5';
const INK = '#101a17';
const SECONDARY = '#4e5d57';

const markPath = join(__dirname, '../public/assets/app-mark.png');
const outPath = join(__dirname, '../public/og-image.png');

const MARK_SIZE = 148;
const circleMask = Buffer.from(
  `<svg width="${MARK_SIZE}" height="${MARK_SIZE}"><circle cx="${MARK_SIZE / 2}" cy="${MARK_SIZE / 2}" r="${MARK_SIZE / 2}" fill="#fff" /></svg>`,
);
const mark = await sharp(markPath)
  .resize(MARK_SIZE, MARK_SIZE)
  .composite([{ input: circleMask, blend: 'dest-in' }])
  .png()
  .toBuffer();

const svg = `
<svg width="${WIDTH}" height="${HEIGHT}" xmlns="http://www.w3.org/2000/svg">
  <rect width="${WIDTH}" height="${HEIGHT}" fill="${PAPER}" />
  <text x="290" y="330" font-family="Arial, sans-serif" font-size="72" font-weight="800" fill="${INK}">Mentioned</text>
  <text x="290" y="390" font-family="Arial, sans-serif" font-size="30" fill="${SECONDARY}">Turn BookTok into your reading list.</text>
</svg>
`;

await sharp({
  create: { width: WIDTH, height: HEIGHT, channels: 4, background: PAPER },
})
  .composite([
    { input: Buffer.from(svg), top: 0, left: 0 },
    { input: mark, top: 241, left: 96 },
  ])
  .png()
  .toFile(outPath);

console.log(`wrote ${outPath}`);

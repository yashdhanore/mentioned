import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

const reducedMotionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');

if (reducedMotionQuery.matches) {
  applyReducedMotionState();
} else {
  initEnhancedMotion();
}

reducedMotionQuery.addEventListener('change', () => {
  window.location.reload();
});

function applyReducedMotionState() {
  document.documentElement.dataset.motion = 'reduced';
  gsap.set('[data-reveal], [data-hero-reel], [data-hero-artifact], [data-story-card], [data-shelf-fragment], [data-shelf-phone], [data-shelf-memory], [data-final-book]', {
    autoAlpha: 1,
    clearProps: 'transform'
  });
  initFinalBookCanvases(true);
}

function initEnhancedMotion() {
  document.documentElement.dataset.motion = 'enhanced';
  initFinalBookCanvases(false);

  gsap.utils.toArray<HTMLElement>('[data-reveal]').forEach((element, index) => {
    gsap.to(element, {
      autoAlpha: 1,
      y: 0,
      duration: 0.95,
      delay: Math.min(index * 0.05, 0.2),
      ease: 'power4.out',
      scrollTrigger: {
        trigger: element,
        start: 'top 86%',
        once: true
      }
    });
  });

  gsap.fromTo(
    '[data-hero-reel]',
    { autoAlpha: 0, y: 44, rotation: -4, scale: 0.96 },
    { autoAlpha: 1, y: 0, rotation: -1.5, scale: 1, duration: 1.1, ease: 'power4.out' }
  );

  gsap.fromTo(
    '[data-hero-artifact]',
    { autoAlpha: 0, y: 36, scale: 0.94 },
    { autoAlpha: 1, y: 0, scale: 1, duration: 0.9, stagger: 0.1, ease: 'power4.out', delay: 0.12 }
  );

  const media = gsap.matchMedia();

  media.add('(min-width: 901px) and (prefers-reduced-motion: no-preference)', () => {
    initStoryTimeline();
    initShelfTimeline();

    return () => {
      ScrollTrigger.getAll().forEach((trigger) => trigger.kill());
    };
  });
}

function initStoryTimeline() {
  const stage = document.querySelector<HTMLElement>('[data-story-stage]');
  const path = document.querySelector<SVGPathElement>('[data-story-path]');

  if (!stage || !path) {
    return;
  }

  const pathLength = path.getTotalLength();
  gsap.set(path, {
    strokeDasharray: pathLength,
    strokeDashoffset: pathLength
  });

  const cards = gsap.utils.toArray<HTMLElement>('[data-story-card]');
  gsap.set(cards, { autoAlpha: 0, y: 44, scale: 0.96 });
  gsap.set(cards[0], { autoAlpha: 1, y: 0, scale: 1 });

  const timeline = gsap.timeline({
    scrollTrigger: {
      trigger: stage,
      start: 'top 16%',
      end: '+=950',
      pin: true,
      scrub: 0.5,
      anticipatePin: 1
    }
  });

  timeline
    .to(path, { strokeDashoffset: 0, duration: 1.5, ease: 'power1.out' })
    .to(cards, { autoAlpha: 1, y: 0, scale: 1, stagger: 0.18, duration: 0.9, ease: 'power3.out' }, 0.08);
}

function initShelfTimeline() {
  const stage = document.querySelector<HTMLElement>('[data-shelf-stage]');

  if (!stage) {
    return;
  }

  const fragments = gsap.utils.toArray<HTMLElement>('[data-shelf-fragment]');
  const phone = document.querySelector<HTMLElement>('[data-shelf-phone]');
  const memory = document.querySelector<HTMLElement>('[data-shelf-memory]');

  gsap.set(fragments, { autoAlpha: 1 });
  gsap.set([phone, memory], { autoAlpha: 0, y: 44, scale: 0.96 });

  const timeline = gsap.timeline({
    scrollTrigger: {
      trigger: stage,
      start: 'top 18%',
      end: '+=1050',
      pin: true,
      scrub: 0.55,
      anticipatePin: 1
    }
  });

  timeline
    .to(fragments[0], { x: 160, y: 120, rotation: -2, scale: 0.9, duration: 1, ease: 'power1.out' }, 0)
    .to(fragments[1], { x: 220, y: -42, rotation: 1, scale: 0.88, duration: 1, ease: 'power1.out' }, 0)
    .to(fragments[2], { x: -180, y: -94, rotation: 2, scale: 0.9, duration: 1, ease: 'power1.out' }, 0)
    .to(fragments, { autoAlpha: 0.18, duration: 0.35, ease: 'power1.out' }, 0.55)
    .to(phone, { autoAlpha: 1, y: 0, scale: 1, duration: 0.45, ease: 'power3.out' }, 0.38)
    .to(memory, { autoAlpha: 1, y: 0, scale: 1, duration: 0.42, ease: 'power3.out' }, 0.58);
}

type BookCell = {
  x: number;
  y: number;
  size: number;
  delay: number;
  color: string;
  alpha: number;
  seedX: number;
  seedY: number;
};

type CanvasState = {
  canvas: HTMLCanvasElement;
  context: CanvasRenderingContext2D;
  width: number;
  height: number;
  cells: BookCell[];
  start: number;
  reduced: boolean;
};

function initFinalBookCanvases(reduced: boolean) {
  document.querySelectorAll<HTMLCanvasElement>('[data-final-book-canvas]').forEach((canvas) => {
    if (canvas.dataset.finalBookReady === 'true') {
      return;
    }

    const context = canvas.getContext('2d');
    if (!context) {
      return;
    }

    canvas.dataset.finalBookReady = 'true';
    const state: CanvasState = {
      canvas,
      context,
      width: 0,
      height: 0,
      cells: [],
      start: performance.now(),
      reduced
    };

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const width = Math.max(280, Math.round(rect.width));
      const height = Math.max(220, Math.round(rect.height));
      const ratio = Math.min(window.devicePixelRatio || 1, 2);

      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      state.width = width;
      state.height = height;
      state.cells = createBookCells(width, height);
      drawFinalBook(state, reduced ? 4200 : performance.now());
    };

    resize();
    window.addEventListener('resize', resize, { passive: true });

    if (reduced) {
      return;
    }

    const tick = (now: number) => {
      drawFinalBook(state, now);
      requestAnimationFrame(tick);
    };

    requestAnimationFrame(tick);
  });
}

function createBookCells(width: number, height: number): BookCell[] {
  const cells: BookCell[] = [];
  const gridColumns = 31;
  const gridRows = 17;
  const cellSize = Math.min(width / 36, height / 25);
  const gap = cellSize * 0.22;
  const step = cellSize + gap;
  const startX = (width - gridColumns * step) / 2;
  const startY = height * 0.24;
  const seedX = width * 0.52;
  const seedY = height * 0.56;

  for (let row = 0; row < gridRows; row += 1) {
    const rowCurve = Math.abs(row - 8);
    const leftStart = 3 + Math.max(0, Math.floor((7 - row) / 2));
    const leftEnd = 14 - Math.max(0, Math.floor((row - 13) / 2));
    const rightStart = 16 + Math.max(0, Math.floor((row - 13) / 2));
    const rightEnd = 27 - Math.max(0, Math.floor((7 - row) / 2));

    for (let column = 0; column < gridColumns; column += 1) {
      const isLeftPage = column >= leftStart && column <= leftEnd;
      const isRightPage = column >= rightStart && column <= rightEnd;
      const isSpine = row > 11 && column >= 14 && column <= 16;

      if (!isLeftPage && !isRightPage && !isSpine) {
        continue;
      }

      const distance = Math.abs(column - 15) + Math.abs(row - 12);
      const jitter = seededNoise(column, row);
      const pageLean = (column < 15 ? -1 : 1) * rowCurve * cellSize * 0.035;
      const targetX = startX + column * step + pageLean;
      const targetY = startY + row * step + rowCurve * cellSize * 0.055;
      const isAccent = isRightPage && (jitter > 0.52 || column > 22 || row < 4);
      const color = isAccent ? '#0e6f68' : '#d8ccba';

      cells.push({
        x: targetX,
        y: targetY,
        size: cellSize * (0.76 + jitter * 0.18),
        delay: distance * 58 + jitter * 180,
        color,
        alpha: isAccent ? 0.9 : 0.46,
        seedX,
        seedY
      });
    }
  }

  const sparks = [
    [22, 1],
    [25, 0],
    [27, 3],
    [28, 6],
    [20, 2],
    [24, 5],
    [29, 8],
    [18, 0],
    [21, -1],
    [26, 8]
  ];

  sparks.forEach(([column, row], index) => {
    const jitter = seededNoise(column + 5, row + 9);
    cells.push({
      x: startX + column * step,
      y: startY + row * step,
      size: cellSize * (0.56 + jitter * 0.22),
      delay: 1300 + index * 120 + jitter * 260,
      color: index % 3 === 0 ? '#cfc2b1' : '#0e6f68',
      alpha: index % 3 === 0 ? 0.34 : 0.86,
      seedX,
      seedY
    });
  });

  return cells;
}

function drawFinalBook(state: CanvasState, now: number) {
  const { context, width, height, cells, start, reduced } = state;
  const cycle = 7200;
  const elapsed = reduced ? 3600 : (now - start) % cycle;
  const fadeStart = 6100;

  context.clearRect(0, 0, width, height);
  drawBookGhost(context, width, height);

  cells.forEach((cell) => {
    const build = reduced ? 1 : clamp((elapsed - cell.delay) / 760, 0, 1);
    const fade = reduced || elapsed < fadeStart ? 1 : 1 - clamp((elapsed - fadeStart) / 800, 0, 1);
    const eased = easeOutCubic(build);
    const x = cell.seedX + (cell.x - cell.seedX) * eased;
    const y = cell.seedY + (cell.y - cell.seedY) * eased;
    const scale = 0.28 + eased * 0.72;
    const pulse = reduced ? 1 : 0.94 + Math.sin((elapsed + cell.delay) / 520) * 0.06;
    const size = cell.size * scale * pulse;

    context.globalAlpha = cell.alpha * build * fade;
    context.fillStyle = cell.color;
    roundedSquare(context, x, y, size, Math.max(3, size * 0.22));
  });

  context.globalAlpha = reduced ? 0.6 : clamp((elapsed - 2400) / 900, 0, 0.62);
  drawBookCrease(context, width, height);
  context.globalAlpha = 1;
}

function drawBookGhost(context: CanvasRenderingContext2D, width: number, height: number) {
  const centerX = width * 0.5;
  const top = height * 0.3;
  const bottom = height * 0.72;
  const outerLeft = width * 0.17;
  const outerRight = width * 0.83;

  context.save();
  context.globalAlpha = 0.4;
  context.fillStyle = '#efe5d3';
  context.beginPath();
  context.moveTo(centerX, top + 20);
  context.bezierCurveTo(width * 0.38, top - 8, outerLeft, top + 18, outerLeft, top + 18);
  context.lineTo(outerLeft, bottom - 26);
  context.bezierCurveTo(width * 0.31, bottom - 18, width * 0.42, bottom + 8, centerX, bottom + 30);
  context.closePath();
  context.fill();

  context.beginPath();
  context.moveTo(centerX, top + 20);
  context.bezierCurveTo(width * 0.62, top - 8, outerRight, top + 18, outerRight, top + 18);
  context.lineTo(outerRight, bottom - 26);
  context.bezierCurveTo(width * 0.69, bottom - 18, width * 0.58, bottom + 8, centerX, bottom + 30);
  context.closePath();
  context.fill();
  context.restore();
}

function drawBookCrease(context: CanvasRenderingContext2D, width: number, height: number) {
  const centerX = width * 0.5;
  context.strokeStyle = '#c7bba9';
  context.lineWidth = 2;
  context.beginPath();
  context.moveTo(centerX, height * 0.32);
  context.bezierCurveTo(centerX - 4, height * 0.48, centerX + 5, height * 0.62, centerX, height * 0.8);
  context.stroke();
}

function roundedSquare(context: CanvasRenderingContext2D, x: number, y: number, size: number, radius: number) {
  const left = x - size / 2;
  const top = y - size / 2;
  context.beginPath();
  context.moveTo(left + radius, top);
  context.lineTo(left + size - radius, top);
  context.quadraticCurveTo(left + size, top, left + size, top + radius);
  context.lineTo(left + size, top + size - radius);
  context.quadraticCurveTo(left + size, top + size, left + size - radius, top + size);
  context.lineTo(left + radius, top + size);
  context.quadraticCurveTo(left, top + size, left, top + size - radius);
  context.lineTo(left, top + radius);
  context.quadraticCurveTo(left, top, left + radius, top);
  context.fill();
}

function seededNoise(x: number, y: number) {
  const value = Math.sin(x * 12.9898 + y * 78.233) * 43758.5453;
  return value - Math.floor(value);
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function easeOutCubic(value: number) {
  return 1 - Math.pow(1 - value, 3);
}

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
  gsap.set('[data-reveal], [data-hero-reel], [data-hero-artifact], [data-story-card], [data-shelf-fragment], [data-shelf-phone], [data-shelf-memory]', {
    autoAlpha: 1,
    clearProps: 'transform'
  });
}

function initEnhancedMotion() {
  document.documentElement.dataset.motion = 'enhanced';

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

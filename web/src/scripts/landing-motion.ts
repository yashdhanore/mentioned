document.documentElement.dataset.motion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  ? 'reduced'
  : 'static';

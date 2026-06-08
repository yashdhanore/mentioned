export type NavItem = {
  label: string;
  href: string;
};

export type BookArtifact = {
  title: string;
  author: string;
  tone: 'paper' | 'sage' | 'teal' | 'ink';
};

export type WorkflowChapter = {
  eyebrow: string;
  title: string;
  body: string;
};

export const navItems: NavItem[] = [
  { label: 'How it works', href: '#story' },
  { label: 'Saved with the Reel', href: '#shelf' },
  { label: 'Waitlist', href: '#waitlist' }
];

export const hero = {
  title: 'Turn BookTok into your reading list.',
  body: 'Send Mentioned a Reel or TikTok. We find the books and save them with the post that made you want to read them.',
  primaryCta: { label: 'See how it works', href: '#story' },
  secondaryCta: { label: 'See saved posts', href: '#shelf' }
};

export const heroBooks: BookArtifact[] = [
  { title: 'The Shallows', author: 'Nicholas Carr', tone: 'teal' },
  { title: 'Deep Work', author: 'Cal Newport', tone: 'sage' },
  { title: 'Atomic Habits', author: 'James Clear', tone: 'paper' }
];

export const workflowChapters: WorkflowChapter[] = [
  {
    eyebrow: 'It happens fast',
    title: 'How a Reel becomes a reading list.',
    body: 'Share the post once. Mentioned finds the books and keeps the recommendation attached.'
  },
  {
    eyebrow: 'Share',
    title: 'Send it to Mentioned.',
    body: 'Use the share sheet instead of taking another screenshot.'
  },
  {
    eyebrow: 'Find',
    title: 'Mentioned looks for books.',
    body: 'The video, caption, and comments are checked for titles and authors.'
  },
  {
    eyebrow: 'Save',
    title: 'Your list gets updated.',
    body: 'The books land in your reading list with the Reel attached.'
  },
  {
    eyebrow: 'Still useful',
    title: 'No clear title?',
    body: 'The post is still saved, so you can come back later.'
  }
];

export const shelfBooks: BookArtifact[] = [
  { title: 'The Shallows', author: 'Nicholas Carr', tone: 'teal' },
  { title: 'Deep Work', author: 'Cal Newport', tone: 'ink' },
  { title: 'Atomic Habits', author: 'James Clear', tone: 'paper' }
];

export const finalCta = {
  title: 'Never lose a book rec in the feed again.',
  body: 'Mentioned turns BookTok and Reels into a reading list you can actually come back to.',
  primaryCta: { label: 'Join waitlist', href: '#waitlist' },
  secondaryCta: { label: 'See how it works', href: '#story' }
};

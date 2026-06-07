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
  { label: 'For readers', href: '#reader-memory' }
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
    title: 'A book rec passes by once.',
    body: 'A title in a caption. A book held up for two seconds. A comment asking for the list.'
  },
  {
    eyebrow: 'Capture',
    title: 'Send the Reel. Keep the reason.',
    body: 'Mentioned saves the post, then looks for the books inside.'
  },
  {
    eyebrow: 'Processing',
    title: 'Finding books...',
    body: 'Mentioned is checking the post for titles and authors.'
  },
  {
    eyebrow: 'Result',
    title: 'Books found',
    body: 'The title, author when available, and the post stay together.'
  },
  {
    eyebrow: 'Recovery',
    title: 'The post is still saved.',
    body: 'No clear book? Keep the post anyway and come back later.'
  }
];

export const shelfBooks: BookArtifact[] = [
  { title: 'The Shallows', author: 'Nicholas Carr', tone: 'teal' },
  { title: 'Deep Work', author: 'Cal Newport', tone: 'ink' },
  { title: 'Atomic Habits', author: 'James Clear', tone: 'paper' }
];

export const readerMemory = {
  eyebrow: 'Saved with the Reel',
  title: 'The Reel stays with the book.',
  body: 'Mentioned keeps the recommendation with the post that made you want to read it.',
  quote: 'I used to screenshot every book rec. Now the book and the Reel stay together.'
};

export const finalCta = {
  title: 'Never lose a book rec in the feed again.',
  body: 'Mentioned turns BookTok and Reels into a reading list you can actually come back to.',
  primaryCta: { label: 'See how it works', href: '#story' },
  secondaryCta: { label: 'Saved with the Reel', href: '#shelf' }
};

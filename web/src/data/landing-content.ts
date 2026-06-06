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
  { label: 'Source memory', href: '#shelf' },
  { label: 'For readers', href: '#reader-memory' }
];

export const hero = {
  title: 'Save the books inside Reels.',
  body: 'Share a Reel, keep the source, find the books later.',
  primaryCta: { label: 'See how it works', href: '#story' },
  secondaryCta: { label: 'Follow the trail', href: '#shelf' }
};

export const heroBooks: BookArtifact[] = [
  { title: 'The Shallows', author: 'Nicholas Carr', tone: 'teal' },
  { title: 'Deep Work', author: 'Cal Newport', tone: 'sage' },
  { title: 'Atomic Habits', author: 'James Clear', tone: 'paper' }
];

export const workflowChapters: WorkflowChapter[] = [
  {
    eyebrow: 'It happens fast',
    title: 'A recommendation passes by once.',
    body: 'A title in a caption. A book held up for two seconds. A post you meant to come back to.'
  },
  {
    eyebrow: 'Capture',
    title: 'Share the source. Keep the trail.',
    body: 'Mentioned saves the post first, then looks for the books inside.'
  },
  {
    eyebrow: 'Processing',
    title: 'Finding books...',
    body: 'Mentioned is checking this post for book recommendations.'
  },
  {
    eyebrow: 'Result',
    title: 'Books mentioned',
    body: 'The title, author when available, and the original post stay together.'
  },
  {
    eyebrow: 'Recovery',
    title: 'The post is still saved.',
    body: 'No clear book? Open the original or try again.'
  }
];

export const shelfBooks: BookArtifact[] = [
  { title: 'The Shallows', author: 'Nicholas Carr', tone: 'teal' },
  { title: 'Deep Work', author: 'Cal Newport', tone: 'ink' },
  { title: 'Atomic Habits', author: 'James Clear', tone: 'paper' }
];

export const readerMemory = {
  eyebrow: 'Reader memory',
  title: 'The source stays attached to the book.',
  body: 'Mentioned keeps the post, the recommendation, and the path back to where you found it.',
  quote: 'I used to screenshot everything. Now the post and the book stay together.'
};

export const finalCta = {
  title: 'Never lose the book recommendation again.',
  body: 'Mentioned keeps the post, the books, and the path back to where you found them.',
  primaryCta: { label: 'See how it works', href: '#story' },
  secondaryCta: { label: 'Source memory', href: '#shelf' }
};

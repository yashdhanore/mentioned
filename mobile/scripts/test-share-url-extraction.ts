import assert from 'node:assert/strict';

import {
  extractSharedSourceUrl,
  isSupportedSharedSourceUrl,
  parseMentionedShareDeepLink,
  sharedUrlFromMentionedDeepLink,
} from '../src/utils/shared-source-url';

const reelUrl = 'https://www.instagram.com/reel/ABC123/';
const postUrl = 'https://instagram.com/p/POST123/?utm_source=ig_web_copy_link';

assert.equal(isSupportedSharedSourceUrl(reelUrl), true);
assert.equal(isSupportedSharedSourceUrl(postUrl), true);
assert.equal(isSupportedSharedSourceUrl('http://www.instagram.com/reel/ABC123/'), false);
assert.equal(isSupportedSharedSourceUrl('https://example.com/reel/ABC123/'), false);
assert.equal(isSupportedSharedSourceUrl('https://www.instagram.com/stories/account/123/'), false);

assert.equal(
  extractSharedSourceUrl({ url: reelUrl, text: undefined }),
  'https://www.instagram.com/reel/ABC123/',
);

assert.equal(
  extractSharedSourceUrl({ url: reelUrl, text: `Different source here: ${postUrl}` }),
  'https://www.instagram.com/reel/ABC123/',
);

assert.equal(
  extractSharedSourceUrl({ text: `Books from here: ${postUrl}` }),
  'https://instagram.com/p/POST123/',
);

assert.equal(
  extractSharedSourceUrl({ text: 'No supported source here https://example.com/reel/ABC123/' }),
  null,
);

assert.equal(
  extractSharedSourceUrl({ text: 'Bracketed source [https://www.instagram.com/reel/BRACKET/]' }),
  'https://www.instagram.com/reel/BRACKET/',
);

assert.equal(
  sharedUrlFromMentionedDeepLink(
    `mentioned://share?url=${encodeURIComponent('https://www.instagram.com/reel/DEEPLINK/')}`,
  ),
  'https://www.instagram.com/reel/DEEPLINK/',
);

assert.equal(
  sharedUrlFromMentionedDeepLink(
    `mentioned:///share?url=${encodeURIComponent('https://www.instagram.com/reel/BRIDGE/')}`,
  ),
  'https://www.instagram.com/reel/BRIDGE/',
);

assert.equal(sharedUrlFromMentionedDeepLink('mentioned://auth/callback?code=abc'), null);
assert.deepEqual(parseMentionedShareDeepLink('mentioned://auth/callback?code=abc'), {
  type: 'non-share-link',
});
assert.equal(
  sharedUrlFromMentionedDeepLink(
    `mentioned://share/extra?url=${encodeURIComponent('https://www.instagram.com/reel/DEEPLINK/')}`,
  ),
  null,
);
assert.equal(
  sharedUrlFromMentionedDeepLink(
    `mentioned:///share/extra?url=${encodeURIComponent('https://www.instagram.com/reel/DEEPLINK/')}`,
  ),
  null,
);
assert.equal(sharedUrlFromMentionedDeepLink('mentioned://share?url=https%3A%2F%2Fexample.com'), null);
assert.deepEqual(parseMentionedShareDeepLink('mentioned://share?url=https%3A%2F%2Fexample.com'), {
  type: 'invalid-share-link',
});

assert.equal(
  sharedUrlFromMentionedDeepLink('mentioned://share?url=https%3A%2F%2Fwww.instagram.com%2Fp%2FHOSTAPP%2F'),
  'https://www.instagram.com/p/HOSTAPP/',
);

assert.equal(sharedUrlFromMentionedDeepLink('mentioned://share'), null);
assert.equal(sharedUrlFromMentionedDeepLink('mentioned://share?url='), null);
assert.deepEqual(parseMentionedShareDeepLink('mentioned://share'), { type: 'invalid-share-link' });
assert.deepEqual(parseMentionedShareDeepLink('mentioned://share?url='), { type: 'invalid-share-link' });
assert.deepEqual(parseMentionedShareDeepLink('mentioned://share?url=%'), { type: 'invalid-share-link' });

assert.deepEqual(
  parseMentionedShareDeepLink(
    `mentioned://share?url=${encodeURIComponent(
      'https://www.instagram.com/reel/PARAMS/?ref=feed&utm_source=ig_web_copy_link&tracking=kept&igsh=removed',
    )}`,
  ),
  {
    type: 'valid',
    sourceUrl: 'https://www.instagram.com/reel/PARAMS/?ref=feed&tracking=kept',
  },
);

console.log('share URL extraction tests passed');

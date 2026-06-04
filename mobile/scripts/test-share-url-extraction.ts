import assert from 'node:assert/strict';

import {
  canonicalSharedSourceKey,
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
assert.equal(isSupportedSharedSourceUrl('https://www.instagram.com/account/reel/ABC123/'), false);

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
  extractSharedSourceUrl({
    url: 'https://www.instagram.com/reel/SECRET/?utm_source=x&igsh=abc&access_token=secret&code=oauth&state=oauth#frag',
  }),
  'https://www.instagram.com/reel/SECRET/',
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
    `mentioned://share?url=${encodeURIComponent(
      'https://www.instagram.com/p/PARAMS/?ref=feed&tracking=kept&fbclid=abc&token=secret',
    )}`,
  ),
  'https://www.instagram.com/p/PARAMS/',
);

assert.equal(
  sharedUrlFromMentionedDeepLink(
    `mentioned:///share?url=${encodeURIComponent('https://www.instagram.com/reel/BRIDGE/')}`,
  ),
  'https://www.instagram.com/reel/BRIDGE/',
);

assert.equal(
  sharedUrlFromMentionedDeepLink(
    `mentioned://expo-development-client/?url=${encodeURIComponent(
      `mentioned://share?url=${encodeURIComponent('https://www.instagram.com/reel/WRAPPED/')}`,
    )}`,
  ),
  'https://www.instagram.com/reel/WRAPPED/',
);

assert.equal(
  sharedUrlFromMentionedDeepLink(
    `com.yashd18.mentioned://expo-development-client/?url=${encodeURIComponent(
      `mentioned://share?url=${encodeURIComponent('https://www.instagram.com/reel/DEVCLIENT/')}`,
    )}`,
  ),
  'https://www.instagram.com/reel/DEVCLIENT/',
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

assert.equal(
  sharedUrlFromMentionedDeepLink('mentioned:///share?url=https%253A%252F%252Fwww.instagram.com%252Freel%252FSAFARI%252F'),
  'https://www.instagram.com/reel/SAFARI/',
);

assert.equal(
  sharedUrlFromMentionedDeepLink('mentioned:///share?url=https://www.instagram.com/reel/RAW/'),
  'https://www.instagram.com/reel/RAW/',
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
    sourceUrl: 'https://www.instagram.com/reel/PARAMS/',
  },
);

assert.equal(
  canonicalSharedSourceKey('https://www.instagram.com/reel/DUP/?utm_source=one&token=secret'),
  'https://www.instagram.com/reel/DUP/',
);

assert.equal(
  canonicalSharedSourceKey('https://www.instagram.com/reel/DUP/?utm_source=two'),
  canonicalSharedSourceKey('https://www.instagram.com/reel/DUP/'),
);

assert.equal(canonicalSharedSourceKey('https://example.com/reel/DUP/'), null);

console.log('share URL extraction tests passed');

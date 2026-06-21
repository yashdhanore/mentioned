import assert from 'node:assert/strict';

import {
  buildCapturesFromSavedSources,
  captureFromSavedSource,
  captureFromSavedSourceCreated,
} from '../src/captures';
import type { SavedSourceResponse } from '../src/api';

const savedSource: SavedSourceResponse = {
  id: '11111111-1111-4111-8111-111111111111',
  source_id: '99999999-9999-4999-8999-999999999999',
  source_key: 'instagram:reel:DONE',
  status: 'done',
  source_url: 'https://www.instagram.com/reel/DONE/',
  thumbnail_url: 'https://example.com/thumb.jpg',
  source_creator_handle: 'reader',
  error_message: null,
  created_at: '2026-06-06T15:49:00Z',
  items: [],
};

const createdCapture = captureFromSavedSourceCreated({
  ...savedSource,
  id: '22222222-2222-4222-8222-222222222222',
  status: 'processing',
  thumbnail_url: null,
});
assert.equal(createdCapture.status, 'processing');
assert.equal(createdCapture.thumbnailUrl, null);
assert.equal(createdCapture.sourceUrl, savedSource.source_url);

const processingCapture = captureFromSavedSource({
  ...savedSource,
  id: '33333333-3333-4333-8333-333333333333',
  status: 'processing',
});
assert.equal(processingCapture.status, 'processing');

const failedCapture = captureFromSavedSource({
  ...savedSource,
  id: '44444444-4444-4444-8444-444444444444',
  status: 'failed',
});
assert.equal(failedCapture.status, 'failed');

const failedCreatedCapture = captureFromSavedSourceCreated({
  ...savedSource,
  id: '99999999-9999-4999-8999-999999999990',
  status: 'failed',
  error_message: 'Could not process this Reel.',
});
assert.equal(failedCreatedCapture.status, 'failed');
assert.equal(failedCreatedCapture.errorMessage, 'Could not process this Reel.');

assert.deepEqual(
  buildCapturesFromSavedSources([savedSource]).map((capture) => capture.id),
  [savedSource.id],
);

assert.equal(captureFromSavedSource(savedSource).status, 'no_books');

const detailedBookCapture = captureFromSavedSource({
  ...savedSource,
  items: [
    {
      id: '55555555-5555-4555-8555-555555555555',
      book_id: '66666666-6666-4666-8666-666666666666',
      title: 'Ignored Product',
      author: null,
      category: 'product',
      confidence: 0.99,
      google_books_url: null,
      cover_image_url: null,
      position: 0,
    },
    {
      id: '77777777-7777-4777-8777-777777777777',
      book_id: '88888888-8888-4888-8888-888888888888',
      title: 'The Left Hand of Darkness',
      author: 'Ursula K. Le Guin',
      category: 'book',
      confidence: 0.99,
      google_books_url: null,
      cover_image_url: 'https://example.com/cover.jpg',
      position: 2,
    },
    {
      id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
      book_id: 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
      title: 'A Wizard of Earthsea',
      author: 'Ursula K. Le Guin',
      category: 'book',
      confidence: 0.88,
      google_books_url: null,
      cover_image_url: null,
      position: 1,
    },
  ],
});
assert.equal(detailedBookCapture.status, 'ready');
assert.deepEqual(
  detailedBookCapture.books.map((book) => book.title),
  ['A Wizard of Earthsea', 'The Left Hand of Darkness'],
);
assert.equal(detailedBookCapture.books[1].coverImageUrl, 'https://example.com/cover.jpg');

console.log('capture mapping tests passed');

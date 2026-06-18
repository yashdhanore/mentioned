import assert from 'node:assert/strict';

import {
  buildCapturesFromJobList,
  captureFromJobDetail,
  captureFromJobListItem,
} from '../src/captures';
import type { JobListItem, JobResponse } from '../src/api';

const listedDoneJob: JobListItem = {
  job_id: '11111111-1111-4111-8111-111111111111',
  status: 'done',
  source_url: 'https://www.instagram.com/reel/DONE/',
  thumbnail_url: 'https://example.com/thumb.jpg',
  source_creator_handle: 'reader',
  created_at: '2026-06-06T15:49:00Z',
};

const listedDoneCapture = captureFromJobListItem(listedDoneJob);
assert.equal(listedDoneCapture.status, 'ready');
assert.equal(listedDoneCapture.creatorHandle, 'reader');
assert.equal(listedDoneCapture.thumbnailUrl, 'https://example.com/thumb.jpg');
assert.equal(listedDoneCapture.sourceUrl, listedDoneJob.source_url);
assert.equal(listedDoneCapture.createdAt, listedDoneJob.created_at);
assert.deepEqual(listedDoneCapture.books, []);
assert.equal(listedDoneCapture.errorMessage, null);

const listedPendingCapture = captureFromJobListItem({
  ...listedDoneJob,
  job_id: '22222222-2222-4222-8222-222222222222',
  status: 'pending',
  thumbnail_url: null,
});
assert.equal(listedPendingCapture.status, 'processing');
assert.equal(listedPendingCapture.thumbnailUrl, null);

const listedFailedCapture = captureFromJobListItem({
  ...listedDoneJob,
  job_id: '33333333-3333-4333-8333-333333333333',
  status: 'failed',
});
assert.equal(listedFailedCapture.status, 'failed');

assert.deepEqual(
  buildCapturesFromJobList([listedDoneJob]).map((capture) => capture.id),
  [listedDoneJob.job_id],
);

const detailedNoBooksJob: JobResponse = {
  ...listedDoneJob,
  error_message: null,
  finished_at: '2026-06-06T15:50:00Z',
  mentions: [],
};
assert.equal(captureFromJobDetail(detailedNoBooksJob).status, 'no_books');

const detailedBookJob: JobResponse = {
  ...detailedNoBooksJob,
  mentions: [
    {
      id: '44444444-4444-4444-8444-444444444444',
      book_id: '55555555-5555-4555-8555-555555555555',
      title: 'The Left Hand of Darkness',
      author: 'Ursula K. Le Guin',
      category: 'book',
      confidence: 0.99,
      google_books_url: null,
      cover_image_url: 'https://example.com/cover.jpg',
    },
  ],
};
const detailedBookCapture = captureFromJobDetail(detailedBookJob);
assert.equal(detailedBookCapture.status, 'ready');
assert.deepEqual(
  detailedBookCapture.books.map((book) => book.title),
  ['The Left Hand of Darkness'],
);
assert.equal(detailedBookCapture.books[0].coverImageUrl, 'https://example.com/cover.jpg');

console.log('capture mapping tests passed');

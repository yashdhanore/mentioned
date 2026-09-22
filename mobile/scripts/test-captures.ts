import assert from 'node:assert/strict';

import {
  captureFromSavedSource,
  mapsUrlForMention,
  mergeSavedSourcesWithCaptures,
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
  skip_reason: null,
  created_at: '2026-06-06T15:49:00Z',
  items: [],
};

const createdCapture = captureFromSavedSource({
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

const failedCreatedCapture = captureFromSavedSource({
  ...savedSource,
  id: '99999999-9999-4999-8999-999999999990',
  status: 'failed',
  error_message: 'Could not process this Reel.',
});
assert.equal(failedCreatedCapture.status, 'failed');
assert.equal(failedCreatedCapture.errorMessage, 'Could not process this Reel.');

assert.deepEqual(
  mergeSavedSourcesWithCaptures([savedSource], []).map((capture) => capture.id),
  [savedSource.id],
);

const noMentionsCapture = captureFromSavedSource(savedSource);
assert.equal(noMentionsCapture.status, 'no_mentions');
assert.equal(noMentionsCapture.skipReason, null);

const skippedCapture = captureFromSavedSource({
  ...savedSource,
  skip_reason: 'dance clip',
});
assert.equal(skippedCapture.status, 'no_mentions');
assert.equal(skippedCapture.skipReason, 'dance clip');

const mixedCapture = captureFromSavedSource({
  ...savedSource,
  items: [
    {
      id: '55555555-5555-4555-8555-555555555555',
      book_id: null,
      title: 'Cafe Nero',
      author: null,
      category: 'place',
      confidence: 0.7,
      google_books_url: null,
      cover_image_url: null,
      place_id: 'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
      formatted_address: '12 King St, London, UK',
      latitude: 51.5072,
      longitude: -0.1276,
      maps_url: 'https://www.google.com/maps/place/?q=place_id:ChIJ-place-1',
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
      place_id: null,
      formatted_address: null,
      latitude: null,
      longitude: null,
      maps_url: null,
      position: 2,
    },
    {
      id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
      book_id: null,
      title: 'Low Confidence Place',
      author: null,
      category: 'place',
      confidence: 0.5,
      google_books_url: null,
      cover_image_url: null,
      place_id: null,
      formatted_address: null,
      latitude: null,
      longitude: null,
      maps_url: null,
      position: 1,
    },
  ],
});
// Place at 0.7 surfaces; book surfaces; place at 0.5 hidden by the 0.6 floor.
assert.equal(mixedCapture.status, 'ready');
assert.deepEqual(
  mixedCapture.mentions.map((mention) => mention.title),
  ['Cafe Nero', 'The Left Hand of Darkness'],
);
assert.deepEqual(
  mixedCapture.mentions.map((mention) => mention.category),
  ['place', 'book'],
);
// subtitle: formatted_address for enriched places, author for books.
assert.equal(mixedCapture.mentions[0].subtitle, '12 King St, London, UK');
assert.equal(mixedCapture.mentions[1].subtitle, 'Ursula K. Le Guin');
assert.equal(mixedCapture.mentions[1].coverImageUrl, 'https://example.com/cover.jpg');
// Enriched place carries coords for the Maps deep-link; book does not.
assert.equal(mixedCapture.mentions[0].formattedAddress, '12 King St, London, UK');
assert.equal(mixedCapture.mentions[0].latitude, 51.5072);
assert.equal(mixedCapture.mentions[0].longitude, -0.1276);
assert.equal(
  mixedCapture.mentions[0].mapsUrl,
  'https://www.google.com/maps/place/?q=place_id:ChIJ-place-1',
);
assert.equal(mixedCapture.mentions[1].latitude, null);
assert.equal(mixedCapture.mentions[1].mapsUrl, null);

// A bare (unmatched) place still renders with no address subtitle.
const barePlaceCapture = captureFromSavedSource({
  ...savedSource,
  items: [
    {
      id: 'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',
      book_id: null,
      title: 'Some Unmatched Cafe',
      author: null,
      category: 'place',
      confidence: 0.8,
      google_books_url: null,
      cover_image_url: null,
      place_id: null,
      formatted_address: null,
      latitude: null,
      longitude: null,
      maps_url: null,
      position: 0,
    },
  ],
});
assert.equal(barePlaceCapture.status, 'ready');
assert.equal(barePlaceCapture.mentions[0].title, 'Some Unmatched Cafe');
assert.equal(barePlaceCapture.mentions[0].subtitle, null);
assert.equal(barePlaceCapture.mentions[0].latitude, null);

const productCapture = captureFromSavedSource({
  ...savedSource,
  items: [
    {
      id: 'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
      book_id: null,
      title: 'Oura Ring',
      author: null,
      category: 'product',
      confidence: 0.9,
      google_books_url: null,
      cover_image_url: null,
      place_id: null,
      formatted_address: null,
      latitude: null,
      longitude: null,
      maps_url: null,
      position: 0,
    },
  ],
});
assert.equal(productCapture.status, 'ready');
assert.equal(productCapture.mentions[0].category, 'product');

// Deep-link: prefer the canonical maps_url for an enriched place.
assert.equal(
  mapsUrlForMention(mixedCapture.mentions[0]),
  'https://www.google.com/maps/place/?q=place_id:ChIJ-place-1',
);
// Books never deep-link to Maps.
assert.equal(mapsUrlForMention(mixedCapture.mentions[1]), null);
// A bare place with no maps_url and no coords is not tappable.
assert.equal(mapsUrlForMention(barePlaceCapture.mentions[0]), null);
// Coords-only place (no maps_url) falls back to a lat/lng search link.
const coordsOnlyPlace = captureFromSavedSource({
  ...savedSource,
  items: [
    {
      id: 'ffffffff-ffff-4fff-8fff-ffffffffffff',
      book_id: null,
      title: 'Coords Only Cafe',
      author: null,
      category: 'place',
      confidence: 0.8,
      google_books_url: null,
      cover_image_url: null,
      place_id: 'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
      formatted_address: '1 Some Rd',
      latitude: 40.0,
      longitude: -73.0,
      maps_url: null,
      position: 0,
    },
  ],
});
assert.equal(
  mapsUrlForMention(coordsOnlyPlace.mentions[0]),
  'https://www.google.com/maps/search/?api=1&query=40,-73',
);

console.log('capture mapping tests passed');

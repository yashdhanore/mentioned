# Mentioned Product Context

Mentioned helps people turn saved social content into structured recommendations and memories they can find and use later.

## Language

**Recommendation collector**:
A person who saves social content because it contains books, places, recipes, restaurants, products, posts, or ideas they may want later.
_Avoid_: Everything saver, casual user

**Book-first wedge**:
The first focused category for Mentioned, aimed at recommendation collectors who save book recommendation content.
_Avoid_: Books-only product

**Published proof**:
The immediate milestone: an installable store-distributed app that demonstrates the native capture core loop, has enough polish to show, and hints at the larger collections and semantic memory vision.
_Avoid_: Full beta product, scale-ready launch

**Vision surface**:
Where Mentioned explains future capabilities. The app uses subtle hints, while the website can show upcoming features, roadmap framing, and waitlist interest.
_Avoid_: Disabled in-app feature screens, misleading in-app promises

**Useful but imperfect extraction**:
The acceptable quality bar for the published proof: many public book recommendation sources should produce useful book results, while misses, mistakes, and failures remain understandable and recoverable.
_Avoid_: Demo-only extraction, near-production extraction

**Basic correction**:
The correction level for the published proof: users can remove incorrect extracted items, retry failed sources, make simple manual edits, or mark a result as wrong without entering a full metadata-management workflow.
_Avoid_: Full catalog editing, silent failure

**Useful collection**:
A user-facing group of saved items that can be revisited, searched, or turned into an output such as a reading list or itinerary.
_Avoid_: Folder, saved pile

**Extracted item**:
A candidate item Mentioned found inside a saved source, such as a book, place, recipe, product, post, or meme reference.
_Avoid_: Final recommendation, user choice

**User-curated collection**:
A list the user intentionally creates by choosing extracted items from one or more saved sources.
_Avoid_: Automatic category bucket, AI-generated output

**Source history**:
The record of a saved source and all extracted items found in it, including items the user has not added to a user-curated collection.
_Avoid_: Discarded items, hidden trash

**Saved source home**:
The immediate app home model for the published proof: users browse saved sources first, then open a source to inspect extracted items.
_Avoid_: Books-first library, collection-first home, activity feed

**Native capture**:
The preferred way to save a source into Mentioned from another app's share sheet. For the published proof, native capture is higher priority than adding new product features.
_Avoid_: Paste-only capture, manual-first capture

**iOS-first published proof**:
The selected platform sequence for the published proof: ship iOS with native share-sheet capture first, then bring Android/Play Store support afterward.
_Avoid_: Android-first launch, simultaneous platform launch

**Release 1 exclusions**:
Capabilities intentionally left out of the iOS-first published proof: semantic search, user-curated collections, non-book categories, Android release, advanced editing, and major scale or cost optimization.
_Avoid_: Scope creep, hidden launch requirements

**Trustworthy small app**:
The quality bar for initial publication: the app looks intentional, handles loading and failure states, has privacy/auth basics, and does not feel broken.
_Avoid_: Bare proof, portfolio-quality launch

**Consumer-polished app**:
The post-publication quality bar before serious promotion: the app should feel polished enough to share, market, and use as a portfolio-quality product.
_Avoid_: Permanent beta polish, hidden prototype

**Promotion-ready semantic search**:
The first major post-publication product direction. It should start with source recall, then expand into item lookup, vague memory search, and mixed item/source results.
_Avoid_: Collections-first promotion, search-only prototype

**Source detail**:
The app screen for one saved source. For the published proof, it should prioritize extracted books first, with source context and source-opening actions secondary.
_Avoid_: Evidence-first detail, source-preview-first detail

**Semantic memory layer**:
The long-term product direction: a way to recall saved online content by meaning, description, or context rather than exact titles or platform search terms.
_Avoid_: AI extractor, smarter folder

**Semantic search**:
A future retrieval capability that searches both extracted items and source history, so users can find either a saved item or the source where it appeared.
_Avoid_: Collection-only search, source-only search

## Example Dialogue

Product: "Who are we building the first version for?"

Domain expert: "Recommendation collectors broadly, but the book-first wedge lets us start with people saving book recommendation content."

Product: "So Mentioned is a books-only app?"

Domain expert: "No. Books are the first category. The promise is saving social recommendations into useful collections, with a longer-term path toward a semantic memory layer."

Product: "Does every extracted book automatically become part of a reading list?"

Domain expert: "No. Extracted items stay attached to their saved source, but a user-curated collection contains only the items the user intentionally chooses."

Product: "What happens to books the user does not add to a collection?"

Domain expert: "They remain in source history and can still be found later, but they are visually secondary to the user's curated collections."

Product: "When semantic search arrives, what should it search first?"

Domain expert: "Both extracted items and source history, but semantic search is not part of the immediate publishing milestone."

Product: "What should the published version prove?"

Domain expert: "It should prove the native capture core loop, store installability, and the larger product vision without needing collections or semantic search yet."

Product: "How good does extraction need to be for the published proof?"

Domain expert: "Useful but imperfect. It should work on many public book recommendation sources, but occasional misses or wrong items are acceptable if the app handles them clearly."

Product: "What should happen when extraction is wrong or incomplete?"

Domain expert: "Users should have basic correction: remove wrong items, retry failed sources, make simple manual edits, or mark a result as wrong."

Product: "How should the current app present the bigger vision?"

Domain expert: "The app should use subtle product hints without disabled features. The website can carry upcoming features, roadmap framing, and waitlist collection."

Product: "What should the published proof home screen organize around?"

Domain expert: "Saved sources. Users should browse saved Reels or posts first, then open one to inspect extracted books."

Product: "Is paste-link capture enough for the published proof?"

Domain expert: "No. Paste link already works, but native capture from the share sheet is the highest-priority goal before publishing."

Product: "Which platform should publish first?"

Domain expert: "iOS first, because there is no existing developer account and iOS appears to be the faster path to an installable published proof. Android follows later."

Product: "What does polished enough to publish mean?"

Domain expert: "The initial release should be a trustworthy small app. Soon after publication, the product should be raised to consumer-polished, portfolio-quality standard before serious promotion."

Product: "What is the first promotion-ready feature after publication?"

Domain expert: "Semantic search. After the iOS-first published proof, the next product jump should make the app consumer-polished and let users find saved items or sources by natural-language memory."

Product: "What semantic search use case comes first?"

Domain expert: "Source recall. Users should first be able to ask for the Reel, post, or source where they remember seeing something. Item lookup and vague memory search can follow in later releases."

Product: "What should Release 1 exclude?"

Domain expert: "Release 1 excludes semantic search, collections, non-book categories, Android, advanced editing, and major scale or cost optimization."

Product: "What matters most on a saved source detail screen?"

Domain expert: "Extracted books first. Source context and source-opening actions are useful, but secondary."

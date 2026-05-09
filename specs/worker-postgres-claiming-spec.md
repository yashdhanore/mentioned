# Worker Postgres Claiming Specification

Status: Interview draft

Last updated: 2026-05-02

Purpose: Define the proof required before the worker claim path can be considered safe for concurrent
production workers on Postgres. This file lives under `specs/` with the other task-specific backend specifications.

## Current Implementation Facts

- `JobCoordinator.claim_next_job()` has a Postgres-specific branch in
  `app/services/job_coordinator.py`.
- The Postgres branch claims with a single `UPDATE ... WHERE id = (SELECT ... FOR UPDATE SKIP
  LOCKED) RETURNING id` statement.
- The SQLite branch remains a simple select-then-update fallback and cannot prove production
  concurrent worker safety.
- Existing pytest coverage in `tests/test_job_coordinator.py` uses SQLite only.
- Existing SQLite tests prove sequential behavior such as "worker B sees no job after worker A
  claimed it", but they do not prove Postgres row-lock behavior.
- `worker/run.py` opens a short session for claim, closes it, then runs extraction outside the claim
  transaction. This matches the intended production shape.
- `psycopg[binary]` is already a project dependency.
- No committed test fixture or smoke script currently starts or targets a real Postgres database for
  worker-claim concurrency.

## Decision Log

1. Worker-claim safety MUST be proven against real Postgres.
   - SQLite, SQL string assertions, and mocked sessions are insufficient.
   - The proof must exercise the actual `JobCoordinator.claim_next_job()` Postgres branch.
2. The primary acceptance test SHOULD be a deterministic `SKIP LOCKED` integration test.
   - Hold a row lock on the highest-priority queued job in one Postgres transaction.
   - From another session, call `claim_next_job()`.
   - The claim must return the next eligible queued job quickly instead of blocking or claiming the
     locked job.
3. A concurrent worker smoke test MAY be added as additional confidence.
   - It should start multiple claimers at the same time and assert that every returned job id is
     unique.
   - It is useful, but it is less deterministic than the lock-holding `SKIP LOCKED` test.
4. The test MUST use an isolated Postgres database or schema.
   - It must not target development, staging, or production data.
   - It must create and drop its own schema or run against a disposable database.
5. The pytest integration test MAY be opt-in locally, but MUST run in CI before this claim is called
   proven.
   - Recommended local gate: `POSTGRES_TEST_DATABASE_URL`.
   - If the URL is absent, the test may skip with an explicit message.
   - CI must provide that URL or run a disposable Postgres service.
6. The production claim transaction MUST remain short.
   - Claiming must commit before extraction begins.
   - The test must not encourage holding worker transactions during extraction.
7. The worker claim proof MUST verify persisted side effects, not only return values.
   - Claimed rows must be `status='running'`.
   - `locked_by`, `locked_at`, `heartbeat_at`, `attempt_count`, `current_stage`, `progress`, and
     `updated_at` must reflect a claim.
   - Unclaimed eligible rows must remain `queued`.
8. Completion requires documentation of the exact command used to run the Postgres proof.
   - The README or test docstring should show the required environment variable and pytest selector.

## Decision 1: What Counts As Proof?

Question: Is it enough that the code contains `FOR UPDATE SKIP LOCKED`?

Recommended answer: no. The claim must be proven by running the actual coordinator method against
real Postgres. SQL text inspection can catch accidental removal, but it cannot prove lock behavior,
transaction timing, isolation interaction, or duplicate-claim absence.

Decision: require a real Postgres test or a verified concurrent worker smoke. Prefer the deterministic
Postgres `SKIP LOCKED` test as the merge-blocking proof.

## Decision 2: Deterministic Test Or Concurrent Smoke?

Question: Should the first proof be a deterministic lock test or a many-worker race smoke?

Recommended answer: deterministic lock test first.

Decision: add `tests/test_postgres_worker_claiming.py` with a test that explicitly locks the first
eligible queued job in one transaction, then calls `JobCoordinator.claim_next_job("worker-b")` from
a second session. The second session must claim the second eligible job without waiting for the first
transaction to release its lock.

Rationale: a many-thread smoke can pass by luck if claims happen one after another. A held-lock test
forces the exact condition `SKIP LOCKED` exists to handle.

## Decision 3: Should The Test Exercise Raw SQL Or The Coordinator?

Question: Should the test run a hand-written SQL snippet, or call `JobCoordinator.claim_next_job()`?

Recommended answer: call the coordinator.

Decision: the test must call the production method. Raw SQL may be used only to set up the blocking
transaction and inspect rows afterward.

Rationale: the risk is not abstract Postgres semantics. The risk is whether this code path, session
handling, SQLAlchemy dialect detection, and commit behavior are correct.

## Decision 4: How Should Test Data Be Created?

Question: Should the test create rows through `create_job()` or insert directly?

Recommended answer: create jobs through `JobCoordinator.create_job()` unless a specific field cannot
be reached that way.

Decision: seed at least two eligible queued jobs through coordinator APIs, then optionally update
priority/created ordering directly if deterministic ordering needs tightening.

Rationale: creating jobs through the coordinator keeps the test aligned with real persisted shape,
including owner ids, normalized URLs, default status, attempts, and timestamps.

## Decision 5: How Many Jobs And Workers Are Required?

Question: What is the minimum deterministic fixture?

Recommended answer: two queued jobs and two independent sessions.

Decision: use two eligible jobs for the lock-holding test:

- Job A has the highest claim ordering and is locked by setup transaction.
- Job B is the next eligible job.
- Worker B must claim Job B while Job A remains locked.
- After the setup transaction rolls back, Job A must still be queued and claimable by Worker A.

Optional smoke coverage may seed more jobs than workers, start 8 to 16 worker threads with separate
sessions, and assert unique claimed job ids.

## Decision 6: How Should Blocking Be Detected?

Question: How does the test avoid hanging if `SKIP LOCKED` is broken?

Recommended answer: set a short Postgres `statement_timeout` for the claiming session.

Decision: the claim session should set `statement_timeout` locally, for example 1000 to 2000 ms. If
the claim blocks behind the held lock, the test should fail quickly.

Rationale: a broken lock strategy should produce a crisp test failure, not a hung CI job.

## Decision 7: What Must Be Asserted?

Question: Which assertions make the proof meaningful?

Recommended answer: assert both absence of duplicate claims and correct persisted state.

Decision: the deterministic test must assert:

- Worker B receives Job B, not Job A.
- Job B is persisted as `running`.
- Job B has `locked_by='worker-b'`.
- Job B has `attempt_count=1`.
- Job B has `current_stage='claimed'`.
- Job B has non-null `locked_at` and `heartbeat_at`.
- Job A remains `queued` while the setup transaction is open.
- After releasing the setup lock, Worker A can claim Job A.
- No job id appears in two claim results.

## Decision 8: Where Should The Test Live?

Question: Should this be in the existing SQLite coordinator test file?

Recommended answer: no.

Decision: create a dedicated file such as `tests/test_postgres_worker_claiming.py`.

Rationale: this test has different infrastructure, skip behavior, setup, and failure modes than the
fast SQLite unit tests. Keeping it separate makes local and CI selection clearer.

## Decision 9: How Should Local And CI Execution Work?

Question: Should the test automatically start Postgres, or require a database URL?

Recommended answer: require `POSTGRES_TEST_DATABASE_URL` for the first implementation, then add a
container helper only if local friction becomes significant.

Decision: implement the pytest file so it skips when `POSTGRES_TEST_DATABASE_URL` is absent. CI must
provide a disposable Postgres service and set that URL.

Rationale: the project has `psycopg` but no Docker/testcontainers dependency yet. Avoid adding new
infrastructure until the test shape is proven.

## Decision 10: Should The Worker Process Itself Be Spawned?

Question: Does proof require launching multiple `mentioned-worker` processes?

Recommended answer: not for the first merge-blocking proof.

Decision: the deterministic pytest should exercise `claim_next_job()` directly. A separate smoke may
launch worker processes later, but it should not be the only proof because pipeline execution adds
external tool and network noise.

Rationale: the invariant under review is claim exclusivity. Direct coordinator tests isolate that
behavior from extraction quality, ffmpeg, yt-dlp, OCR, OpenAI, and network dependencies.

## Required Test Shape

The core test should follow this structure:

```text
given a disposable Postgres schema
and two eligible queued jobs ordered A before B
and transaction T1 holds `select id from jobs where id = A for update`
when transaction T2 calls `JobCoordinator.claim_next_job("worker-b")`
then T2 returns B quickly
and B is running and locked by worker-b
and A remains queued while T1 is open
when T1 rolls back
then worker-a can claim A
and no claimed job id is duplicated
```

## Implementation Scope

The implementation SHOULD add:

- `tests/test_postgres_worker_claiming.py`
- A Postgres test engine fixture using `POSTGRES_TEST_DATABASE_URL`
- Disposable schema setup and teardown
- A deterministic held-lock `SKIP LOCKED` test
- Optional concurrent claim smoke in the same file or a later script
- README documentation for running the Postgres claim proof locally

The implementation SHOULD NOT:

- Replace the existing SQLite coordinator tests.
- Depend on production or shared development data.
- Mock `claim_next_job()`.
- Treat SQL text inspection as sufficient proof.
- Hold database transactions while extraction runs.

## Completion Criteria

This work is complete when:

- The new Postgres test fails if `FOR UPDATE SKIP LOCKED` is removed or replaced with a blocking
  claim strategy.
- The test calls the actual `JobCoordinator.claim_next_job()` method.
- The test proves two workers cannot receive the same job id.
- The test proves a locked first job is skipped and remains queued until its lock is released.
- The test verifies persisted claim fields.
- The test is skipped locally without `POSTGRES_TEST_DATABASE_URL` and required in CI with Postgres.
- The run command is documented.

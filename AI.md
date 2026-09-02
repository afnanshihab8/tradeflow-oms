# A note on how I used AI

I used OpenAI ChatGPT and codex as a pair programmer for this assignment. Its involvement was substantial: it
helped turn the brief into a plan, wrote much of the first-pass Django code and tests, ran the checks,
and helped investigate failures. I made the product and architecture calls, steered the revisions,
and kept the scope tied to the assignment rather than treating the generated code as a finished answer.

This was an iterative conversation, not a single “build this app” prompt.

## What I asked it to do

I started by prompting a brief of what was expected in the assignment and my phased implementation plan. The
early conversation focused on questions I expected to defend in a review: transaction boundaries,
concurrent stock purchases, authorization, historical pricing, repeat cancellation, and duplicate
submissions.

Some representative requests, lightly shortened for readability, were:

> Make this plan as strong as possible, and let me review it before we execute.

> Use PostgreSQL, email/password login, SimpleJWT, a separate Customer model, admin-managed products,
> clear idempotency behavior, soft product deletion, and tests for the main edge cases.

> Do not make any Git commits yet. We will handle Git after all coding is done.

> Implement the plan.

> Dockerise the whole project, add Linux commands to the README, and save some conversations later for the AI usage file. 

Codex then worked through the implementation, showed progress as it went, and used test failures as
feedback instead of hiding them.

## Decisions I deliberately changed before implementation

My original outline used DRF's built-in token authentication and put company/tier data on the user.
After reviewing those choices, I changed the design to:

- short-lived SimpleJWT access tokens with rotating, blacklistable refresh tokens;
- a custom email-login `User` kept separate from the `Customer` business account;
- customer-only order creation and summaries, with staff limited to review and cancellation;
- PostgreSQL as a real requirement so row locking can be exercised rather than merely described;
- admin/seed-based catalog management, because product CRUD was not required by the brief;
- immutable order-line snapshots plus product deactivation instead of destructive product deletion.

I also chose a simple discount rule that is easy to explain and test: wholesale accounts receive 10%
off when the order contains at least 50 units in total.

## Where AI helped most

It scaffolded models, serializers, API views, permissions, the transactional order service,
cancellation logic, demo data, OpenAPI documentation, tests, CI, and here and there of the README. 

The most useful part was edge-case pressure testing. In particular, the implementation was exercised
with separate PostgreSQL connections for two buyers competing for the last unit, two requests sharing
one idempotency key, and two simultaneous cancellations. Those are the cases where a solution can look
fine in a normal API test while still corrupting stock in real use.

One concrete correction came from a failing email-outage test. The first callback used
`functools.partial`, which did not expose the callable metadata Django's robust `on_commit` logging
expected. That was replaced by a named closure, and the test was rerun to confirm that an email failure
is logged without turning a committed order into an API error.

Another deliberate hardening step was keeping important checks in the service layer even when the
serializer already validates them. That prevents another caller, such as a management command or a
future background job, from bypassing duplicate-product and stock invariants.

## How I checked the result

Codex ran the Django system check, migration-drift check, Ruff lint/format checks, OpenAPI validation,
the PostgreSQL-backed test suite, concurrency tests, and coverage enforcement. I kept the commands in
the README so the same evidence can be reproduced during review. This file summarizes the relevant chat in a form that is easier to review. 
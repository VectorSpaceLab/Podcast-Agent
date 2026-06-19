# Podcast-Agent Development Docs

`dev-docs` contains the working documents used to design, plan, and validate implementation work.

## Document types

### `design/`

Use for feature design and step-by-step implementation framing.

Each design document should answer:

- What is being added.
- What is in scope.
- What is out of scope.
- Which modules are involved.
- What the minimal implementation looks like.

### `exec-plans/`

Use for execution plans derived from one design document.

Each plan should answer:

- Which design document it follows.
- What the minimum implementation is.
- How modules are organized.
- Which responsibilities belong where.
- What the implementation order is.

### `specs/`

Use for stable contracts and module behavior.

Typical content:

- data models
- artifact formats
- CLI arguments
- IO expectations
- boundary rules

### `decisions/`

Use for architectural decisions that need a reasoned record.

Each decision should explain:

- the decision
- alternatives considered
- the reason for choosing it
- the tradeoffs

### `error-summary/`

Use for production or workflow failure summaries and their repair guidance.

Each error summary should explain:

- the observed failure
- the exact failure point
- the likely cause
- the current fix or workaround
- how to verify the fix

### `cli/`

Use for CLI behavior notes, command examples, and CLI-specific verification.

### `prompts/`

Use for prompt drafts and prompt revisions.

### `examples/`

Use for reproducible sample inputs and outputs.

## Writing rules

- One document should cover one topic.
- File names should use `YYYY-MM-DD-topic-name.md`.
- Keep documents short and implementation-oriented.
- Prefer stable contracts over temporary ideas.
- Keep responsibilities explicit.

## Index

See [`INDEX.md`](INDEX.md) for the current document index.

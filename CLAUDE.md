You are the senior engineer responsible for implementing the entire application described below.

IMPORTANT:
This project must be implemented STRICTLY according to the provided FlyRank Internship Backend Track Capstone Brief:
“AI Image Understanding & Content Matching Engine”.

The PDF is the source of truth.

Your objective is to build the COMPLETE, RUNNABLE, EVALUATABLE application and all required repository artifacts.

Do NOT add features merely because they are technically interesting.
Do NOT turn this into a large image platform.
Do NOT add a frontend.
Do NOT implement stretch goals unless every core requirement is already complete and verified.
Do NOT silently omit requirements.
Do NOT replace a requirement with a superficial mock.
Do NOT claim something works without actually testing it.

The finished repository must be something an evaluator can clone onto a clean machine, run using the documented command, seed with reproducible demo data, exercise through the API, and verify against the capstone acceptance probes.

==================================================

1. # SOURCE-OF-TRUTH REQUIREMENTS

The application must satisfy the following exact capstone goal:

Build a system that:

1. Looks at an image library.
2. Understands what is actually in each image.
3. Automatically tags/classifies the images.
4. Matches images to blog posts based on semantic meaning rather than filenames or exact keywords.
5. Uses a mismatch guard to prevent incorrect recommendations.
6. Gives good suggestions when confident.
7. Safely rejects uncertain or incorrect matches instead of guessing.
8. Explains why a recommendation was rejected.

Core example:

Blog post:
“The behavior of red foxes”

Correct image:
A red fox.

Incorrect candidate:
A gray wolf in a forest.

Expected result:
REJECTED

Expected explanation:
“Animal category mismatch: expected fox, detected wolf”

Another required behavior:

If no image is sufficiently good for a post, the system must return:

“no confident match”

together with reasons such as:

- similarity below threshold
- subjects do not match
- low confidence

This is NOT an image search engine.
It is a trustworthy AI decision system with a safety/mismatch layer.

# ================================================== 2. NON-NEGOTIABLE SCOPE

The implementation must remain within the realistic scope specified by the capstone.

Dataset:

- At least 40 images.
- Target approximately 50 images.
- Images must span at least 4 categories.
- Example categories include:
  - red fox
  - wolf
  - dog
  - bear
  - deer
- Use licensed-free images from Unsplash/Pexels or another corpus mechanism explicitly permitted by the brief.
- Keep the corpus small.
- The corpus must be reproducible.
- Either commit the small corpus if practical or provide a download/seed mechanism that allows evaluators to reproduce it.
- Do not create a huge dataset.

Evaluation dataset:

- At least 10 labeled posts.
- Each post must identify the correct image.
- The eval dataset must measure top-1 precision.
- The resulting top-1 precision must be reported in README.md.
- The number in README.md must match the number produced by the evaluation script.

Review interface:

- NO full frontend.
- API endpoints are sufficient.
- A simple admin/review table or minimal internal page is allowed but is NOT required.
- Prefer API endpoints plus readable JSON responses unless a UI is genuinely necessary.

AI:

- One vision model is sufficient.
- One embedding model is sufficient.
- Do NOT build model-comparison infrastructure.
- Do NOT implement stretch goals before the core is complete.

Budget:

- $0.
- No credit card.
- Use free-tier or fully local tooling.
- Prefer a simple local Ollama-based implementation if that provides the cleanest reproducible implementation.
- If using cloud Gemini, use only the free tier and never hard-code credentials.

# ================================================== 3. REQUIRED TECHNOLOGY DIRECTION

The brief permits:

Backend:

- Node.js + Express
  OR
- Python + FastAPI

Schema validation:

- Zod for Node.js
  OR
- Pydantic for Python

Database:

- PostgreSQL via Docker.
- pgvector is optional according to the brief, but semantic vector storage/search must be implemented.
- At approximately 50 images, an appropriately simple vector representation is acceptable.
- If pgvector makes the implementation cleaner and remains fully free/local, it may be used.
- Do not introduce unnecessary infrastructure.

Vision:

- Gemini Flash free tier
  OR
- Ollama vision model.

Embeddings:

- Gemini embeddings
  OR
- Ollama embedding model such as all-minilm.

Choose ONE vision model and ONE embedding model.

The choice must prioritize:

1. $0 operation
2. reproducibility
3. local/offline capability where practical
4. simplicity
5. reliability for the required evaluation behavior

Do NOT implement multiple AI providers unless strictly necessary to satisfy a requirement.

Claude Code/Nemotron 3 Ultra is the DEVELOPMENT AGENT being used to build this repository.
It is NOT automatically the runtime AI model of this application.
Keep those concepts separate.

# ================================================== 4. REQUIRED ARCHITECTURE

Use a layered architecture with clear separation between:

DATA

- database models
- migrations
- repositories/data-access

LOGIC

- vision processing
- schema validation
- embedding generation
- similarity calculation
- ranking
- mismatch guard
- batch processing
- evaluation
- cost tracking

HTTP

- routes/controllers
- request validation
- response formatting
- error handling

The architecture must make the mismatch guard its own clearly identifiable module/service.

Required conceptual pipeline:

IMAGES
|
| background batch job
v
VISION MODEL
|
v
STRUCTURED VALIDATED METADATA
|
+--> image_metadata
|
+--> embed(caption)
|
v
image_vectors

POST TEXT
|
v
embed(post text)
|
v
post_vectors

GET /posts/:id/images
|
v
Similarity Ranking
|
v
Mismatch Guard
|
+--> Suggested image + explanation
|
+--> No confident match + explanation
|
v
Review API
|
+--> approve
|
+--> reject
|
+--> inspect why

Everything must pass through the guard before being presented as a valid recommendation.

# ================================================== 5. IMAGE INGESTION AND CLASSIFICATION

Every image must be processed through the selected vision model.

The vision model must produce structured metadata equivalent to:

{
"subject": "red fox",
"category": "animal",
"attributes": [
"orange fur",
"wild",
"forest"
],
"caption": "A red fox standing in a forest",
"confidence": 0.94
}

Define a formal schema.

The schema must enforce:

- subject exists
- category exists
- attributes is an array
- caption exists
- confidence exists
- confidence is numeric
- confidence is between 0 and 1
- other appropriate type constraints

The exact implementation can use Zod or Pydantic depending on the selected backend.

CRITICAL:

Never trust raw model output.

Every vision response must go through schema validation before it enters trusted application state.

If model output is malformed:

- do NOT persist it as valid metadata.
- retry when appropriate.
- if retries fail, mark the image processing as failed/flagged.
- record the failure.
- never silently accept malformed output.

Low-confidence classifications:

- must be flagged.
- must NOT be silently accepted as a confident classification.
- must remain inspectable.

The application must be able to demonstrate at least one low-confidence image being flagged.

# ================================================== 6. BATCH BACKGROUND PROCESSING

Vision processing must NOT run synchronously inside a normal request path.

Implement background batch processing for the image corpus.

The batch job must support:

- processing multiple images
- progress tracking
- retries
- failure handling
- cost tracking per AI call
- idempotency where necessary
- status visibility

Slow bulk AI work must never block an ordinary API request.

The implementation does NOT need a massive distributed job system.

Use the simplest reliable background-job mechanism compatible with the selected stack.

The evaluator must be able to trigger the batch processing and observe its result.

Example lifecycle:

PENDING
->
PROCESSING
->
COMPLETED

or

PENDING
->
PROCESSING
->
FAILED / FLAGGED

Retries must not cause duplicate processing to corrupt the database.

If a job is retried, the relevant action should happen only once where idempotency matters.

There must be a clear failure record/log/status so failed jobs are visible.

The shared capstone requirement explicitly requires:

- at least one background job
- retries
- failure alert/visibility

Do not fake this with a synchronous loop hidden behind an endpoint.

# ================================================== 7. COST TRACKING

Every vision and embedding call must have a cost entry.

Create persistent cost records containing enough information to attribute:

- operation type
- model
- related image/post/job if applicable
- timestamp
- token/usage information when available
- calculated cost
- status

Even if the selected local model has an effective monetary cost of $0, record the call and its calculated cost as $0 where appropriate.

The evaluator must be able to inspect the cost log.

Implement a budget guard.

The budget guard must prevent the application from continuing AI processing once the configured budget limit would be exceeded.

Budget configuration must come from environment/configuration rather than hard-coded secrets.

Do NOT fabricate cloud pricing data.

If local Ollama is used, accurately record the monetary cost as zero and still track each call.

# ================================================== 8. EMBEDDINGS

Create embeddings for:

1. Image descriptions/captions.
2. Blog post text.

Both must be embedded into the SAME semantic space using the SAME embedding model.

Store image embeddings.

Store post embeddings.

The system must support semantic equivalence.

For example:

“red fox”

“Vulpes vulpes”

“wild fox species”

should be semantically close enough to allow the correct image to rank highly when the model represents them similarly.

Do NOT implement matching using filename keyword search.

Do NOT rely solely on exact string matching.

# ================================================== 9. VECTOR SEARCH AND SIMILARITY

Use cosine similarity as the ranking metric.

For a post:

1. Obtain/compute its embedding.
2. Compare it with stored image embeddings.
3. Rank image candidates by semantic similarity.
4. Pass candidates into the mismatch guard.
5. Never expose a candidate as a confident recommendation merely because it has the highest similarity score.

Important:
Highest similarity does NOT automatically mean acceptable.

The mismatch guard is mandatory.

# ================================================== 10. MISMATCH GUARD

This is the production-critical decision layer.

Implement it as a separate module/service with explicit, testable rules.

It must combine:

1. Extracted tags / structured metadata.
2. Semantic similarity score.
3. Vision confidence score.
4. Tuned similarity thresholds.

The similarity threshold MUST be selected using the labeled evaluation data.

Do NOT simply invent a threshold and claim it is correct.

The guard must be able to distinguish:

FOX POST + FOX IMAGE
=> potentially accepted if confidence/similarity clear the configured thresholds.

FOX POST + WOLF IMAGE
=> rejected.

FOX POST + GENERIC DOG IMAGE
=> ranks poorly and should not be accepted merely because it is an animal.

No sufficiently good candidate:
=> “no confident match”

The guard must return machine-readable decision data AND a human-readable explanation.

Example:

{
"decision": "rejected",
"reason": "Animal category mismatch: expected fox, detected wolf"
}

Possible rejection reasons include:

- category mismatch
- subject mismatch
- semantic similarity below threshold
- vision confidence below threshold
- multiple guard conditions failed

Do not hide why a candidate was rejected.

The guard should evaluate candidates in a deterministic, testable way.

Keep the guard logic easy to explain to an evaluator.

# ================================================== 11. THRESHOLD TUNING

Do not guess the final similarity threshold.

Create the labeled evaluation dataset first.

Use the evaluation dataset to select/tune the similarity threshold.

The threshold should be defensible using measured evaluation results.

The README must explain:

- what threshold was selected
- what evaluation data was used
- what top-1 precision resulted
- why the threshold is used

Do not optimize the README number by cheating the evaluation dataset.

The fox/wolf boundary must be demonstrably rejected.

# ================================================== 12. NO-CONFIDENT-MATCH BEHAVIOR

This behavior is mandatory.

When no candidate passes the guard:

The API must return a clear result equivalent to:

“no confident match”

with reasons.

For example:

{
"match": null,
"status": "no_confident_match",
"reasons": [
"similarity below threshold",
"subject mismatch"
]
}

Do NOT return the highest-ranked image anyway.

Do NOT fall back to a random image.

Do NOT guess.

The absence of a recommendation is a valid and expected result.

# ================================================== 13. DATABASE

Use PostgreSQL.

Create proper migrations.

The database must contain models/tables representing the required concepts:

- images
- image tags / metadata
- embeddings
- posts
- suggestions
- approvals/rejections
- batch jobs / processing state
- cost records

The brief explicitly requires database models for:

- images
- tags
- embeddings
- posts
- suggestions
- approvals/rejections

Add whatever supporting persistence is minimally necessary for:

- jobs
- retries
- costs
- tenant isolation
- idempotency

Use appropriate indexes.

At minimum, think carefully about indexes for:

- image identifiers
- post identifiers
- job status
- suggestion relationships
- review status
- tenant isolation
- any vector/search fields where applicable

The shared requirements specify:
“Real persistence — schema as migrations, right indexes, isolated tenants.”

Therefore:

- include a tenant identifier in persistent entities where appropriate.
- ensure queries are tenant-scoped.
- seed the application with one demo tenant.
- do NOT build an entire SaaS multi-tenant platform.
- tenant isolation only needs to satisfy the persistence requirement cleanly.

Do not leave the application dependent on in-memory arrays as its real data store.

# ================================================== 14. IDEMPOTENCY

Retries must be safe.

Identify operations where duplicate execution could create incorrect duplicate state.

Implement idempotency where it matters.

Examples:

- image processing job
- embedding generation
- batch job execution
- review decision

Use database constraints/status checks/idempotency keys as appropriate.

Do not over-engineer distributed idempotency infrastructure.

The goal is:
If the same retry happens twice, the application should not create contradictory or duplicated state.

# ================================================== 15. API VALIDATION

All HTTP inputs must be validated at the boundary.

Bad input must result in a clean 4xx response.

Bad input must NOT cause an accidental 500.

Validate:

- path parameters
- query parameters
- request bodies
- review decisions
- post creation/update inputs
- batch job inputs
- any IDs or identifiers

Return clear error responses.

Do not leak:

- API keys
- secrets
- stack traces
- internal credentials

# ================================================== 16. REQUIRED REVIEW WORKFLOW

Implement a simple review API.

The reviewer must be able to:

1. Inspect a suggested pairing.
2. See why an image was selected.
3. See why an image was refused.
4. Approve a suggested pairing.
5. Reject a suggested pairing.

A frontend is NOT required.

Use validated API endpoints.

Persist approval/rejection decisions.

The review data must remain inspectable after the request completes.

# ================================================== 17. REQUIRED ACCEPTANCE PROBES

The implementation must explicitly support these six acceptance probes.

PROBE 1:

Run the batch job on the corpus.

Expected:

- every successfully processed image gets schema-valid tags.
- at least one low-confidence image is flagged rather than guessed.

Create a reproducible way to demonstrate this.

---

PROBE 2:

Query images for the “red fox” article.

Expected:

- fox image ranks first.
- wolf ranks clearly lower.
- dog ranks clearly lower.

The ranking must be based on semantic similarity and then guarded.

---

PROBE 3:

Force the wolf to be considered as a candidate for the fox post.

Expected:

- mismatch guard rejects the wolf.
- response contains a category-mismatch explanation.

Example:
“Animal category mismatch: expected fox, detected wolf”

---

PROBE 4:

Query a post for which there is no suitable image.

Expected:

- “no confident match”
- explanation/reasons
- examples:
  - similarity below threshold
  - subject mismatch

The system must refuse rather than guess.

---

PROBE 5:

Run the evaluation script.

Expected:

- top-1 precision is calculated on the labeled evaluation dataset.
- the value matches the number documented in README.md.

---

PROBE 6:

Inspect the cost log.

Expected:

- every vision call has a cost entry.
- every embedding call has a cost entry.
- calls are attributable to their relevant operation/image/post/job.
- local calls can have monetary cost 0 but must still be recorded.

# ================================================== 18. EVALUATION METRIC

Implement a reproducible evaluation script.

Use the labeled evaluation set.

Measure:

TOP-1 PRECISION

Definition:
Of all evaluated posts, the proportion whose first suggested image was the labeled correct image.

The evaluation output must clearly state:

- total evaluated posts
- number correct at rank 1
- top-1 precision

Example conceptual output:

Evaluated posts: 10
Correct top-1 matches: 9
Top-1 precision: 90.0%

Use the actual measured result.

Do NOT hard-code the number.

The README must contain the actual result generated by the evaluation script.

# ================================================== 19. DEMO DATA

Provide reproducible seed/demo data.

The dataset should contain at least:

- 40 images
- 4+ categories
- approximately 50 images preferred

Use categories that make the mismatch guard demonstrable.

Recommended core animal concepts:

- red fox
- wolf
- dog
- bear
- deer

Create at least 10 blog posts for evaluation.

Ensure the dataset contains:

- correct semantic matches
- visually/semantically similar wrong matches
- clearly unrelated images
- at least one situation where no image should pass the guard
- at least one low-confidence image scenario

The seed process must be reproducible.

Do not depend on manually creating database rows after startup.

If external image URLs are used:

- use permitted/licensed-free sources
- make the download process reproducible
- do not commit secrets
- avoid a dependency on an unreliable manual process if a deterministic seed/download script can be provided.

Keep dataset size reasonable.

Do not download enormous files.

# ================================================== 20. FILES REQUIRED BY THE CAPSTONE

The repository MUST contain:

README.md
capstone.yaml
EVIDENCE.md
BUILDLOG.md
.env.example

Also add:

- .gitignore
- LICENSE
- database migration files
- seed/demo data mechanism
- tests where useful/necessary
- source code
- Docker configuration if used
- evaluation script

README.md MUST contain:

1. What the system does.
2. Architecture explanation.
3. Architecture diagram.
4. Exact setup instructions.
5. Exact run command.
6. Exact database startup instructions.
7. Exact seed steps.
8. Exact API usage examples.
9. How to run the batch job.
10. How to run the evaluation.
11. The actual top-1 precision.
12. How the mismatch guard works.
13. The selected thresholds and how they were tuned.
14. Limitations.
15. Required environment variables.
16. Explanation of local/cloud AI choice.
17. How an evaluator can reproduce the fox/wolf rejection.

The architecture diagram can be ASCII if that is clearer and easier to maintain.

---

capstone.yaml MUST contain:

run:
one command that boots the system

seed:
the command/process used to create reproducible demo data

test:
optional test command, but include one if available

base_url:
the API base URL

endpoints:
the important endpoints an evaluator should probe

Make the manifest simple and machine-readable.

---

EVIDENCE.md MUST contain:

One pasted proof for EVERY requirement in the capstone brief.

Each proof should include:

- requirement name
- test/probe name
- actual command
- actual output/result
- short explanation if necessary

Evidence can be:

- test output
- curl transcript
- log line
- evaluation output

Do NOT write vague claims like:
“Implemented successfully.”

Claims without evidence are considered incomplete.

Populate this file as the implementation progresses.

Use REAL outputs from the running application.

---

BUILDLOG.md MUST contain:

An honest AI usage log.

Record:

- where AI helped
- what the AI generated
- where AI was wrong
- what was corrected
- important engineering decisions
- relevant debugging discoveries

Do NOT pretend the application was written entirely manually.

The capstone explicitly permits AI-assisted development but requires honest ownership.

---

.env.example MUST contain every environment variable required by the app.

Use safe placeholders.

Never include real secrets.

---

.gitignore MUST prevent:

- .env
- node_modules if Node
- virtualenvs/.venv if Python
- caches
- build artifacts
- secrets
- unnecessary large generated files

# ================================================== 21. GITHUB REQUIREMENTS

The repository is intended to be:

A SEPARATE PUBLIC GITHUB REPOSITORY.

Suggested repository name:

flyrank-capstone-image-relevance

Use:

- lowercase
- hyphens
- no spaces

Do NOT build inside another project repository.

Do NOT create a monorepo.

Do NOT mix unrelated work into this repository.

Add a license.
MIT is acceptable.

Keep main runnable.

Make small meaningful commits while building.

Aim for at least one meaningful commit per working session/phase.

Do NOT:

- commit API keys
- commit tokens
- commit passwords
- commit .env
- commit node_modules
- commit virtual environments
- commit oversized datasets
- force-push away meaningful development history

The implementation itself cannot create a GitHub repository unless credentials/access are actually available.
If repository access is unavailable, build the complete local repository and clearly identify the remaining manual GitHub step.

# ================================================== 22. SECURITY / SECRETS

Secrets must exist only in environment configuration.

Never:

- hard-code API keys
- commit API keys
- print API keys
- log API keys
- include secrets in README
- expose secrets through API responses

If a secret is ever stored persistently, use appropriate encryption.
Prefer not storing secrets persistently at all.

# ================================================== 23. FAILURE HANDLING

The system must fail safely.

AI failure:

- retry where appropriate
- record failure
- do not silently accept invalid output

Schema failure:

- reject
- retry/flag
- never trust malformed output

Low confidence:

- flag
- do not confidently classify

Embedding failure:

- record failure
- retry where appropriate
- do not create fake vectors

Database failure:

- return safe server error
- do not expose internals

Invalid HTTP input:

- return 4xx

Budget exceeded:

- stop further AI calls
- return a clear budget-related failure
- preserve already-recorded cost data

No acceptable match:

- return no confident match
- never guess

# ================================================== 24. TESTING REQUIREMENTS

Create tests for the most important correctness guarantees.

At minimum, test:

1. Vision schema accepts valid structured output.
2. Vision schema rejects malformed output.
3. Low-confidence output is flagged.
4. Similarity calculation works.
5. Semantic ranking places the appropriate image first.
6. Fox/wolf mismatch is rejected.
7. Generic dog does not become an accepted fox match merely because it is an animal.
8. Below-threshold candidates are rejected.
9. No-confident-match response is generated.
10. Review approval works.
11. Review rejection works.
12. Invalid API input returns 4xx.
13. Batch retry does not duplicate processing.
14. Cost entries are created for AI calls.
15. Budget guard prevents calls after the configured limit.
16. Evaluation script calculates top-1 precision correctly.

Do not create meaningless tests that only assert that functions exist.

Tests must validate behavior.

# ================================================== 25. OBSERVABILITY

Keep logging useful but minimal.

Log:

- batch job start/end
- image processing success/failure
- retry
- low-confidence flag
- embedding generation
- matching decision
- mismatch rejection reason
- review decision
- cost record
- budget rejection

Never log secrets.

Logs should make it possible to produce evidence for EVIDENCE.md.

# ================================================== 26. DEVELOPMENT PHASES

Implement in these phases, matching the capstone brief.

PHASE 1 — DESIGN

Create:

- one-page design document/content
- problem statement
- data model
- API surface
- layer sketch
- one explicit non-goal
- matching strategy
- mismatch guard rules
- database design
- initial approximately 50-image dataset plan

Gate:
The design is committed and the architecture is clear enough to implement.

Do NOT proceed blindly if the design contradicts the requirements.

---

PHASE 2 — IMAGE UNDERSTANDING PIPELINE

Implement:

- image ingestion
- vision model integration
- structured output
- schema validation
- low-confidence flagging
- batch processing
- retries
- progress/status
- per-call cost tracking

Gate:
All seed images can be processed and their costs are visible.

---

PHASE 3 — MATCHING ENGINE

Implement:

- image embeddings
- post embeddings
- persistence
- semantic similarity
- cosine similarity
- ranking
- mismatch guard
- human-readable rejection explanations
- no-confident-match behavior

Gate:
Fox post ranks fox first.
Wolf is rejected when forced as a candidate.
No-good-image scenario returns no confident match.

---

PHASE 4 — PRODUCTION LAYER

Implement:

- review API
- approval/rejection persistence
- evaluation dataset
- evaluation script
- top-1 precision
- README
- architecture diagram
- EVIDENCE.md
- BUILDLOG.md
- capstone.yaml
- .env.example
- license
- final hardening

Gate:
Every Section 6 requirement has evidence.

# ================================================== 27. STRETCH GOALS

DO NOT implement stretch goals unless every core requirement is complete, tested, evidenced, and passing.

Stretch goals from the brief are:

- automatic alt text
- near-duplicate detection using perceptual hashes or embedding distance
- fallback image generation when no suitable image exists
- human-in-the-loop agent QA for uncertain matches
- test suite for schema validation, mismatch rejection, and matching accuracy

The test suite is listed as a stretch goal in the brief, but implement the core correctness tests needed to prove the mandatory requirements.

Do NOT sacrifice core requirements to implement any stretch feature.

If there is any doubt, SKIP stretch goals.

# ================================================== 28. EXPLICIT NON-GOALS

Do NOT build:

- a full frontend
- user authentication
- social features
- image uploading platform with elaborate UX
- image editing
- recommendation feeds
- chat interface
- autonomous agent swarm
- multiple AI providers
- model comparison dashboard
- massive vector database infrastructure
- cloud deployment infrastructure unless required for running the evaluator
- payment/billing system
- analytics dashboard
- notification system
- unnecessary microservices
- Kubernetes
- Redis unless genuinely required by the simplest job implementation
- complex distributed architecture
- unnecessary abstractions
- unrelated features

The capstone explicitly says:
Do not build a massive image platform.

Favor a small correct system over a large fragile one.

# ================================================== 29. IMPORTANT IMPLEMENTATION PRINCIPLES

PRINCIPLE 1:
Correctness beats complexity.

PRINCIPLE 2:
The mismatch guard is the central engineering feature.

PRINCIPLE 3:
Never trust AI output without schema validation.

PRINCIPLE 4:
Never accept low-confidence classifications silently.

PRINCIPLE 5:
Never guess when no candidate clears the guard.

PRINCIPLE 6:
The similarity threshold must be justified using evaluation data.

PRINCIPLE 7:
Slow bulk AI work belongs in a background job.

PRINCIPLE 8:
Retries must be safe and idempotent.

PRINCIPLE 9:
Every AI call must be cost-tracked.

PRINCIPLE 10:
Bad API input produces 4xx, not accidental 500s.

PRINCIPLE 11:
Secrets stay in environment variables.

PRINCIPLE 12:
Everything necessary to reproduce the demo must be in the repository or provided through a reproducible seed/download process.

PRINCIPLE 13:
Do not claim compliance until you have actually tested it.

# ================================================== 30. CLAUDE CODE OPERATING INSTRUCTIONS

You are operating as an autonomous senior software engineer.

Before writing substantial code:

1. Inspect the repository.
2. Determine whether a project already exists.
3. Do not destroy unrelated user work.
4. If this is an empty repository, initialize the capstone structure.
5. Read all relevant existing files before modifying them.
6. Identify the available runtime/tooling.
7. Choose the simplest stack that satisfies the brief.
8. Write the design before implementing the entire system.

When implementation choices are unspecified by the PDF:

- choose the simplest implementation that satisfies the requirement.
- do not add optional architecture merely because it is common in production.
- document important choices.
- do not ask me unnecessary questions when a reasonable requirement-compliant choice exists.

Do not repeatedly explain what you are going to do.
Spend tokens on implementation, testing, debugging, and verification.

# ================================================== 31. TOKEN-EFFICIENCY RULES

You are running with a capable reasoning model, so use autonomous execution.

Avoid:

- long conversational explanations
- repeating the requirements
- narrating every file before editing it
- asking for confirmation for routine engineering decisions
- generating unnecessary documentation before functionality exists
- rewriting working code without a requirement-driven reason

Prefer:

- inspect
- plan briefly
- implement
- test
- fix
- verify
- document evidence

When a requirement is already satisfied, do not redesign it.

When tests fail:

1. identify root cause
2. fix the implementation
3. rerun the relevant test
4. rerun related acceptance probes if necessary

Do not stop at “the code looks correct.”

# ================================================== 32. REQUIREMENT TRACEABILITY

Maintain a requirement checklist internally while building.

Every mandatory requirement must map to:

- implementation location
- test/probe
- evidence entry

At the end, perform a final audit.

Use this exact conceptual checklist:

AI PROCESSING
[ ] Structured vision output
[ ] Schema validation
[ ] Invalid output never trusted
[ ] Low-confidence classification flagged
[ ] Background batch processing
[ ] Retries
[ ] Per-call vision cost tracking
[ ] Per-call embedding cost tracking

MATCHING
[ ] Image embeddings stored
[ ] Post embeddings stored
[ ] Semantic similarity
[ ] Cosine similarity
[ ] Ranked suggestions
[ ] Equivalent concepts work semantically

SAFETY
[ ] Mismatch guard
[ ] Tag-based validation
[ ] Similarity threshold
[ ] Confidence threshold
[ ] Wolf rejected for fox post
[ ] Human-readable rejection reason
[ ] No-confident-match behavior
[ ] No guessing

BACKEND
[ ] PostgreSQL
[ ] Migrations
[ ] Images model
[ ] Tags/metadata model
[ ] Embeddings model
[ ] Posts model
[ ] Suggestions model
[ ] Approvals/rejections model
[ ] Job persistence
[ ] Cost persistence
[ ] Required indexes
[ ] Tenant isolation
[ ] API boundary validation
[ ] Clean 4xx errors
[ ] Review API
[ ] Idempotency

QUALITY
[ ] Labeled eval dataset >=10 posts
[ ] Top-1 precision calculation
[ ] README precision matches script
[ ] README architecture
[ ] README architecture diagram
[ ] README run instructions
[ ] README seed instructions
[ ] README limitations
[ ] capstone.yaml
[ ] EVIDENCE.md
[ ] BUILDLOG.md
[ ] .env.example
[ ] .gitignore
[ ] License

GITHUB / SECURITY
[ ] Separate repository structure
[ ] No secrets
[ ] No .env
[ ] No node_modules / virtualenv
[ ] Reasonable dataset size
[ ] Reproducible seed
[ ] Main remains runnable

# ================================================== 33. FINAL ACCEPTANCE TEST

Before declaring the project complete, behave as if you are the external FlyRank evaluator.

Start from the documented setup process.

Run the documented run command.

Run the seed process.

Run the batch job.

Verify:

- images receive structured schema-valid metadata
- low-confidence image is flagged
- vision calls have cost records
- embedding calls have cost records

Create/query the red fox post.

Verify:

- fox ranks first
- wolf ranks lower
- dog ranks lower

Force the wolf candidate.

Verify:

- guard rejects it
- category mismatch explanation is present

Run a no-match post.

Verify:

- response says no confident match
- reasons are present

Run the evaluation script.

Verify:

- top-1 precision is calculated
- README contains the exact same number

Inspect the cost log.

Verify:

- every AI operation has an entry

Test invalid API requests.

Verify:

- clean 4xx
- not 500

Test retry/idempotency.

Verify:

- duplicate retry does not corrupt/duplicate state

Test review workflow.

Verify:

- approve works
- reject works
- decision persists
- reason can be inspected

Then audit every mandatory requirement.

# ================================================== 34. EVIDENCE GENERATION

After functionality is verified, update EVIDENCE.md with REAL command output.

Do not fabricate output.

For every requirement, provide enough evidence for an evaluator to verify it quickly.

Prefer examples such as:

COMMAND:
curl ...

OUTPUT:
...

or:

COMMAND:
npm run evaluate

OUTPUT:
Evaluated posts: ...
Correct top-1 matches: ...
Top-1 precision: ...

or actual application logs.

# ================================================== 35. FINAL README QUALITY

The README should be concise but complete.

An evaluator should be able to understand the project within minutes.

Recommended README structure:

# AI Image Understanding & Content Matching Engine

## Problem

## What It Does

## Architecture

## Mismatch Guard

## Data Model

## AI Pipeline

## Matching

## Setup

## Environment Variables

## Run

## Seed

## Batch Processing

## API Endpoints

## Review Workflow

## Evaluation

## Top-1 Precision

## Example: Fox vs Wolf

## Evidence

## Limitations

Do not claim production scale.

Explicitly acknowledge the bounded capstone scope.

# ================================================== 36. FINAL RULE

The PDF requirements outrank your personal engineering preferences.

If a proposed implementation conflicts with the brief:
FOLLOW THE BRIEF.

If a feature is not required and increases complexity:
DO NOT ADD IT.

If an AI model gives an uncertain answer:
DO NOT GUESS.

If the best candidate is wrong:
REJECT IT.

If no candidate clears the threshold:
SAY “NO CONFIDENT MATCH”.

The final product should demonstrate exactly what the capstone is designed to teach:

- structured vision output
- schema validation
- embeddings
- semantic matching
- cosine similarity
- tuned similarity thresholds
- AI safety layers
- background jobs
- retries
- idempotency
- cost tracking
- human-in-the-loop review
- evaluation-driven quality
- production-minded reliability

Start by inspecting the repository and available environment.

Then implement Phase 1.

Do not stop until the complete core capstone is implemented, tested, documented, and verified against all six acceptance probes.

## SOURCE OF TRUTH

This CLAUDE.md is an implementation specification derived from the official
FlyRank capstone PDF.

The official PDF requirements take precedence over engineering preferences,
assumptions, convenience, or suggestions.

If any ambiguity or conflict is discovered, stop and identify the conflict
rather than silently inventing a requirement.

The implementation must satisfy every mandatory requirement in the capstone
brief and must not add unnecessary functionality.

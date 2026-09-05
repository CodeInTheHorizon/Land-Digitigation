# Intelligent Land Record Digitization System — Claude Instructions

## 1. Project Status

This is an EXISTING, RUNNING and FUNCTIONAL project.

Do not rebuild the project from scratch.

Do not replace the existing architecture unless explicitly instructed.

Always inspect the repository and existing implementation before making changes.

Treat existing working functionality as something to preserve.

---

## 2. Project Purpose

This project is an Intelligent Land Record Digitization and Validation System.

It processes scanned land records, PDFs, legacy documents and potentially handwritten documents.

The system aims to:

- upload land-record documents
- preprocess documents
- perform OCR
- support multilingual documents
- extract structured land-record information
- display extracted information clearly
- preserve raw OCR results
- support validation/review
- eventually operate as a deployed full-stack application

Primary expected users include:

- government officials
- land-record operators
- administrative staff
- citizens

The UI should therefore prioritize clarity, reliability and usability rather than decorative design.

---

# 3. Existing Architecture

Do not assume architecture from this file alone.

Inspect the repository when required.

The project contains at least:

- `frontend/`
- `backend/`

Before modifying a subsystem, inspect its current framework, dependencies, conventions and existing implementation.

Reuse existing libraries and components whenever practical.

Do not introduce unnecessary frameworks or dependencies.

---

# 4. Phase 1 Status — COMPLETE

Phase 1 was previously implemented and tested.

DO NOT reimplement Phase 1 unless explicitly asked.

Phase 1 includes:

- improved OCR preprocessing
- structured OCR result extraction
- multilingual handling
- English/Hindi support improvements
- language-aware extraction
- raw OCR preservation
- structured land-record parsing
- warnings/review handling
- frontend structured-result support

Important implementation includes:

`backend/app/services/extraction/structured_record.py`

Phase 1 also modified relevant:

- preprocessing
- OCR orchestration
- document pipeline
- entity extraction
- field mapping
- worker persistence
- extraction API/schema
- frontend types
- OCR result rendering
- `DocumentDetailPage.tsx`

Existing Phase 1 functionality must be preserved.

---

# 5. Existing Structured Extraction

The backend can return information such as:

- `structured_data`
- `detected_language`
- `raw_text`
- `warnings`
- processing metadata

Structured land-record data may contain:

- document language
- document type
- owner details
- father/husband/relative details
- survey number
- khasra number
- khata number
- plot number
- area
- area unit
- village
- tehsil
- district
- state
- land classification
- ownership type
- mutation details
- registration information
- additional extracted fields
- raw OCR text

Missing values should remain null/not detected.

Never fabricate missing land-record information.

Preserve Unicode and original-language values.

---

# 6. Multilingual Rules

The project supports multilingual land records.

English and Hindi are important baseline languages.

Existing additional-language support must not be removed.

Preserve Unicode correctly, particularly Devanagari.

Examples include:

- भूमिस्वामी
- खातेदार
- खसरा क्रमांक
- खाता
- ग्राम
- तहसील
- जिला
- रकबा
- नामांतरण

Do not automatically transliterate or translate extracted values unless specifically requested.

Do not convert Hindi names into English merely for display convenience.

Preserve the original extracted value.

---

# 7. OCR Rules

Unless explicitly working on OCR:

DO NOT modify:

- OCR engines
- preprocessing algorithms
- language-recognition logic
- structured extraction
- parser logic
- entity extraction
- field mapping

UI work must consume the existing API rather than reinvent OCR logic.

If OCR changes are explicitly requested:

1. inspect the current pipeline
2. preserve working behavior
3. make minimal changes
4. never hallucinate extracted fields
5. maintain partial extraction
6. preserve raw OCR
7. run relevant regression tests

---

# 8. Frontend Rules

When working on the frontend:

Prioritize:

- clean layout
- clear information hierarchy
- professional appearance
- responsive behavior
- accessibility
- clear loading states
- clear errors
- readable structured results
- Unicode support
- simple workflows

Prefer existing:

- styling system
- UI components
- utility classes
- component libraries
- project conventions

Avoid:

- excessive gradients
- neon styling
- excessive glassmorphism
- giant landing-page sections
- excessive animations
- decorative floating elements
- heavy animation libraries
- unnecessary cards
- excessive shadows
- unnecessary dependencies

This is an operational administrative application, not a marketing landing page.

---

# 9. UI Effects

Effects should be minimal and professional.

Allowed when appropriate:

- subtle hover transitions
- subtle button transitions
- small card interactions
- accordion transitions
- loading animations
- focus transitions
- small entrance transitions

Prefer roughly 150–300ms UI transitions.

Do not add a heavy animation framework unless already installed.

---

# 10. Structured Result UI Rules

Structured information must be more prominent than raw OCR.

Prefer logical result groups such as:

## Document Information

- detected language
- document type
- processing status

## Owner Details

- owner name
- father/husband name
- address
- additional owners

## Land Identification

- survey number
- khasra number
- khata number
- plot number

## Location

- village
- tehsil
- district
- state

## Area & Classification

- area
- unit
- land classification
- ownership type

## Mutation / Registration

Display relevant structured information when present.

## Additional Fields

Render dynamically rather than assuming every document has identical fields.

---

# 11. Empty Data Rules

Never prominently display frontend values such as:

- `null`
- `undefined`
- empty string
- empty object
- meaningless empty arrays

For important fields where extraction failed, use a user-friendly representation such as:

`Not detected`

Optional sections with no useful information may be hidden.

Do not create large empty UI sections.

---

# 12. Raw OCR Rules

Raw OCR text must remain available.

It must remain secondary to structured results.

Prefer collapsed behavior such as:

`View raw OCR text`

Do not make raw OCR the primary/default result view.

---

# 13. Confidence and Warnings

If confidence or warnings exist in API results, use them.

Use simple statuses such as:

`Needs review`

Do not invent confidence values.

Do not use alarming error styling for normal OCR uncertainty.

Reserve strong error styling for actual failures.

---

# 14. Upload UX Rules

When editing document upload functionality, preserve existing API behavior.

A good workflow is:

Document selection
→ Language / Auto Detect
→ Process Document
→ Processing
→ Structured Result

Where supported, provide:

- drag and drop
- click to browse
- selected filename
- file size
- remove/change document
- supported format information
- language selection
- clear processing button
- clear validation messages

Do not fake upload or OCR progress percentages.

---

# 15. Error Handling

User-facing errors should be understandable.

Handle where applicable:

- unsupported file
- empty upload
- oversized file
- unreadable document
- OCR returned no text
- partial extraction
- request failure
- backend unavailable
- timeout/network issue

Do not display:

- stack traces
- internal filesystem paths
- secrets
- raw internal exception dumps

in the production UI.

---

# 16. Responsive UI

Frontend changes should work on:

- desktop
- tablet
- mobile

Desktop/tablet are the primary operational targets.

Ensure:

- no horizontal overflow
- long identifiers wrap appropriately
- Hindi/Unicode text renders correctly
- buttons remain usable
- navigation remains accessible
- structured information remains readable

---

# 17. Accessibility

Apply practical accessibility improvements.

Use:

- semantic controls
- labels
- visible keyboard focus
- adequate contrast
- readable font sizes
- understandable disabled states
- accessible loading states

Do not perform unrelated large accessibility rewrites.

---

# 18. Deployment Status

IMPORTANT:

Deployment-related changes may already exist because a previous coding agent accidentally began deployment work before Phase 1.

Therefore:

DO NOT rewrite deployment configuration unless explicitly asked.

When deployment work is requested:

First audit existing configuration.

Inspect relevant files such as:

- `vercel.json`
- `render.yaml`
- Dockerfiles
- `.env.example`
- frontend environment handling
- backend CORS
- backend start commands
- health endpoint
- production dependencies

Reuse valid existing deployment configuration.

Fix only what is missing or incorrect.

Target architecture is expected to be:

Frontend → Vercel

Backend/API → Render

Do not automatically migrate database, Redis, storage, OCR engine or other infrastructure.

---

# 19. Secrets

Never expose or hard-code secrets.

Never print actual `.env` secret values.

Do not commit:

- API keys
- database passwords
- JWT secrets
- authentication secrets
- private service credentials

Use environment variables.

Preserve `.env.example` with safe placeholder values when applicable.

---

# 20. Scope Discipline

Modify only files required for the current task.

Do not use a narrowly-scoped request as justification for project-wide refactoring.

Avoid:

- rewriting working modules
- renaming unrelated files
- reorganizing the entire folder structure
- replacing existing libraries
- modifying APIs unnecessarily
- changing database technology
- introducing architecture changes without need

Minimal, targeted modifications are preferred.

---

# 21. Existing Functionality Protection

Unless the current task explicitly changes them, preserve:

- document upload
- OCR processing
- structured extraction
- multilingual support
- detected language
- structured_data handling
- raw OCR
- warnings
- authentication
- routing
- document history
- backend API integration
- database behavior
- worker behavior
- deployment configuration

---

# 22. Code Quality Rules

Follow existing project conventions.

Prefer:

- reusable existing components
- small targeted components
- clear names
- type-safe code
- minimal duplication
- maintainable code

Avoid unnecessary abstraction.

Do not extract a new component merely because three lines of JSX exist.

Do not suppress TypeScript problems with `any` unless genuinely unavoidable.

Do not change lint rules simply to hide errors.

Remove unused imports/debug statements only in files being modified.

---

# 23. Dependency Rules

Before adding a dependency:

1. check whether existing project dependencies already solve the problem
2. prefer built-in framework capabilities
3. prefer current component/styling system
4. add a package only when there is a clear implementation benefit

Do not install large packages for trivial UI effects.

---

# 24. Testing Rules

After implementation, run only relevant validation.

Frontend tasks should use configured commands for:

- type checking
- lint
- production build
- relevant tests

Backend tasks should use:

- relevant backend tests
- startup/import validation where appropriate

Do not run huge unrelated suites repeatedly without reason.

Never claim a test passed unless it was actually executed.

If a failure existed before the current task and is unrelated, report it rather than modifying unrelated code.

---

# 25. Git Safety

Do not:

- delete user work
- reset unrelated changes
- run destructive Git commands
- force push
- rewrite Git history
- execute `git push`

unless explicitly instructed.

Before overwriting suspicious existing work, inspect it.

Do not revert changes made by another agent solely because you would have implemented them differently.

---

# 26. Agent Behavior

Operate as an implementation agent, not a tutorial assistant.

When given an implementation task:

1. read this file
2. inspect only relevant code
3. understand current implementation
4. make required changes
5. validate them
6. report concise results
7. stop

Do not ask questions that the repository itself can answer.

Do not ask for confirmation for ordinary implementation decisions.

Make reasonable choices based on existing architecture.

---

# 27. Token and Output Discipline

Keep token usage LOW.

Do not narrate detailed reasoning.

Do not give lengthy explanations of files.

Do not explain basic programming concepts.

Do not create unsolicited documentation.

Do not repeatedly summarize progress.

During execution, use only short status messages when needed, such as:

- `Inspecting frontend...`
- `Updating result UI...`
- `Running validation...`

Do not output a long implementation plan unless explicitly requested.

Do not paste large amounts of source code in chat after already modifying files.

---

# 28. Final Response Format

Unless the execution prompt specifies otherwise, finish with only:

TASK COMPLETE

Files changed:
- ...

Implemented:
- maximum 8 concise points

Validation:
- Type check: PASS/FAIL/NOT APPLICABLE
- Lint: PASS/FAIL/NOT APPLICABLE
- Build: PASS/FAIL/NOT APPLICABLE
- Tests: PASS/FAIL/NOT CONFIGURED

Existing issues not caused by this task:
- only when applicable

Do not add:

- tutorials
- future recommendations
- lengthy explanation
- code walkthrough
- unrelated suggestions

Stop after reporting completion.
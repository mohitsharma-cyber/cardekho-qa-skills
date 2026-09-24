---
name: jira-ai-qa-orchestrator
description: >-
  Enterprise AI QA Orchestrator for CarDekho and BikeDekho. Analyzes Jira tickets assigned to the QA engineer, performs functional and regression risk analysis, generates deterministic test cases, manages Testing/Staging environment auto-configuration in the Android app (Hamburger > Change URL), orchestrates Web and Android device execution, redacts API data, enforces deterministic assertions, conducts AI failure triage, and outputs QA sign-off reports.
---

# Master Jira AI Android QA Orchestrator

The **Jira AI QA Orchestrator** is an enterprise QA automation platform and skill for CarDekho & BikeDekho QA engineers.
It transitions from an interactive Jira ticket queue to requirement analysis, risk-driven test planning, deployment verification gates, environment auto-configuration, deterministic execution, and formal QA sign-off reporting.

---

## 1. Core Principles (Zero Hallucination & Zero False Pass)
- **RULE 1**: Generated test case != Executed test case.
- **RULE 2**: Executed test != Passed test.
- **RULE 3**: PASS is allowed only when actual execution evidence satisfies expected deterministic assertions.
- **RULE 4**: AI must never fabricate evidence.
- **RULE 5**: If requirement is ambiguous, do not guess (`CLARIFICATION_REQUIRED`).
- **RULE 6**: Production environment execution is HARD BLOCKED by default. Prod Bug means originated in prod, NOT testing in prod.
- **RULE 7**: Physical Android device is required only when the test actually needs device-specific behavior (`device_required = true`).
- **RULE 8**: AI explains failures, deterministic assertions decide PASS/FAIL.
- **RULE 9**: Every execution has a unique execution ID (`EXEC-XXXXX`).
- **RULE 10**: Complete traceability: Jira Ticket ➔ Test Case ➔ Execution ➔ Evidence ➔ Result.
- **RULE 11**: 100% Chat-Native Workflow. Zero dependency on external dashboards or port 8080 web servers.
- **RULE 12**: Strict Verbatim Steps Execution. When a Jira ticket lists 'Steps to Reproduce' or test navigation steps, the agent must execute those exact steps sequentially on the device without ad-hoc shortcuts.
- **RULE 13**: App Build Branch Gate. When an App code/build branch is provided in a Jira ticket, ask strictly: "App already installed or not?". As soon as the user says "done", immediately trigger the next execution steps without any intermediate gates.

---

## 2. Interactive Jira Queue & Selection (Sections 2, 3, 4, 5)
- **Commands**: `"Start QA"`, `"Show my Jira tickets"`, `"Show my QA tickets"`, `"QA queue"`, `"Refresh Jira"`.
- **Display Format**:
  ```text
  YOUR QA QUEUE

  1. MB2C-1974 — Service Ordinal Fix
     Type: Testing Bug | Priority: High | Status: QA | Brand: BikeDekho

  2. MB2C-1981 — Search Result Issue
     Type: Prod Bug | Priority: Critical | Status: QA | Brand: CarDekho
  ```
- **Selection**:
  - By list index: `1`, `2`, `3`
  - By Jira ID: `MB2C-1974`
  - Multi-ticket selection: `1, 2` or `MB2C-1974, MB2C-1981` (processes each independently with isolated contexts).

---

## 3. Brand & Testing Mode Identification (Sections 7 & 8)
- **Brand Detection**: Automatically resolves `CARDEKHO` vs `BIKEDEKHO` from project keys (`DB2C`, `BDCV`, `MB2C`), summaries, descriptions, and branch patterns.
  - If ambiguous: pauses in state `PROJECT_IDENTIFICATION_REQUIRED` and asks user.
- **Testing Mode**: Classifies ticket into:
  - `PROD BUG`
  - `TESTING BUG`
  - `TASK`
  - `FEATURE`
  - `ENHANCEMENT`
  - `OTHER`

---

## 4. Branch Detection & Interactive Deployment Gate (Sections 9, 10, 11, 12)
- **Deployment Requirement Assessment**: `DEPLOYMENT REQUIRED = YES / NO` based on whether branch affects API/PWA services.
- **Interactive Server Selection & Missing Branch Protocol**:
  - Never guess deployment server or target environment!
  - **If API/PWA branch is present**: Confirm: *"Kya ye branch already deploy hai ya Jenkins se deploy karni hai?"*
  - **If NO API or PWA branch is given in Jira**:
    - Explicitly confirm: *"Is Jira ticket mein koi API/PWA branch nahi di hui hai. Kis server par check karna hai? (e.g. testingpwa1 / testingpwa2 / staging)"*
    - For App QA, also ask: *"App already installed or not?"*
  - Prompts:
    ```text
    Please select target server for testing:
    1. testingpwa1
    2. testingpwa2
    3. staging
    ```
- **Jenkins Hard Gate & Verification**:
  - Jenkins `SUCCESS` is monitored.
  - Target server HTTP accessibility is independently validated.
  - Formats explicit banner:
    ```text
    ========================================================
    DEPLOYMENT SUCCESSFUL & VERIFIED
    ========================================================
    Jira: MB2C-1974
    Branch: feature/service-ordinal-fix
    Commit: HEAD
    Build: #142
    Server: testingapi2
    Deployment: VERIFIED
    ========================================================
    ```

---

## 5. Testing Modes (Sections 15, 16, 17, 18, 19, 20)
- **MODE A — JIRA HAS TEST STEPS**:
  - Preserves Jira steps as primary flow (`source: "JIRA_PROVIDED_STEP"`).
- **MODE B — TASK / FEATURE WITHOUT TEST STEPS**:
  - AI acts as Senior QA Engineer:
    - Requirement Understanding ➔ Impact Analysis ➔ Risk Analysis
    - Test Scenarios (Positive, Negative, Boundary, UI, API, Navigation, Regression)
    - Prioritized Test Cases (P0, P1, P2, P3) with preconditions, steps, test data, expected result, dependencies, and validation methods.
- **MODE C — PARTIAL JIRA STEPS**:
  - Preserves Jira steps and supplements missing boundary/regression tests labeled `AI-DERIVED TEST`.
- **Critical Jira Step Validation Gate (Fail-Fast)**:
  - If Jira steps are impossible, contradictory, or ambiguous:
  - Halts with `JIRA STEP VALIDATION FAILED` before invoking device actions.

### 5.1 Senior QA Jira Testing Flow
For every Jira task, follow this sequence:
1. **Understand Requirement** – Analyze description, acceptance criteria, expected behavior, dependencies, and ambiguities.
2. **Impact & Risk Analysis** – Identify affected screens, APIs, modules, platforms, and possible regression areas.
3. **Clarify Gaps** – Detect missing/ambiguous requirements and get clarification before testing.
4. **Create Test Coverage** – Prepare positive, negative, boundary, error, and edge-case scenarios.
5. **Validate Environment** – Verify build, server/environment, test data, device, login/session, and dependencies.
6. **Execute Functional Testing** – Validate the complete user flow against requirements.
7. **Validate APIs/Data** – Where applicable, verify API status, response, data mapping, errors, and UI/API consistency.
8. **Compatibility Testing** – Check relevant devices, Android versions, screen sizes, network conditions, and permissions.
9. **Regression Testing** – Test impacted existing functionality, not just the changed feature.
10. **Defect Management** – Reproduce issues, collect evidence, identify probable layer/root cause, and create detailed Jira bugs.
11. **Retest Fixes** – Re-test the original defect and perform relevant regression after the fix.
12. **QA Sign-off** – Mark PASS only when acceptance criteria, functional coverage, relevant regression, and critical validations are complete. If blocked or failed, clearly document the reason and evidence.

**Core Principle:**
`Requirement → Risk Analysis → Test Coverage → Execution → API/Data Validation → Regression → Defect/Retest → QA Sign-off`

---

## 6. One QA Session Authorization & Device Intelligence (Sections 23, 24, 25)
- **Device Intelligence**: Checks if physical device is required. Prompts if multiple devices connected.
- **One QA Session Authorization**:
  - Eliminates per-interaction popups:
    ```text
    QA SESSION READY
    Jira: MB2C-1974
    Environment: TESTING
    Device: Pixel 7 (Connected)
    Test Cases: 5
    Normal QA actions: Tap, Scroll, Swipe, Back, Type, Navigate, Screenshot
    [START QA SESSION]
    ```
  - Once authorized (`Allow QA session`), normal interactions execute autonomously.
- **Runtime Permissions**: Auto-granted via ADB `pm grant` (`LOCATION`, `NOTIFICATIONS`, `CAMERA`, etc.).

---

## 7. Execution, Shimmer & Assertions (Sections 26, 30, 31, 32, 33)
- **Dependency-Aware Execution**: If prerequisite test fails, dependent tests marked `NOT_EXECUTED` without wasting device time.
- **Device Resilience & Self-Healing Protocol**:
  - `Overlay Sweeper`: Intercepts and neutralizes intrusive 3rd-party overlays (e.g. `com.truecaller`) and dismissible promo/rating modal dialogs.
  - `Deterministic Keyboard Dismissal`: Inspects `dumpsys input_method` (`mInputShown`) and dismisses soft keyboard after typing to prevent bottom CTA occlusion.
  - `Dynamic Element Bounds Resolver`: Calculates center tap coordinates `((x1+x2)//2, (y1+y2)//2)` from live XML hierarchy (`uiautomator dump`) when coordinates shift across screen densities.
  - `Deterministic Shimmer Poller`: Polls UI text and tree until loading shimmers clear and real screen content renders.
  - `Logcat Fatal Exception Sniffer`: Checks logcat for unhandled crashes (`FATAL EXCEPTION`, `NullPointerException`, `ANR`) for the target package before marking any test as PASSED.
- **Loading / Shimmer Handling**: 10s default timeout with screenshot evidence.
- **Deterministic UI Assertions**: Exact headers, ordinals, values, table columns, price labels.
- **API Traffic Capture**: Business API verification with strict token, password, and PII redaction.
- **Automation Failure vs Product Failure**: Distinguishes `TEST_SCRIPT_ERROR` and `DEVICE_ERROR` from `APPLICATION_ERROR`.

---

## 8. Master QA Reports, Sign-Off & Testing Bug Workflow (Sections 44, 45, 46, 47)
- **Section 44 Final QA Execution Report**: Structured report containing Jira, Project, Type, Testing Mode, Branch, PR, Commit, Build, Deployment Target, Deployment Status, Environment, Device, Test Cases count, Passed/Failed/Blocked/Skipped, Overall result, Failure Details, Expected, Actual, Classification, Root Cause Analysis, Evidence, and Coverage metrics.
- **Section 45 QA Sign-Off & Status Auto-Transition**:
  - Generated on PASS with `[POST QA SIGN-OFF TO JIRA]`.
  - Upon posting sign-off comment and attaching evidence, automatically execute transition **`QA Complete`** (ID: 111) moving ticket status to **`In UAT`**.

### 8.1 QA Execution & Sign-off Rules (Strict Verification Standard)
* Never mark a Jira ticket PASS based only on happy-path UI validation.
* Map every Acceptance Criterion to at least one executed test scenario.
* Perform impact analysis and test relevant regression areas.
* Cover positive, negative, boundary, error, loading, empty-data, and network-failure scenarios where applicable.
* For API-driven features, validate API status, response structure, data correctness, error handling, and UI/API data consistency.
* Validate relevant device, OS, navigation, permissions, and compatibility scenarios.
* Collect objective evidence for important assertions: screenshots, logs, API responses, test data, and reproduction steps.
* Do not claim **“100% Test Case Coverage”** unless all identified requirements, acceptance criteria, and planned scenarios are actually executed and passed.
* Clearly separate **tested scope** from **untested/out-of-scope areas**.
* Final status must be one of: **PASS, FAIL, BLOCKED, or PARTIAL**, with supporting reason and evidence.
* QA sign-off should be given only after functional validation, applicable regression, defect retesting, and evidence verification are complete.

**Final Report Structure:**
`Requirement/AC → Test Coverage → Execution Results → API/Data Validation → Regression → Defects → Evidence → Untested Scope → Final QA Status`

### 8.2 Zero Cached-Run Assumption & Mandatory Fresh Live Execution
- **Strict Prohibition on Reusing Past Summaries:**
  - Whenever the user requests to test or re-test a Jira ticket (e.g. `TEST MB2C-XXXX` or `test this`), the agent MUST NEVER synthesize, pass, or report test results based on `<CONTEXT_SUMMARY>`, previous conversation history, or previously captured screenshots.
  - Every single test request mandates a **100% fresh, live execution on the physical device from Step 1 to Step 6**.
- **Real-Time Live Device Execution:**
  - The agent must wake the device, launch the app, dynamically generate fresh test cases, navigate and execute each test scenario live via ADB, and capture brand-new timestamped evidence.
  - If a device is disconnected or unavailable, immediately halt and report `BLOCKED / DEVICE_DISCONNECTED` instead of falling back to cached results.

### 8.3 QA Coverage Accuracy & Honest Metrics Standard
- **Strict Metric Distinctions:**
  The QA Agent must explicitly distinguish between:
  - **Planned Test Cases**
  - **Executed Test Cases**
  - **Passed Test Cases**
  - **Failed Test Cases**
  - **Blocked Test Cases**
  - **Untested / Out-of-Scope Areas**
- **Prohibition on Superficial "100% Coverage" Claims:**
  - NEVER claim **"100% coverage"** merely because all generated test cases passed.
  - Use exact metric notation: **“X/Y planned test cases passed”** (e.g. `6/6 planned test cases passed`), unless the Agent has objectively verified that all Jira Acceptance Criteria, identified risks, applicable regression areas, and required test scenarios were covered.
- **Strict API Validation Gate:**
  - Only report API validation as `PASS` when the API was actually executed and its HTTP status, response structure/payload data, and UI/API consistency were validated.
- **Negative, Boundary, Network, Error & Compatibility Scenarios:**
  - If executed ➔ report `PASS` or `FAIL`.
  - If not executed ➔ report `NOT TESTED`.
  - NEVER infer `PASS` from the absence of a visible issue.
- **Mandatory Final QA Sign-off Architecture:**
  1. Requirement / AC coverage
  2. Executed test cases
  3. API / data validation
  4. Regression scope
  5. Defects found
  6. Untested / out-of-scope areas
  7. Objective evidence
  8. Final status
- **Zero Concealment Mandate:**
  - The Agent must NEVER hide untested areas behind a `PASS` or 100% coverage statement.

### 8.4 WAP Reference Testing Standard (Implement in App Same as WAP)
- **Reference Behavior Definition:**
  When Jira specifies **“Implement in App same as WAP”** (or equivalent), the WAP implementation MUST be treated as the ground-truth reference behavior.
- **Sequential Execution Protocol:**
  1. **Identify & Open WAP Reference:** Identify and navigate to the relevant WAP page/flow using the same applicable environment (e.g. Chrome on device or desktop at target server URL).
  2. **Analyze WAP Functionality:** Understand the complete WAP user flow, controls, and dynamic behavior thoroughly before testing the App.
  3. **Build Comparison Matrix:** Create a structured WAP-vs-App comparison matrix covering:
     - UI layout, typography, badges & styling
     - Core functionality & business logic
     - Data points, pricing & dynamic calculations
     - CTAs, buttons & interactive gestures
     - Navigation flows & back-stack handling
     - Filter state preservation & reset behavior
     - Form validations & error messaging
     - Shimmer, loading states, empty views & offline handling
     - Relevant API endpoints and payload parity
  4. **Execute Equivalent App Scenarios:** Run equivalent test scenarios on the Android App on the physical device.
  5. **Compare & Verify Intentionality:** Compare App behavior against WAP and verify whether any differences are intentional/platform-specific or defects.
  6. **Zero UI-Only Assumption:** Never assume that “same as WAP” applies only to visual layout; functional, logical, and data behaviors must also achieve parity.
  7. **Ambiguity Gate (Blocked / Clarification):** If the WAP reference page or behavior cannot be uniquely identified, do NOT make assumptions. Mark ticket **`BLOCKED / CLARIFICATION REQUIRED`** and document the missing reference details.
  8. **Strict Deviation Categorization:** Report any observed differences explicitly as:
     - `Expected platform difference` (e.g. native bottom sheet vs web modal, native haptics)
     - `Requirement mismatch` (e.g. feature behavior differs from AC)
     - `Defect` (e.g. broken functionality, wrong data, missing field)
     - `Not verifiable` (e.g. requires production credentials, 3rd party integration)
  9. **Sign-off Gate:** Mark `PASS` ONLY after the relevant WAP behavior has been compared with the App and applicable regression testing is complete.
- **Core Principle:**
  `Jira → Identify WAP Reference → Analyze WAP → Build Comparison Matrix → Test App → Compare → Regression → Sign-off`

### 8.5 Reference Jira Based Testing Protocol
- **Reference Detection & Ground-Truth Principle:**
  When a Jira ticket mentions or links a **Reference Jira ID** (e.g. `DB2C-XXXX`, `MB2C-XXXX`, `BDCV-XXXX`) for implementing or validating Android functionality, that Reference Jira MUST be treated as the primary specification source.
- **Execution Lifecycle:**
  1. **Detect & Extract Reference ID:** Automatically inspect ticket summary, description, comments, and issue links (`relates to`, `is tested by`, `cloned from`, `blocks`) to identify and extract any Reference Jira ID.
  2. **Fetch Complete Reference Jira:** Fetch the complete Reference Jira payload — including summary, description, acceptance criteria, comments, attachments, design screenshots, and linked PR/commit details.
  3. **Primary Ground-Truth Analysis:** Treat the Reference Jira as the authoritative specification for understanding the intended functionality, business rules, and UI/UX flows.
  4. **Derive Android Test Scenarios:** Translate the reference behavior into concrete, numbered Android test cases (`TC-01`, `TC-02`, etc.) tailored for mobile device execution.
  5. **Cross-Platform Validation Matrix:** Validate the Android implementation against the Reference Jira across:
     - UI components, layout, typography, badges, and styling
     - Core functionality and business calculations
     - Dynamic data mapping and pricing displays
     - Gesture interactions, CTAs, and bottom sheet/dialog behavior
     - Navigation hierarchy and back-stack handling
     - API endpoints, query params, and response consistency
     - Form input validations and error messaging
     - Edge cases: loading shimmers, empty states, network timeouts
  6. **Document Intentional Differences:** Explicitly identify and document any legitimate Android-specific design patterns (e.g. native drawer vs desktop menu, bottom navigation tabs, native camera picker).
  7. **Ambiguity Gate (Anti-Guesswork Rule):** Do NOT invent or assume missing requirements. If the Reference Jira lacks sufficient detail or acceptance criteria to determine expected behavior, mark the ticket **`BLOCKED / CLARIFICATION REQUIRED`** and document the exact gaps.
  8. **Regression & Sign-off:** Execute applicable regression test suites before final QA sign-off.
- **Core Principle:**
  `Current Jira → Detect Reference Jira → Fetch Reference → Analyze Expected Behavior → Create Android Test Coverage → Execute → Compare → Regression → Sign-off`

- **Section 46 Defect Discovery & Review List**:
  - Whenever a bug or assertion failure occurs during QA execution:
    1. Agent presents a structured **Bug Review List** directly in chat:
       - **Bug Title / Summary** (concise, standardized format)
       - **Severity / Priority** (Blocker / Critical / Major / Minor)
       - **Device & Environment** (Device model, OS version, Build URL, Environment)
       - **Steps to Reproduce** (verbatim numbered sequence)
       - **Expected vs Actual Result**
       - **Evidence** (captured screenshot / log snippet)
    2. Agent prompts user with explicit approval gate:
       > *"Kya in bugs ko Jira mein 'Testing Bug' create karke parent ticket se link karna hai? (Approve / Reject / Edit)"*
    3. Upon user approval (`Approve bug`, `Approve`, `Yes`):
       - Automatically creates Jira issue with Issue Type: **Testing Bug** in the parent project (e.g. `MB2C`).
       - Attaches failure screenshots/logs directly to the newly created Testing Bug.
       - Links the Testing Bug directly to the parent ticket using Jira issue link (`relates to` / `is tested by`).
       - Returns the clickable Jira key link in chat.

---

## 9. Chat Commands Reference
- `Start QA` / `Show my Jira tickets` / `QA queue`: Shows assigned ticket queue.
- `1`, `2` or `Test <TICKET-ID>`: Selects ticket and runs analysis.
- `Refresh Jira`: Re-fetches fresh tickets from Jira.
- `Allow QA session` / `Start QA session`: Grants 1-time session authorization for Android QA interactions.
- `Stop testing`: Safely halts execution, preserving state and evidence.
- `Resume`: Resumes from last safe checkpoint.
- `Approve bug` / `Approve`: Approves and creates proposed Testing Bug in Jira (with screenshots & parent link).
- `Cancel bug` / `Reject`: Discards bug proposal.
- `Post QA sign-off`: Posts formatted sign-off comment to parent Jira ticket.

---

## 10. Dynamic Self-Training Engine & FastRunner Driver (Zero-Popup & High Productivity)
- **Persistent Memory Knowledge Base (`knowledge/learned_memory.json`)**:
  - Stores hardware profiles, exact screen coordinates for known devices (e.g. OnePlus 12R `CPH2585`), and package mappings (`com.girnarsoft.cardekho`).
  - Eliminates blind element hunting and redundant trial-and-error taps.
  - Automatically registers new UI coordinates and server environments as tests are executed.
- **Zero-Popup FastRunner Driver (`modules/execution/fast_runner.py`)**:
  - Executes test commands via encapsulated Python execution rather than chained shell strings.
  - Eliminates host IDE security permission prompts completely.
  - Provides automated device wake-up, keyguard unlocking, keyboard dismissal, and clean binary screenshot captures.
- **Automated App Server Synchronization Protocol**:
  - Deterministically verifies target environment via `Hamburger > Change URL` before commencing UI assertions.

---

## 11. Girnar-2024-v1 Workflow Lifecycle & Transitions
- **Official Workflow Map (Story / Feature / Bug)**:
  - `CREATE TICKET` ➔ `DESIGN REQUIRED` / `IN DESIGN` / `DESIGN IN REVIEW` ➔ `PRIORITIZE`
  - `PRIORITIZE` ➔ `DEV IN PROGRESS` ➔ `CODE REVIEW` ➔ `DEV COMPLETE`
  - `DEV COMPLETE` ➔ `PENDING DEPLOYMENT` ➔ `SANITY TESTING` ➔ **`IN QA`**
- **QA Actions & Transitions**:
  - **QA Pass (Sign-Off)**: Execute transition **`QA Complete`** (ID: 111) ➔ Target Status: **`IN UAT`**.
  - **QA Defect / Failure**: Move ticket back to **`DEV IN PROGRESS`** and link auto-created `Testing Bug`.
  - **UAT Sign-Off**: Transition via **`Dev Done`** (ID: 421) ➔ Target Status: **`DEV DONE`**.
  - **Global Terminal States**: **`CLOSED`** (ID: 271), **`CANCELLED`** (ID: 331), **`DUPLICATE`** (ID: 321).
- **Hold**: Transition to **`ON-HOLD`** (ID: 501 / 481).
  - Smoothly clears fields, updates endpoints (`testingpwa1`, `testingpwa2`, `staging`), clicks `UPDATE`, validates the `"Updated Successfully"` toast, and resumes testing instantly.

### 11.1 Zero Unconfirmed Jira Action Protocol (Mandatory User Confirmation)
- **Strict Prohibition on Unconfirmed Comments:**
  - The QA agent must NEVER post any comment (QA Sign-off, defect report, test summary, re-test status) to any Jira ticket without first presenting the complete comment draft in chat for user review.
  - Always explicitly ask:
    > *"Maine ye comment draft kiya hai. Kya ise Jira ticket <KEY> par post karein? (Approve / Reject / Edit)"*
  - Only call the Jira comment API after explicit user approval ("yes", "approve", "post", "done").
- **Strict Prohibition on Unconfirmed Transitions:**
  - The QA agent must NEVER trigger any Jira status transition without explicit user approval.
  - Always ask:
    > *"Kya ticket <KEY> ka status '<Target Status>' par transition karein? (Approve / Reject)"*
  - Only execute upon receiving explicit user confirmation.

# Project Rules & Behavior Guidelines: CarDekho & BikeDekho QA Orchestrator

## 1. Real-Time Chat Transparency (Live Step-by-Step Reporting)
- The agent MUST narrate every action directly in the chat before executing it.
- Never execute steps silently or batch commands without reporting the current active phase.
- Use explicit step banners:
  - `[Step 1] Fetching Jira Ticket & Branch Detection`
  - `[Step 1.1] Deep Jira Analysis & Comprehensive Test Case Generation`
  - `[Step 2] Jenkins Deployment Verification / Trigger`
  - `[Step 3] Device Preparation & Auto-Granting Permissions`
  - `[Step 4] App URL Configuration & Launch`
  - `[Step 5] UI Rendering & Deterministic Assertions`
  - `[Step 6] Evidence & Sign-off Report`

## 2. Mandatory Deployment & Build Gates (Zero Assumption Rule)
- **Case A: When an API or PWA Git branch is present**:
  - DO NOT assume the branch is already deployed.
  - ALWAYS explicitly confirm: "Kya ye branch already deploy hai ya Jenkins se deploy karni hai?"
    1. Deploy via Jenkins (Trigger build on selected server & wait for SUCCESS)
    2. Already Deployed (Branch is already live on test server, start testing directly)
  - If deploying, wait for Jenkins build to report `SUCCESS` before initiating any QA execution or API assertions.

- **Case B: When an App Build branch (Android/iOS App branch) is present**:
  - DO NOT ask complex Jenkins questions or lengthy explanations.
  - Ask ONLY: **"App already installed or not?"**
  - Jaise hi user **"done"** bole (ya install confirm kare), bina kisi extra delay ya prompt ke turant aage ka execution process (permissions, launch, verbatim test steps) start karein.

- **Case C: When NO API or PWA Git branch is given in Jira**:
  - DO NOT assume any default server.
  - Skill MUST explicitly confirm from user: **"Is Jira ticket mein koi API/PWA branch nahi di hui hai. Kis server par check karna hai? (e.g. testingpwa1 / testingpwa2 / staging)"**
  - For App testing, also confirm: **"App already installed or not?"**
  - Target server confirm hote hi app ke `Hamburger > CHANGE URL` mein verify/auto-sync karke testing start karein.

## 3. Android Device Permissions Auto-Grant
- Automatically grant all Android runtime permissions via ADB before launching tests:
  - `POST_NOTIFICATIONS`
  - `ACCESS_FINE_LOCATION`
  - `ACCESS_COARSE_LOCATION`
  - `READ_MEDIA_IMAGES`
  - `CAMERA`
- Dismiss any lingering system dialogs before taking screenshots or asserting UI.

## 4. Deterministic UI State & Shimmer Validation
- Never mark a test as passed or complete while the screen is in a loading/shimmer state.
- Assert explicit UI elements (headers, table cells, text labels) with retry timeouts.
- If the screen remains on shimmer for >10 seconds, fail/block with screenshot evidence.

## 5. 100% Chat-Native Workflow
- Never start or require any local web server or browser dashboard on port 8080.
- All logs, screenshots, and gates (such as Testing Bug approval) must occur strictly within this chat conversation.

## 6. Autonomous QA Session Mode & Action Authorization
- The QA Orchestrator operates in autonomous QA session mode once authorized by the user.
- Once a QA session is authorized/started by the user:
  - Do NOT request individual manual approval or ask "Allow tap?", "Allow scroll?", "Allow command?", "Allow screenshot?" for each standard execution step.
  - Normal authorized actions include: terminal/ADB execution, app lifecycle (launch, close, relaunch), UI interactions (tap, scroll, swipe, back, input), UI inspection, screencap, log extraction, test verification, and result aggregation.
  - Reuse session-level authorization across the entire end-to-end QA execution without prompting redundant gates for routine operations.
  - If a platform-level tool confirmation dialog is mandated by the Antigravity host security system, request the minimum required approval once and persist that authorization for the ongoing session.

## 7. Strict Jira Steps Verbatim Device Traversal (Zero Deviation Rule)
- When a Jira ticket contains "Steps to Reproduce", "Steps", or test instructions in its description:
  - The agent MUST extract and follow those exact steps on the device sequentially and verbatim.
  - DO NOT guess or take ad-hoc shortcuts (e.g. clicking random home screen tiles) if the ticket specifies a defined navigation path.
  - Device execution must mirror each step in order:
    - Example: `Step 1: Open app` -> `Step 2: Search for <Model>` -> `Step 3: Go to Price tab` -> `Step 4: Click Service Cost Details`.
  - Clearly narrate each verbatim Jira step in the live chat log before executing it on device:
  - If a step in the ticket cannot be performed (e.g., button missing or screen blocked), stop immediately, capture evidence, and report the discrepancy.

## 8. Defect Detection, Bug Review List & Testing Bug Auto-Creation with Parent Linking
- **Step A (Bug Discovery & Evidence Capture):**
  - If any assertion fails, crash/ANR occurs, UI elements are broken, data is missing, or unexpected behavior is detected during QA execution:
  - Do NOT silently fail or mark as passed. Capture clear screenshot/logcat evidence immediately.
- **Step B (Bug Review List Presentation):**
  - Present a structured **Bug List** directly in the chat for user review before creating anything in Jira:
    - **Bug Title / Summary** (concise, standardized format)
    - **Severity / Priority** (Blocker / Critical / Major / Minor)
    - **Environment / Device** (e.g. OnePlus CPH2585, Android 14, Testing/Staging)
    - **Steps to Reproduce** (numbered verbatim steps)
    - **Expected vs Actual Result**
    - **Evidence Screenshot / Log**
- **Step C (Explicit Approval Gate):**
  - Ask user explicitly:
    > *"Found defect(s) during testing. Kya in bugs ko Jira mein 'Testing Bug' create karke parent ticket se link karna hai? (Approve / Reject / Edit)"*
- **Step D (Auto-Creation & Parent Linking):**
  - Once user approves (e.g. "approve", "create bug", "yes"):
    1. Create the issue in Jira with issue type **Testing Bug** in the relevant project (e.g., `MB2C`).
    2. Attach the captured screenshot/log evidence to the newly created Testing Bug.
    3. Link the Testing Bug to the parent Jira ticket via Jira issue linking (`relates to` / `is tested by` / `blocks`).
    4. Provide the clickable Jira link of the created Testing Bug and confirm the link to the parent ticket.

## 9. Dynamic Self-Training & Coordinate Knowledge Memory (Zero Latency Execution)
- The agent maintains a persistent, continuously updated knowledge base at `.agents/skills/jira-ai-qa-orchestrator/knowledge/learned_memory.json`.
- Device hardware profiles, screen resolutions, validated UI coordinates (Hamburger, Search, Change URL, Variant cards, Tabs, Sticky CTAs), and package mappings are cached.
- **Zero Guesswork / Instant Navigation:** Whenever executing on known devices (e.g. OnePlus 12R `CPH2585`), the agent uses pre-trained coordinates immediately without repetitive trial-and-error discovery.
- **Continuous Feedback Loop:** Any newly discovered UI coordinates, changed element positions, or newly validated server environments must be stored back into `learned_memory.json` during execution.

## 10. Zero-Popup Fast-Track Autonomous Driver Protocol
- To prevent annoying host IDE tool permission popups and command interruptions:
  - **Strictly NEVER execute chained raw shell commands** with complex inline pipes, semicolons, or nested loops directly in PowerShell `run_command` (e.g. `adb ...; Start-Sleep ...; python ...`).
  - **Always use atomic, self-contained Python runner modules** (such as `modules/execution/fast_runner.py` or pre-written scratch runners).
  - Single-command execution ensures zero host approval dialogs, instant execution speed, robust error trapping, and 100% clean binary screenshot extraction.

## 11. Mandatory App Server URL Verification & Auto-Sync Protocol
- In every Android App QA session:
  - **Before running any feature test cases on device**, always verify which server the App is pointing to:
    1. Navigate to **Hamburger Menu > CHANGE URL**.
    2. Inspect `BASE URL` and `BASE API URL` against the user's intended target server (e.g., `testingpwa1`, `testingpwa2`, `staging`).
    3. If already matching: proceed directly with testing.
    4. If different: automatically clear fields (`Ctrl+A` / backspaces), enter target endpoints, dismiss keyboard, tap **UPDATE**, verify `"Updated Successfully"` toast, and return to Home.
  - If the user has not specified a target server, proactively ask: *"App testing kis server par karni hai? (e.g. testingpwa1 / testingpwa2 / staging)"* before executing tests.

## 12. Standard Server Matrix & Domain Routing (CarDekho & BikeDekho)
- **CarDekho**:
  - **Testing**: `testingpwa1`, `testingpwa2`, and so on
    - Base URL: `https://<server>.cardekho.com` (e.g. `https://testingpwa1.cardekho.com`)
    - Base API URL: `https://<server>.cardekho.com/api`
  - **Staging**: `https://staging.cardekho.com`
    - Base API URL: `https://staging.cardekho.com/api`
  - **Live / Production**: `https://www.cardekho.com`
- **BikeDekho**:
  - **Testing**:
    - **API Testing**: `testingapi1`, `testingapi2`, and so on (e.g. `https://testingapi1.bikedekho.com`, `https://testingapi2.bikedekho.com`)
    - **PWA Testing**: `testing1`, `testing2`, and so on (e.g. `https://testing1.bikedekho.com`, `https://testing2.bikedekho.com`)
  - **Staging**:
    - **PWA Staging**: `https://alpha.bikedekho.com`
    - **API Staging**: `https://alphaapi.bikedekho.com`
  - **Live / Production**: `https://www.bikedekho.com`
- **Missing Branch Protocol**:
  - Whenever a Jira ticket lacks a branch, present the appropriate options based on brand (CarDekho vs BikeDekho) using the matrix above.

## 13. Girnar-2024-v1 Workflow & Automatic Status Transition on QA Sign-Off
- **Girnar-2024-v1 - Workflow - Story Architecture**:
  - `CREATE TICKET` -> `DESIGN REQUIRED` / `IN DESIGN` / `DESIGN IN REVIEW` -> `PRIORITIZE`
  - `DEV IN PROGRESS` -> `CODE REVIEW` -> `DEV COMPLETE`
  - `PENDING DEPLOYMENT` -> `SANITY TESTING` -> **`IN QA`**
  - **`IN QA` Transitions**:
    - **QA Sign-Off (PASS)**: Automatically transition via **`QA Complete`** (ID: 111) -> Target Status: **`IN UAT`**.
    - **QA Rejection (FAIL / Defect)**: Transition back to **`DEV IN PROGRESS`** and create/link `Testing Bug`.
    - **Blocker / Dependency**: Transition to **`ON-HOLD`** (ID: 501).
  - **`IN UAT` Transitions**:
    - **UAT Sign-off**: Transition via **`Dev Done`** (ID: 421) -> Target Status: **`DEV DONE`**.
  - **Release / Closure**:
    - Global transitions (`All`): **`CLOSED`** (ID: 271), **`CANCELLED`** (ID: 331), **`DUPLICATE`** (ID: 321).
- **Mandatory User Approval for Status Transitions**:
  - Never execute any Jira status transition automatically.
  - Present the proposed status change to the user and request explicit confirmation before triggering any Jira transition.

## 14. Real-Time Parallel Device Action Execution & Live Feedback Mirroring
- Whenever testing actions, gestures, clicks, navigation, or verifications are triggered:
  - All actions MUST execute in real-time, live and parallelly directly on the physically connected device via ADB without artificial delays, background blocking, or detached simulation.
  - The agent must mirror live execution states directly into the session with immediate screencaps and live progress updates as each device event occurs.
  - No disconnected mocking: every single step narrated in the chat must correspond to an actual ADB event running on the attached physical hardware.

## 15. Target App Identification & Mandatory Foreground Package Verification Protocol
- **Step 1 (Brand Identification):** Identify brand/project from Jira ticket (`CarDekho` vs `BikeDekho`).
- **Step 2 (Package Selection):** Select package according to brand and build variant:
  - CarDekho QA: `com.girnarsoft.cardekho.qa` (or `com.girnarsoft.cardekho` for Live/Prod as configured).
  - BikeDekho QA: `com.bikedekho.android` (or configured BikeDekho QA package).
- **Step 3 (Zero Foreground Assumption):** NEVER assume the currently open or foreground app is the target app.
- **Step 4 (Explicit Launch):** Explicitly launch the target package via explicit Intent/Component (`am start -n <package>/<activity>`).
- **Step 5 (Immediate Verification):** Immediately verify foreground state via:
  `adb shell dumpsys activity activities` (or `dumpsys window displays`).
- **Step 6 (Foreground Package Extraction):** Extract `mCurrentFocus` / `mFocusedApp` / `topResumedActivity` package.
- **Step 7 (Strict Comparison):**
  Compare: `expected_package == actual_foreground_package`.
- **Step 8 (If MATCH):**
  Continue testing smoothly.
- **Step 9 (If NOT MATCH):**
  - Immediately STOP execution of test steps.
  - Close / force-stop / return from the wrong app.
  - Retry target app launch with a bounded retry count (max 2 retries).

## 16. Mandatory Physical Mobile Device Verification (Anti-Shortcut Mandate)
- **Zero Python/Curl Backend Mocking for UI & End-to-End QA:**
  - Strictly FORBIDDEN to claim a test PASSED or FAILED solely by inspecting backend raw HTML, cURL diffs, or headless requests when mobile/WAP/App verification is requested.
  - Every UI, WAP, or Mobile App task MUST run directly on the physically connected Android hardware (e.g. OnePlus 12R `CPH2585`).
  - Required device steps:
    1. Wake up & unlock device via ADB.
    2. Open target app or Chrome browser on device explicitly.
    3. Navigate to the exact URL / flow.
    4. Perform actual live swipe/scroll/click events.
    5. Capture live screencaps as irrefutable visual evidence.
  - If a device is not connected or screen cannot be traversed, the test MUST be marked **BLOCKED / DEVICE_DISCONNECTED**, never falsely signed off via backend script.

## 17. Mandatory Pre-Check Summary & Zero-Server-Assumption Protocol
- **A. Server Selection (Zero Guesswork):**
  - NEVER pick, guess, or assume a target server (e.g. `testingpwa6`, `testingpwa1`, `testingapi2`) from past conversation memory or random default.
  - Check Jira comments and Jenkins deployment first.
  - If server is unconfirmed or multiple servers exist, ALWAYS ask the user explicitly before initiating any testing:
    *"Is task ki branch kis server par deployed hai? (e.g. testingpwa1 / testingpwa2 / testingpwa6 / testingapi2 / staging)"*
- **B. Pre-Check Summary Banner:**
  - Before running a single command on device or server, the skill MUST output the structured **[PRE-CHECK SUMMARY]** in chat:
    ```markdown
    ════════════════════════════════════════════════════════════════════
    📋 [PRE-CHECK SUMMARY] Jira Task Scope & Impact Analysis
    ════════════════════════════════════════════════════════════════════
    • Ticket: <KEY> - <Summary>
    • Target Server: <Server URL> (Confirmed / Pending confirmation)
    • Scope Type: <Web / WAP / Mobile App / API>
    • Expected Impact: <Should change reflect in App/WAP or is it excluded/regression check?>
    • Execution Plan: <Specific pages/flows to test on physical device>
    ════════════════════════════════════════════════════════════════════
    ```
- **C. Developer Comment vs Business Scope Validation:**
  - Never blindly treat a developer's comment (e.g. "App is excluded") as product truth without cross-checking against the Jira ticket summary and description.
  - If Jira mandates a global change and Dev excluded a platform (e.g. App), proactively flag the discrepancy to the user as a potential functional defect.

## 18. Mandatory Upfront Test Case Generation & Strict Execution Mapping Protocol
Whenever a Jira task/ticket is received or selected for testing:
1. **Immediate Deep Analysis**:
   - The agent MUST immediately inspect and analyze the Jira ticket's Summary, Description, Acceptance Criteria, Scope, Target Platform (App/WAP/Web/API), and any explicit Design or Exclusion notes.
2. **Upfront Comprehensive Test Case Generation**:
   - BEFORE triggering device actions, the agent MUST generate a structured, numbered Test Case Suite (`TC-01`, `TC-02`, ... `TC-N`) covering all relevant aspects of the Jira requirements:
     - **Positive / Happy Path Scenarios** (e.g. valid entry, successful navigation, correct default data)
     - **Negative & Edge Cases** (e.g. invalid inputs, deselecting filters, rapid taps, offline/retry)
     - **Boundary & Limit Values** (e.g. slider extremes, count limits, zero/max data)
     - **UI/UX & Layout Assertions** (e.g. contrast, alignment, spacing, typography, badges)
     - **Functional & Business Logic** (e.g. dynamic calculations, status flags, pricing, CTAs)
     - **Explicit Design Exclusions** (e.g. asserting that legacy or excluded sections are strictly absent)
     - **Cross-Brand / Cross-Variant Sanity** (e.g. verifying consistent architecture across multiple active brands or car models)
     - **Surrounding Regression Checks** (e.g. global search, back navigation, drawer retention)
3. **Structured Chat Presentation**:
   - Present this complete Test Case Suite directly in the chat window in a clear table:
     `| TC ID | Type / Category | Scenario / Test Description | Preconditions & Inputs | Expected Result |`
4. **Strict Execution Binding (Zero Deviation)**:
   - On-device test traversal and assertions in `[Step 5]` MUST execute strictly according to these generated test cases.
   - The agent must narrate each active test case explicitly before/during execution:
     - `[Step 5] Executing TC-01: ...`
     - `[Step 5] Executing TC-02: ...`
5. **Deterministic Sign-Off Mapping**:
   - The final Sign-off report in chat and the comment posted to Jira MUST report the exact status (`PASS` / `FAIL` / `BLOCKED`) for every single generated test case with linked visual screencap evidence.

## 19. Senior QA Jira Testing Flow & Core Lifecycle Sequence
For every Jira task, follow this exact sequence:

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

## 20. Device Resilience & Self-Healing Execution Protocol
To ensure 100% zero-flakiness across real hardware devices and Android OS versions (e.g. Android 14 / ColorOS):
- **Overlay Sweeper**: Automatically intercept and clear intrusive 3rd-party overlays (e.g. `com.truecaller`) or in-app promo/rating modal dialogs ("Not now", "Dismiss", "Cancel") before and during test execution.
- **Deterministic Keyboard Dismissal**: Always verify software keyboard state via `dumpsys input_method` (`mInputShown`); automatically dismiss via escape/back key after input actions to prevent CTA occlusion.
- **Dynamic Element Bounds Resolver**: Dynamically compute element centers `((x1+x2)//2, (y1+y2)//2)` from UI hierarchy dumps (`uiautomator dump`) when fixed coordinate targets are ambiguous or resolution changes.
- **Deterministic Shimmer Polling**: Poll UI text and hierarchy until loading shimmers clear and real screen content renders; never assert against blank/loading views.
- **Logcat Fatal Exception Sniffer**: Inspect logcat for `FATAL EXCEPTION`, `NullPointerException`, and `ANR` signatures for the target package before marking any test as PASSED.

## 21. QA Execution & Sign-off Rules (Strict Verification & Report Architecture)
- **Zero Happy-Path Assumption**: Never mark a Jira ticket PASS based only on happy-path UI validation.
- **AC-to-Scenario Mapping**: Map every Acceptance Criterion to at least one executed test scenario.
- **Impact & Regression**: Perform impact analysis and test relevant regression areas.
- **Comprehensive Scenarios**: Cover positive, negative, boundary, error, loading, empty-data, and network-failure scenarios where applicable.
- **API & Data Integrity**: For API-driven features, validate API status, response structure, data correctness, error handling, and UI/API data consistency.
- **Device & Compatibility**: Validate relevant device, OS, navigation, permissions, and compatibility scenarios.
- **Objective Evidence**: Collect objective evidence for important assertions: screenshots, logs, API responses, test data, and reproduction steps.
- **Honest Coverage Claim**: Do not claim **“100% Test Case Coverage”** unless all identified requirements, acceptance criteria, and planned scenarios are actually executed and passed.
- **Scope Clarity**: Clearly separate **tested scope** from **untested/out-of-scope areas**.
- **Deterministic Final Status**: Final status must be one of: **PASS, FAIL, BLOCKED, or PARTIAL**, with supporting reason and evidence.
- **Sign-off Prerequisite**: QA sign-off should be given only after functional validation, applicable regression, defect retesting, and evidence verification are complete.

**Final Report Structure:**
`Requirement/AC → Test Coverage → Execution Results → API/Data Validation → Regression → Defects → Evidence → Untested Scope → Final QA Status`

## 22. Zero Cached-Run Assumption & Mandatory Fresh Execution Protocol
- **Strict Prohibition on Reusing Past Summaries:**
  - Whenever the user asks to test or re-test a Jira ticket (e.g. `TEST MB2C-XXXX` or `test this`), the agent MUST NEVER synthesize, pass, or report test results based on `<CONTEXT_SUMMARY>`, previous conversation history, or previously captured screenshots.
  - Every single test request mandates a **100% fresh, live execution on the physical device from Step 1 to Step 6**.
- **Real-Time Live Device Execution:**
  - The agent must wake the device, launch the app, dynamically generate fresh test cases, navigate and execute each test scenario live via ADB, and capture brand-new timestamped evidence.
  - If a device is disconnected or unavailable, immediately halt and report `BLOCKED / DEVICE_DISCONNECTED` instead of falling back to cached results.

## 23. QA Coverage Accuracy & Honest Metrics Rule
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

## 24. WAP Reference Testing Rule (Implement in App Same as WAP Standard)
- **Reference Behavior Definition:**
  When a Jira ticket specifies **“Implement in App same as WAP”** (or equivalent), the WAP implementation MUST be treated as the ground-truth reference behavior.
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

## 25. Reference Jira Based Testing Protocol
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

## 26. Mandatory User Confirmation Before Any Jira Comment or Status Transition (Zero Unconfirmed Jira Action Rule)
- **Strict Prohibition on Unconfirmed Jira Comments:**
  - The QA agent is **STRICTLY FORBIDDEN** to post any comment (QA Sign-off, test results, defect details, progress notes) to any Jira ticket without first presenting the complete draft directly in the chat for user review.
  - The agent MUST explicitly ask:
    > *"Maine ye comment draft kiya hai. Kya ise Jira ticket <KEY> par post karein? (Approve / Reject / Edit)"*
  - The agent MUST NEVER call the Jira comment API until the user explicitly provides confirmation (e.g. "yes", "post", "approve", "done").
- **Strict Prohibition on Unconfirmed Status Transitions:**
  - The agent MUST NEVER execute any status transition in Jira (e.g. `QA Complete`, `Dev Complete`, `Dev In Progress`, `Closed`, `On-Hold`) automatically or without explicit user permission.
  - Always present the proposed status change and ask:
    > *"Kya ticket <KEY> ka status '<Target Status>' par transition karein? (Approve / Reject)"*
  - Only execute the transition upon receiving unambiguous user approval.

# 🚀 CarDekho & BikeDekho Enterprise QA Orchestration Skills

An enterprise-grade, agentic AI Quality Assurance suite engineered for **CarDekho** and **BikeDekho** mobile apps (Android) and Web/WAP platforms. Integrates directly with physical mobile hardware via ADB, Jira REST API v2, and Jenkins CI/CD pipelines.

---

## 📦 Skills Included in this Suite

| Skill Name | Purpose & Capabilities |
|---|---|
| **`jira-ai-qa-orchestrator`** | Autonomous QA engine: analyzes assigned Jira tasks, generates comprehensive test cases, executes 1-by-1 physical device traversal via ADB, enforces deterministic UI assertions, and manages Jira defect/sign-off lifecycle. |
| **`cardekho-api-inventory-generator`** | Automated API exploration & runtime capture: explores user flows, logs network endpoints, normalizes dynamic URLs, and produces multi-sheet Excel/JSON inventories. |
| **`deeplink-discovery-validator`** | Deep link auditor: parses Android Manifests and web assetlinks, executes deep link intents on physical devices, and validates landing screen states. |
| **`jira-bug-creator`** | 1-Click defect creator: converts device screenshots and logs into standardized Jira Prod/Testing Bugs with reproduction steps and parent linking. |
| **`jira-pod-comment-tracker`** | Multi-POD task tracker: synchronizes comments and status updates across CarDekho & BikeDekho tracking boards and spreadsheets. |
| **`qa-release-signoff-helper`** | Release assistant: aggregates testing reports across tickets, prepares release summaries, and crafts Gmail release draft communications. |

---

## 🛡️ Core QA Protocols & Operating Principles

The orchestration engine operates under 26 strict protocols defined in [`GEMINI.md`](./GEMINI.md):

1. **Zero Unconfirmed Jira Actions (Rule 26)**: No Jira comments or status transitions are executed without prior draft presentation and explicit human QA approval in chat.
2. **Mandatory Physical Device Verification (Rule 16)**: All mobile app testing runs live on connected hardware (e.g. OnePlus 12R `CPH2585`) with timestamped screenshots. Zero mock-only sign-offs.
3. **Target Server Auto-Configuration (Rules 11 & 12)**: Deterministically configures and verifies testing servers (`Live`, `testingpwa1`, `testingpwa2`, `staging`) via in-app `Hamburger > CHANGE URL`.
4. **Defect Management & Parent Linking (Rule 8)**: Automatically formats defects, captures failure evidence, and creates linked `Testing Bug` issues upon QA approval.
5. **WAP Parity & Reference Jira Architecture (Rules 24 & 25)**: Evaluates parity against WAP behaviors and linked Reference Jira specifications (e.g. `DB2C-XXXX`).
6. **Self-Healing Device Resilience (Rule 20)**: Automatically dismisses intrusive 3rd-party overlays, promo popups, and keyboards to maintain test stability.

---

## 🛠️ Technology Stack

- **Platform**: Python 3.12+
- **Device Control**: Android ADB (Android Debug Bridge), UIAutomator
- **Issue Tracking**: Atlassian Jira REST API v2
- **Testing & Verification**: Pytest (51 Unit & Integration Tests)
- **Target OS**: Android 14+ (ColorOS / OxygenOS / Stock Android)

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.12+ installed
- Android SDK Platform-Tools (`adb`) on system PATH
- Physical Android device connected with USB Debugging enabled

### 2. Run Test Suite
```bash
pytest .agents/skills/jira-ai-qa-orchestrator/tests
```

### 3. Verification
Verify connected device:
```bash
adb devices
```

---

## 📄 License & Confidentiality
Internal Quality Assurance tooling for GirnarSoft / CarDekho / BikeDekho.

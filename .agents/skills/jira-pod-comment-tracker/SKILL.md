---
name: jira-pod-comment-tracker
description: >-
  Enterprise Jira Pod Comment & Task Tracker for CarDekho & BikeDekho. Use whenever the user wants to comment on any Jira task or save/track Jira task IDs across POD columns in Google Sheets (https://docs.google.com/spreadsheets/d/1PuV4A8jCO5wMW7-Aih27688UA6aooP1z7v9gK7K2nvM/edit?usp=sharing) and Excel:
  - DB2C project tasks -> CarDekho column
  - BDCV project tasks -> BikeDekho Web column
  - MB2C project tasks -> CD App <Android & iOS> column (if CarDekho related) or BD App <Android & iOS> column (if BikeDekho related)
  Maintains formatted Excel (.xlsx), CSV, and 1-Click Google Apps Script / Webhook synchronization.
---

# Enterprise Jira Pod Comment & Task Tracker (CarDekho & BikeDekho)

You are an **Enterprise Jira Pod Comment & Task Tracker** for **CarDekho** and **BikeDekho**.

Your job is:
1. When the user asks to comment on any Jira task, post the comment to Jira via REST API.
2. Automatically classify the task into its relative POD column matching the team's official Google Sheet:
   - **`DB2C`** Project $\rightarrow$ **`CarDekho`** column
   - **`BDCV`** Project $\rightarrow$ **`BikeDekho Web`** column
   - **`MB2C`** Project (CarDekho App related) $\rightarrow$ **`CD App  <Android & iOS>`** column
   - **`MB2C`** Project (BikeDekho App related) $\rightarrow$ **`BD App    <Android & iOS>`** column
3. Store and synchronize the Jira link in:
   - **Live Google Sheet**: [Google Sheets Tracker](https://docs.google.com/spreadsheets/d/1PuV4A8jCO5wMW7-Aih27688UA6aooP1z7v9gK7K2nvM/edit?usp=sharing)
   - **1-Click Google Apps Script Runner**: [`output/sync_google_sheet.js`](file:///c:/Users/Mohit%20Sharma/Documents/antigravity/silly-curie/output/sync_google_sheet.js)
   - **Local Excel Sheet**: [`output/jira_pod_tracker.xlsx`](file:///c:/Users/Mohit%20Sharma/Documents/antigravity/silly-curie/output/jira_pod_tracker.xlsx)
   - **Local CSV Sheet**: [`output/jira_pod_tracker.csv`](file:///c:/Users/Mohit%20Sharma/Documents/antigravity/silly-curie/output/jira_pod_tracker.csv)

---

## 1. Google Sheet Column Layout

The live Google Sheet uses the following exact 6 columns:

| Column Header | Source Jira Project / Detection |
| :--- | :--- |
| **`CarDekho`** | `DB2C-*` tickets |
| **`BikeDekho Web`** | `BDCV-*` tickets |
| **`ZigWheels`** | Zigwheels web tickets |
| **`CD App  <Android & iOS>`** | `MB2C-*` tickets related to CarDekho |
| **`BD App    <Android & iOS>`** | `MB2C-*` tickets related to BikeDekho |
| **`ZW App  <Android & iOS>`** | `MB2C-*` tickets related to ZigWheels |

*Values stored in cells are full Jira URLs e.g. `https://jira.girnarsoft.com/browse/DB2C-10268`.*

---

## 2. Trigger Scenarios

Activate this skill whenever the user says:
- *"Comment on Jira task `<KEY>`: <comment text>"* (e.g. `comment on DB2C-10148: verified and approved`)
- *"`<KEY>` pr comment kar do: <comment text>"*
- *"Save task `<KEY>` to pod tracker / google sheet"*
- *"Track `<KEY>`"*
- *"MB2C task par comment kiya hai use relative column me daal do"*
- *"Show me current POD columns / board"*

---

## 3. Execution Commands

### A. Post Comment & Track Jira Task
```powershell
python .agents/skills/jira-pod-comment-tracker/scripts/comment_and_track.py `
  --key "<JIRA_KEY>" `
  --comment "<Comment text>"
```

### B. Track Task (Without Posting New Comment)
```powershell
python .agents/skills/jira-pod-comment-tracker/scripts/comment_and_track.py `
  --key "<JIRA_KEY>"
```

### C. Track Multiple Tasks
```powershell
python .agents/skills/jira-pod-comment-tracker/scripts/comment_and_track.py `
  --keys "<KEY1>" "<KEY2>" "<KEY3>"
```

### D. View Current POD Board
```powershell
python .agents/skills/jira-pod-comment-tracker/scripts/comment_and_track.py --view
```

### E. Set Apps Script Webhook URL (For 100% Real-Time Automated Google Sheet Push)
```powershell
python .agents/skills/jira-pod-comment-tracker/scripts/comment_and_track.py --set-webhook "<WEB_APP_URL>"
```

---

## 4. Google Sheet Update Workflow

1. Whenever the script runs, it fetches the latest state of the Google Sheet, merges any existing entries, adds the new Jira URL in the correct column, and saves to local Excel/CSV.
2. It automatically writes the updated code to [`output/sync_google_sheet.js`](file:///c:/Users/Mohit%20Sharma/Documents/antigravity/silly-curie/output/sync_google_sheet.js).
3. **To update Google Sheet with 1 click**:
   - Open Google Sheet $\rightarrow$ **Extensions** $\rightarrow$ **Apps Script**
   - Paste contents of [`output/sync_google_sheet.js`](file:///c:/Users/Mohit%20Sharma/Documents/antigravity/silly-curie/output/sync_google_sheet.js)
   - Click **Run `updateJiraPodBoard()`**.
4. **For 100% automated background updates (No copy-paste needed ever)**:
   - In Apps Script, click **Deploy** $\rightarrow$ **New deployment** $\rightarrow$ **Web app**.
   - Execute as: **Me**, Who has access: **Anyone**.
   - Copy Web App URL and run:
     `python .agents/skills/jira-pod-comment-tracker/scripts/comment_and_track.py --set-webhook "<WEB_APP_URL>"`
   - From then on, every comment or track command instantly pushes directly to Google Sheets!

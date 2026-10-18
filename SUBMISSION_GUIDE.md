# Salik's Submission Guide (zero to sent)

Delete this file before pushing to GitHub if you prefer; it is only for you. Time needed: about 2 to 3 hours.

## A. Install tools (Windows laptop, all free)
1. **Python**: python.org/downloads -> Download Python 3.12 -> run installer -> TICK "Add python.exe to PATH" -> Install Now.
2. **VS Code**: code.visualstudio.com -> Download for Windows -> install with defaults. Open it -> Extensions icon (four squares, left bar) -> search `Python` (Microsoft) -> Install.
3. **Git**: git-scm.com/download/win -> install with defaults.
4. **GitHub account**: github.com -> Sign up (username like `salik-hussain`). Verify your email.
5. Close all windows. Press Windows key, type `PowerShell`, open it, then run:
   ```
   python --version
   git --version
   ```
   Both must print a version. If not, restart the laptop and try again.

## B. Put the project on your laptop
1. Unzip `change-order-extractor.zip` into `Documents`. You should have `Documents\change-order-extractor`.
2. VS Code -> File -> Open Folder -> choose `change-order-extractor` -> Select Folder -> "Yes, I trust the authors".
3. Terminal -> New Terminal (VS Code, bottom panel). Run one at a time:
   ```
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements-dev.txt
   ```
   If PowerShell says scripts are disabled, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, press Y, then activate again.
   When it works you see `(.venv)` at the start of the line.
4. If VS Code asks to select an interpreter: Ctrl+Shift+P -> `Python: Select Interpreter` -> choose the one inside `.venv`.

## C. Run and understand it (do not skip: they may ask you about it)
```
python -m pytest -q
python -m change_order_extractor data
python -m change_order_extractor data\co_003.txt
python -m change_order_extractor.evaluate data\heldout evaluation\heldout_labels.json
```
Expected: `49 passed`. Open `outputs\co_003.json` in VS Code and read it. Read `TECHNICAL_WRITEUP.md` twice. Make it yours:
- Replace `YOUR-USERNAME` in README.md with your GitHub username.
- Add 2 or 3 NEW change-order text files in `data\` that you write yourself, run the tool, and note what breaks. Mention one real finding in your own words at the end of the write-up under "Notes from my testing". Genuine own work beats perfect polish.

## D. Optional: try the AI fallback (free)
1. Go to aistudio.google.com -> sign in -> "Get API key" -> create key. Never put the key in a file or on GitHub.
2. In the VS Code terminal:
   ```
   $env:GEMINI_API_KEY = "paste-key-here"
   python -m change_order_extractor data\heldout\h_01.txt --llm gemini
   ```
   `project_name` should now be filled with `"method": "llm"`. If you get an error, the model name may have changed: set `$env:GEMINI_MODEL = "gemini-2.5-flash"` (check the current name in Google AI Studio) and retry.
   This path was tested here only with a fake model, not a live API, so tell them exactly that if asked.

## E. Publish on GitHub
1. In the VS Code terminal:
   ```
   git init
   git add .
   git commit -m "Change-order extraction pipeline with validation, confidence and tests"
   ```
   If Git asks who you are:
   ```
   git config --global user.name "Salik Hussain"
   git config --global user.email "your-github-email@gmail.com"
   ```
   then run the commit again.
2. github.com -> `+` (top right) -> New repository.
   - Repository name: `change-order-extractor`
   - Description: `Validated JSON extraction with confidence scores from messy construction change orders (text and PDF)`
   - Public. Do NOT tick README, .gitignore or license (they already exist).
   - Create repository.
3. Copy the three lines GitHub shows under "push an existing repository" and run them:
   ```
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/change-order-extractor.git
   git push -u origin main
   ```
   Sign in in the browser window if asked.
4. Refresh the page: you should see README, a green check (tests) after a minute, and all folders.
5. Copy the address-bar URL. Open it in a private window to confirm it is public.

## F. The 1-minute recording
Read the passage exactly as written in their email. It is about 100 words, so a calm pace is roughly 45 to 60 seconds. Not rushing matters more than hitting exactly 60.
- Phone: **Voice Recorder** (Android) or **Voice Memos** (iPhone). Quiet room, phone about 20 cm from your mouth, close windows and fans.
- Practise the whole passage 2 to 3 times. Words to practise: carpenters, electricians, plumbers, organized, proof.
- Pause at full stops. Smile slightly; it improves tone. Record, listen back fully, redo if noisy or you stumble.
- Send it to yourself on WhatsApp Web or email, download to the laptop. `.m4a` or `.mp3` is fine (keep under 10 MB).

## G. Send
Gmail -> open the thread "Re: AI Engineer Role - Sledge" -> Reply. Paste the email below, attach the audio with the paperclip, check the repo link works, Send.

```
Hello Sledge Team,

Please find my submission for the AI Engineer role.

1. Repository (code, tests, sample data, results):
   https://github.com/YOUR-USERNAME/change-order-extractor
2. Technical write-up (approach, confidence scoring, failure modes):
   https://github.com/YOUR-USERNAME/change-order-extractor/blob/main/TECHNICAL_WRITEUP.md
3. One-minute English recording: attached.

Summary: a rule-based pipeline with an optional, evidence-grounded LLM fallback. It returns validated JSON with
per-field confidence and the supporting text, and flags ambiguous or missing data for review instead of guessing.
It has 49 automated tests. On 6 held-out documents it scored 92% field accuracy on the first run; the known failure
modes (scanned PDFs, tables, title-only project names) are documented.

I would also appreciate confirmation that the role is open to applicants based in Pakistan, and the expected working
hours and employment terms.

Best regards,
Salik Hussain
```

## H. Safety (still true)
They have not answered your questions about Pakistan eligibility, hours, and terms. Look for a real website and named people. Never pay anything. Never send passport, ID, bank details or passwords. If they ask for any, stop and tell me.

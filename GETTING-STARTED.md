# Run LinguaSI on your computer

This guide gets the whole of LinguaSI running on your own Windows, Mac or Linux computer:

- **the website** (the main app) at http://localhost:3000
- **the mobile app**, shown in your browser, at http://localhost:8081
- **the API** with its documentation at http://localhost:8000/docs
- a **demo learner** with four weeks of history, so every screen has something to show

You only install one program, **Docker Desktop**. You do not need Python, Node.js, a database or Git:
Docker downloads and runs all of that for you, in its own containers. Nothing else on your computer
is changed. LinguaSI runs in **Mock AI Mode**, so no AI account, key or payment is needed.

The first start takes 5–15 minutes (Docker downloads and builds everything). After that, LinguaSI
starts in about a minute.

**Contents**

1. [Install Docker Desktop](#1-install-docker-desktop)
2. [Download LinguaSI](#2-download-linguasi)
3. [Start LinguaSI](#3-start-linguasi)
4. [Use LinguaSI](#4-use-linguasi)
5. [Stop, restart, update or reset](#5-stop-restart-update-or-reset)
6. [Optional: real AI feedback](#6-optional-real-ai-feedback)
7. [If something goes wrong](#7-if-something-goes-wrong)

**What your computer needs:** Windows 10 or 11, a recent macOS, or Linux; 8 GB of memory (RAM)
or more; about 10 GB of free disk space; an internet connection for the first start.

---

## 1. Install Docker Desktop

Skip this step if Docker Desktop is already installed. Open it and check that it says
**Engine running** (bottom-left corner of its window).

### Windows

1. Go to https://www.docker.com/products/docker-desktop/ and click **Download for Windows**.
   Most computers need the **AMD64** version. Choose **ARM64** only if your laptop has a
   Snapdragon processor (Settings → System → About → "System type" says "ARM-based processor").
2. Open the downloaded `Docker Desktop Installer.exe`. Keep the option **Use WSL 2** ticked and
   click **OK**. When the installer finishes, click **Close and restart** (or restart the computer
   yourself).
3. After the restart, open **Docker Desktop** from the Start menu. Accept the agreement (it's free
   for personal use). You can skip signing in and skip the survey.
4. Wait until the bottom-left corner of the Docker Desktop window shows **Engine running**. The first
   time this can take a few minutes.

If Docker Desktop shows an error about **WSL** or **virtualization** instead, see
[Docker Desktop doesn't start](#docker-desktop-doesnt-start-windows).

### Mac

1. Find out which chip your Mac has: Apple menu  → **About This Mac**. "Chip: Apple M…" means
   Apple silicon; "Processor: … Intel …" means Intel.
2. Go to https://www.docker.com/products/docker-desktop/ and download Docker Desktop for
   **Apple silicon** or **Intel chip** to match.
3. Open the downloaded `Docker.dmg` and drag **Docker** into **Applications**.
4. Open **Docker** from Applications. Confirm that you want to open it, accept the agreement, enter
   your Mac password if asked, and skip signing in.
5. Wait until the Docker Desktop window shows **Engine running**.

### Linux

Install Docker Engine with the Compose plugin by following https://docs.docker.com/engine/install/
for your distribution (or install Docker Desktop for Linux). Then let your user run Docker without
`sudo`, and log out and back in:

```sh
sudo usermod -aG docker $USER
```

---

## 2. Download LinguaSI

**Option A: download a ZIP (easiest, no Git needed)**

1. Open https://github.com/Adnan121129/LinguaSI.
2. Click the green **Code** button, then **Download ZIP**.
3. Unzip it:
   - **Windows:** right-click the ZIP file → **Extract All…** → **Extract**. Use the extracted
     folder, not the ZIP itself: scripts can't run from inside a ZIP.
   - **Mac:** double-click the ZIP file.
4. You now have a folder called **`LinguaSI-main`**. You can move it anywhere, for example into
   Documents.

**Option B: with Git**

```sh
git clone https://github.com/Adnan121129/LinguaSI.git
```

This creates a folder called **`LinguaSI`**.

---

## 3. Start LinguaSI

### Windows

1. Open the LinguaSI folder.
2. Double-click **`start-windows.bat`**.
   - If Windows asks whether to run it, click **Run**. If a blue window says "Windows protected your
     PC", click **More info** → **Run anyway**. The file is a short, readable script (open it with
     Notepad to see exactly what it does).
   - If file extensions are hidden, the file is shown as **start-windows** with a gear icon.
3. A black window opens and shows the progress. Leave it open. The first start downloads and builds
   everything, which takes 5–15 minutes; you'll see many lines scroll by.
4. When it says **LinguaSI is running**, the website opens in your browser.

### Mac

1. Open **Terminal**: press `Cmd + Space`, type `Terminal` and press Enter.
2. Type `sh` followed by **a space** (don't press Enter yet).
3. Drag the **`start.sh`** file from the LinguaSI folder in Finder into the Terminal window. Its full
   path appears after `sh `.
4. Press **Enter**. The first start takes 5–15 minutes. When it says **LinguaSI is running**, the
   website opens in your browser.

### Linux

Open a terminal in the LinguaSI folder and run:

```sh
sh start.sh
```

### What the start script does

The script is safe to run again at any time, for example after restarting your computer. Each time
it:

1. checks that Docker is installed and running, and starts Docker Desktop if it isn't;
2. removes containers left over from an earlier start (your data is kept);
3. checks that ports 3000, 8000 and 8081 are free;
4. builds and starts the four parts of LinguaSI: the database, the API, the website and the mobile
   app preview, and waits until they are ready;
5. creates the demo learner (only the first time);
6. opens the website.

If anything goes wrong, it stops with a message that starts with **PROBLEM:** and says what to do.
The most common problems and fixes are in [section 7](#7-if-something-goes-wrong).

---

## 4. Use LinguaSI

| Open | Address |
| --- | --- |
| Website | http://localhost:3000 |
| Mobile app (browser preview) | http://localhost:8081 |
| API documentation (for developers) | http://localhost:8000/docs |

**Sign in with the demo learner** to see LinguaSI with four weeks of progress, essays, speaking
tests, mistakes and streaks:

- Email: `demo@linguasi.app`
- Password: `LinguaSI-demo-2026`

Or click **Create an account** to start as a new learner: you'll set your goal and take the
15-minute diagnostic.

**The mobile app preview** shows the phone app's screens in your browser, with the same account and
data as the website. For a phone-sized view in Chrome or Edge, press `F12`, then `Ctrl + Shift + M`
(`Cmd + Shift + M` on a Mac) and choose a phone at the top of the page. To run the app on a real
phone, see [mobile/README.md](mobile/README.md) (this needs Node.js).

**Mock AI Mode:** writing and speaking feedback, the tutor and generated practice all work, using
realistic built-in feedback instead of a paid AI service. Screens show a **Mock AI Mode** badge.
To use a real AI provider, see [section 6](#6-optional-real-ai-feedback).

---

## 5. Stop, restart, update or reset

**Stop LinguaSI** (your accounts and progress are kept):

- Windows: double-click **`stop-windows.bat`**
- Mac and Linux: `sh stop.sh` (the same way you ran `start.sh`)
- Or, in Docker Desktop: **Containers** → **linguasi** → the stop button

**Start it again:** run the start script again. It takes about a minute. If you didn't stop
LinguaSI, it starts by itself whenever Docker Desktop starts.

**Update to a newer version of LinguaSI:** download the ZIP again (or run `git pull`), then run the
start script from the new folder. It rebuilds what changed. Your data is kept, because it is stored
in Docker, not in the folder.

**Open a terminal in the LinguaSI folder** (for the commands below):

- Windows: open the folder in File Explorer, click the address bar, type `cmd` and press Enter.
- Mac: in Terminal, type `cd` and a space, drag the LinguaSI folder into the window, press Enter.

**Reset everything** (deletes all accounts and progress, then the next start begins fresh):

```sh
docker compose down -v
```

**Uninstall:** run `docker compose down -v --rmi local` in the LinguaSI folder, then delete the
folder. You can also uninstall Docker Desktop if you don't need it any more.

---

## 6. Optional: real AI feedback

You need an API key from Anthropic (Claude), OpenAI or Google (Gemini). The provider bills every
request: a Claude or ChatGPT chat subscription does **not** include API credits.

1. Open a terminal in the LinguaSI folder (see [section 5](#5-stop-restart-update-or-reset)).
2. Create your settings file from the template and open it:
   - Windows: `copy .env.example .env` then `notepad .env`
   - Mac: `cp .env.example .env` then `open -e .env`
   - Linux: `cp .env.example .env` then edit `.env` with any text editor
3. Change these lines (example for Claude) and save:

   ```ini
   AI_PROVIDER=anthropic
   AI_MOCK_MODE=false
   ANTHROPIC_API_KEY=your-key-here
   ```

4. Run the start script again.

The key stays inside the API container. It is never sent to the website or the mobile app.
`.env.example` explains the other settings.

---

## 7. If something goes wrong

Find the message you see below. After fixing the cause, run the start script again: it is always
safe to repeat.

### "Docker is not installed" or "'docker' is not recognized"

Install Docker Desktop ([section 1](#1-install-docker-desktop)). If you just installed it, restart
the computer once, open Docker Desktop, and run the start script again.

### Docker Desktop doesn't start (Windows)

- **An error about WSL** ("WSL needs updating", "WSL 2 installation is incomplete"): right-click the
  Start button → **Terminal (Admin)** or **Windows PowerShell (Admin)**, run `wsl --update` (or
  `wsl --install` if WSL is missing), then restart the computer.
- **"Virtualization support not detected"**: virtualization is switched off in your computer's
  firmware (BIOS/UEFI). Restart into the BIOS settings and enable **Intel Virtualization Technology
  (VT-x)** or **SVM Mode** (AMD). Search the web for "enable virtualization" with your computer's
  model for the exact keys.
- **Stuck on "Starting the Docker Engine"**: in Docker Desktop click the bug icon
  (**Troubleshoot**) → **Restart Docker Desktop**, or restart the computer.

### "Docker is not running" / "Docker Desktop is not running"

Open Docker Desktop and wait until it shows **Engine running**, then run the start script again.

### "Port 3000 is already used by another program" (or 8000, 8081)

Another program on your computer uses that port. Close it, or give LinguaSI a different port:

1. Create the settings file as in [section 6](#6-optional-real-ai-feedback), steps 1–2.
2. Change the port line, for example `WEB_PORT=3001` (or `API_PORT=8001`, `MOBILE_PORT=8082`), and
   save.
3. Run the start script again and use the new address, e.g. http://localhost:3001.

### "Ports are not available … forbidden by its access permissions" (Windows)

Windows has reserved that port for itself. Choose a port from a different range, as above (for
example `API_PORT=8800`). Alternatively, open **Terminal (Admin)** and run `net stop winnat` and
then `net start winnat`, which releases the reservations.

### The download or build fails: "failed to fetch", "timeout", "TLS handshake", "could not resolve"

Docker could not download something. Check your internet connection, switch off a VPN if you use
one, and run the start script again: it continues where it stopped. Behind a company proxy, enter it
in Docker Desktop → **Settings** → **Resources** → **Proxies**.

### "no space left on device"

Free some disk space. Docker can also delete its unused downloads and build files (your LinguaSI
data is kept):

```sh
docker system prune
```

### The build stops with "exit code: 137" or "killed"

Docker ran out of memory. Close other programs and run the start script again. On a Mac, give Docker
more memory in Docker Desktop → **Settings** → **Resources** (4 GB or more).

### "must run inside the LinguaSI folder" / "docker-compose.yml is missing" / "no configuration file provided"

The script was started from the wrong place, usually from inside the ZIP file. Extract the ZIP
first ([section 2](#2-download-linguasi)) and run the script from the extracted folder.

### "Your Docker Compose is too old" / "this version of Docker Desktop is too old" / "unknown flag: --wait"

Update Docker Desktop: click the gear icon (**Settings**) → **Software updates**, or install the
latest version from https://www.docker.com/products/docker-desktop/.

### "Your user is not allowed to use Docker" / "permission denied … docker.sock" (Linux)

Run `sudo usermod -aG docker $USER`, log out and back in, and run `sh start.sh` again.

### "Permission denied" when starting `start.sh` (Mac, Linux)

Start it with `sh start.sh` (as in [section 3](#3-start-linguasi)) rather than `./start.sh`.

### The website shows an error or doesn't load

If LinguaSI was only just started, wait half a minute and refresh the page. In Docker Desktop,
**Containers** → **linguasi** should list four running parts: `db`, `api`, `web` and `mobile`. If
one has stopped, run the start script again.

### The demo learner can't sign in

Create it with this command, in a terminal in the LinguaSI folder:

```sh
docker compose exec api python -m app.cli demo --if-missing
```

### Still stuck?

Save LinguaSI's recent messages to a file (in a terminal in the LinguaSI folder):

```sh
docker compose logs --tail 200 > linguasi-log.txt
```

The file contains no passwords or essay texts. Share it, together with what you did and the
message you saw, and the problem can usually be pinpointed from there.

---

Developers who prefer to run the API, website and mobile app without Docker will find those steps
in the [README](README.md#9-installation).

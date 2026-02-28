# Duepi EVO – Dev Container Documentation

This directory contains everything needed to run a **Home Assistant development environment** inside a VS Code Dev Container. The container provides a fully isolated, reproducible setup so you can develop, test and debug the `duepi_evo` custom component without touching your local machine.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Container Creation & Initialisation (`setup.sh`)](#container-creation--initialisation-setupsh)
3. [Starting Home Assistant](#starting-home-assistant)
4. [Available VS Code Tasks (CMD+P)](#available-vs-code-tasks-cmdp)
5. [Customisation](#customisation)
6. [File Structure Overview](#file-structure-overview)

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine on Linux)
- [Visual Studio Code](https://code.visualstudio.com/)
- VS Code extension: **Dev Containers** (`ms-vscode-remote.remote-containers`)

Open the repository folder in VS Code and click **"Reopen in Container"** when prompted, or run the command `Dev Containers: Reopen in Container` from the Command Palette (`CMD+P` / `Ctrl+P`).

---

## Container Creation & Initialisation (`setup.sh`)

### 1. Dockerfile (`Dockerfile`)

When the container is built for the first time, VS Code uses `.devcontainer/Dockerfile` to create the image. The following steps are performed at **build time**:

| Step | What happens |
|------|-------------|
| Base image | `mcr.microsoft.com/devcontainers/python:1-3.13` – a Debian-based image with Python 3.13 pre-installed |
| System packages | Installs `git`, `curl`, `build-essential`, `ffmpeg`, `libturbojpeg0-dev`, `libpcap-dev` |
| Python packages | Runs `pip install -r requirements_test.txt` (which itself includes `requirements_dev.txt`) to make all dependencies available at container startup |

The installed Python packages include `homeassistant`, `pytest-homeassistant-custom-component`, `pytest`, `coverage`, `pytest-asyncio`, and several HA-specific libraries.

### 2. Port forwarding

Port **8123** on the container is automatically forwarded to port **8123** on your host, so the Home Assistant UI is accessible at [http://localhost:8123](http://localhost:8123).

### 3. VS Code Extensions installed automatically

The following extensions are installed inside the container:

| Category | Extension |
|----------|-----------|
| Python | `ms-python.python`, `ms-python.pylint`, `ms-python.isort`, `ms-python.black-formatter` |
| GitHub | `github.copilot`, `github.copilot-chat`, `donjayamanne.githistory`, `waderyan.gitblame` |
| Utilities | `ferrierbenjamin.fold-unfold-all-icone`, `vscode.markdown-math`, `yzhang.markdown-all-in-one`, `bierner.markdown-mermaid` |

### 4. Post-create command: `setup.sh`

Immediately after the container is created, VS Code automatically runs `scripts/setup.sh`. This script performs **6 steps**:

| Step | Action |
|------|--------|
| **1/6** | Installs Python packages from `requirements_test.txt` into the user's site-packages (ensures latest versions) |
| **2/6** | Creates the `config/` directory (HA runtime config folder) and sets permissions to `777` |
| **3/6** | Creates a **symlink** `.devcontainer/configuration.yaml` → `config/configuration.yaml` so HA uses the versioned config |
| **4/6** | Creates a **symlink** `custom_components/duepi_evo` → `config/custom_components/duepi_evo` so HA loads the component directly from source |
| **5/6** | Creates a **symlink** `.devcontainer/lovelace_dashboards` → `config/.storage/lovelace_dashboards` for the Lovelace dashboard registry |
| **6/6** | Creates a **symlink** `.devcontainer/lovelace.dashboard_test` → `config/.storage/lovelace.dashboard_test` for the test dashboard |

> **Note:** All symlinks are idempotent – if they already exist the script silently skips them.

---

## Starting Home Assistant

When you start Home Assistant via `scripts/ha.sh start`, the following sequence is executed:

1. **Re-runs `setup.sh`** – ensures the environment is consistent (symlinks, packages).
2. **Launches `hass`** – starts Home Assistant with:
   - `--config config/` – points HA to the `config/` directory
   - `--debug` – enables debug-level logging for HA core

Home Assistant will then:
- Load `.devcontainer/configuration.yaml` (via the symlink in `config/`)
- Load `custom_components/duepi_evo` (via the symlink in `config/custom_components/`)
- Start the HTTP server on **0.0.0.0:8123**
- Enable the **debugpy** remote debugger on port **5678** (non-blocking, attach at any time)
- Set the log level to `warning` globally, but `debug` for `custom_components.duepi_evo`

The UI is available at [http://localhost:8123](http://localhost:8123) once HA has finished starting.

---

## Available VS Code Tasks (CMD+P)

Open the Command Palette with **`CMD+P`** (macOS) or **`Ctrl+P`** (Windows/Linux), then type **`task `** (with a space) to list all available tasks, or use the exact names below.

| Task label | Description |
|------------|-------------|
| `Home Assistant: Start` | Runs `setup.sh` then launches HA in debug mode. Runs in the background. |
| `Home Assistant: Stop` | Kills the running `hass` process. |
| `Home Assistant: Restart` | Stops HA, waits 2 seconds, then starts it again. |
| `Home Assistant: Install Dependencies` | Runs `pip install -r requirements_dev.txt`. |
| `Home Assistant: Run Tests` | Runs `pytest tests/ -v` to execute the test suite. |
| `Home Assistant: Format Code` | Runs `black` on `custom_components/` and `evo-python/` (line length 119). |
| `Home Assistant: Lint Code` | Runs `pylint` on `custom_components/duepi_evo/` and `evo-python/`. |

### How to run a task step by step

1. Press **`CMD+P`** (or **`Ctrl+P`**).
2. Type `task ` (note the trailing space) – VS Code will show the task picker.
3. Select the desired task and press **Enter**.

Alternatively, the **`Home Assistant: Start`** task is set as the **default build task**, so you can trigger it directly with **`CMD+Shift+B`** (or **`Ctrl+Shift+B`**).

---

## Customisation

### Change the pellet stove IP address

Edit `.devcontainer/configuration.yaml` and update the `host` field under the `climate` platform:

```yaml
climate:
  - platform: duepi_evo
    host: 192.168.1.86   # ← replace with your stove's IP address
    port: 2000
```

### Mount additional local directories

Open `.devcontainer/devcontainer.json` and add entries to the `mounts` array:

```jsonc
"mounts": [
    // existing mounts ...
    // Example: mount a local UI card's dist folder
    "source=${localEnv:HOME}/<directory>/my-ui-card/dist,target=/workspaces/Duepi_EVO/config/www/community/my-ui-card,type=bind"
]
```

### SSH keys for Git operations

By default the container mounts `~/.ssh` from your host so that SSH-based Git operations work out of the box. To disable this, comment out the corresponding line in `devcontainer.json`:

```jsonc
// "source=${localEnv:HOME}${localEnv:USERPROFILE}/.ssh,target=/home/vscode/.ssh,type=bind,consistency=cached"
```

### Adjust HA logging verbosity

Edit `.devcontainer/configuration.yaml`:

```yaml
logger:
  default: warning          # global level: debug | info | warning | error | critical
  logs:
    custom_components.duepi_evo: debug   # per-component override
```

### Lovelace dashboards

Versioned Lovelace dashboard files live in `.devcontainer/`:

| File / Folder | Description |
|---------------|-------------|
| `lovelace_dashboards` | Dashboard registry (list of dashboards) |
| `lovelace.dashboard_test` | Content of the `test` dashboard |

Edit these files directly – they are symlinked into `config/.storage/` and HA will pick up changes on the next reload.

### Recorder retention

The recorder is configured to keep only **1 day** of history (suitable for development). Adjust in `.devcontainer/configuration.yaml`:

```yaml
recorder:
  purge_keep_days: 1   # increase if you need more history
```

---

## File Structure Overview

```
.devcontainer/
├── Dockerfile                  # Container image definition
├── devcontainer.json           # VS Code Dev Container configuration
├── configuration.yaml          # Home Assistant configuration (symlinked into config/)
├── lovelace_dashboards         # Lovelace dashboard registry (symlinked into config/.storage/)
├── lovelace.dashboard_test     # Test dashboard content  (symlinked into config/.storage/)
└── README.md                   # This file

scripts/
├── setup.sh                    # Post-create initialisation script
└── ha.sh                       # HA start / stop / restart helper

config/                         # Runtime HA config (git-ignored, built by setup.sh)
├── configuration.yaml          # → symlink to .devcontainer/configuration.yaml
└── custom_components/
    └── duepi_evo               # → symlink to custom_components/duepi_evo/

custom_components/
└── duepi_evo/                  # Integration source code (edit here)
    ├── __init__.py
    ├── climate.py
    └── manifest.json
```

# 🌍 One Health Dashboard — Bettahalasuru

A science-driven, integrated data platform assessing the health of humans, animals, and the environment at the village interface — built on the **One Health** framework by the **Planetary Health Foundation**, an initiative of Equine Biotech, IISc.

---

## 📋 Overview

This dashboard provides a multi-pillar view of health data for rural villages in Karnataka, India. It integrates live environmental data (AQI, humidity), Google Sheets-backed health records, and an AI-powered chatbot assistant — all in a responsive Plotly Dash web application.

**Built by:** Martin Thomas, Alex Mathew Shaji, Teena Tomy, Jesvin Saji, Christina Biju, Thoshitha V, and Vaishnavi Dubey.

---

## 🗂️ Project Structure

```
.
├── app.py                      # Main Dash application (entry point)
├── patch_animal_static.py      # Utility script for patching animal static data
├── requirements.txt            # Python dependencies
├── assets/
│   └── bot.png                 # Chatbot avatar image
└── data/                       # Local Excel fallback data
    ├── human.xlsx
    ├── animal.xlsx
    ├── Environment.xlsx
    ├── interconnectedness.xlsx
    ├── overview.xlsx
    ├── Human-Village-2.xlsx
    ├── Animal-Village-2.xlsx
    ├── Environment-Village-2.xlsx
    ├── Interconnectedness-Village-2.xlsx
    ├── Overview-Village -2.xlsx
    ├── Human-Village-3.xlsx
    ├── Animal-Village-3.xlsx
    ├── Environment-Village-3.xlsx
    ├── Interconnectedness-Village-3.xlsx
    ├── Overview-Village-3.xlsx
    ├── Human-Village-4.xlsx
    ├── Animal-Village-4.xlsx
    ├── Environment-Village-4.xlsx
    ├── Interconnectedness-Village-4.xlsx
    └── Overview-Village-4.xlsx
```

---

## ✨ Features

### 📊 Dashboard Pillars
| Pillar | What It Shows |
|---|---|
| **Overview** | Village-wide KPIs — population, livestock, AQI, water sources, One Health surveillance radar |
| **Human Pillar** | PHC population stats, major diseases, vector-borne disease trends, screening programs, disease burden, antibiotic calibration |
| **Animal Pillar** | Stray dog ABC program, rabies projection (5-year), AMR antibiotic findings in livestock |
| **Environment Pillar** | Water quality (physicochemical + microbial), gram staining summary, soil microbial load, live AQI doughnut chart |
| **Interconnectedness** | Force-directed graph of One Health pathways, risk matrix, zoonotic transmission, rainfall–disease correlation, projected outcomes |

### 🤖 AI Chatbot (ONE Health Bot)
- Context-aware chatbot powered by a local Ollama/Gemma model via ngrok tunnel
- Answers questions using live dashboard data (population, AQI, diseases, water quality, etc.)
- Fetches live weather from aqi.in when weather-related questions are asked
- Scrapes PHF website content for institutional knowledge questions

### 🌐 Data Sources
- **Primary:** Google Sheets (fetched as CSV via gviz API)
- **Fallback:** Local `.xlsx` files in the `data/` directory
- **Live AQI & Humidity:** Scraped from https://www.aqi.in (cached for 10 minutes)
- **Live Weather:** Scraped from aqi.in weather page

### 🏘️ Multi-Village Support
Supports 4 villages with independent data sheets:
- Bettahalasuru (Village 1)
- Village 2
- Village 3
- Village 4

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- pip

### Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd <repo-folder>

# Install dependencies
pip install -r requirements.txt
```

> **Optional:** For live AQI scraping, `requests` and `beautifulsoup4` must be installed (both are included in `requirements.txt`). Without them, the app falls back to Google Sheets air quality data.

### Running the App

```bash
python app.py
```

The app will start in debug mode and be accessible at `http://127.0.0.1:8050`.

---

## 🤖 Chatbot Setup (Ollama + Gemma + ngrok)

The ONE Health Bot runs on a local AI model (Gemma) served through Ollama, and is made accessible to the dashboard via an ngrok tunnel. Follow all five steps below in order.

---

### Step 1 — Install Ollama

**Option A: Via Browser (Recommended)**
1. Open your browser and go to https://ollama.com/download
2. Download the installer for your OS (Windows / macOS / Linux)
3. Run the installer and follow the on-screen instructions
4. Once installed, Ollama runs as a background service automatically

**Option B: Via Terminal (Linux / macOS)**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

To verify Ollama is installed:
```bash
ollama --version
```

---

### Step 2 — Install the Gemma Model

1. Open a terminal (Command Prompt / PowerShell on Windows, Terminal on Mac/Linux)
2. Pull and install the Gemma model:

```bash
ollama pull gemma
```

> This downloads the Gemma model (~5 GB). Make sure you have a stable internet connection.

To verify the model is installed:
```bash
ollama list
```

You should see `gemma` in the list.

---

### Step 3 — Run Ollama with Gemma

Start the Ollama server (if it is not already running as a background service):

```bash
ollama serve
```

In a **second terminal**, run the Gemma model:

```bash
ollama run gemma
```

> You can type a test message to confirm it is working, then press `Ctrl+D` or type `/bye` to exit the interactive mode. The server will keep running in the background.

The Ollama API is now available at `http://localhost:11434`.

---

### Step 4 — Install ngrok and Get Your Auth Token

ngrok creates a public HTTPS URL that points to your local Ollama server, so the dashboard can reach it from any machine.

**Install ngrok:**

1. Go to https://ngrok.com/download
2. Download the installer for your OS (Windows / macOS / Linux)
3. Extract and place `ngrok` (or `ngrok.exe`) somewhere accessible, or add it to your system PATH

**Get your ngrok Auth Token:**

1. Go to https://dashboard.ngrok.com/signup and create a free account
2. After signing in, navigate to https://dashboard.ngrok.com/get-started/your-authtoken
3. You will see your personal auth token on that page — it looks like this:
   ```
   2abc1XYZexampleTokenHere_abcdefghijklmnopqrstuvwxyz
   ```
4. Copy the full token

**Add the auth token to ngrok** (one-time setup — run this once in terminal):

```bash
ngrok config add-authtoken 2abc1XYZexampleTokenHere_abcdefghijklmnopqrstuvwxyz
```

> Replace the token above with your actual token copied from the dashboard.

**Start the ngrok tunnel pointing to Ollama:**

```bash
ngrok http 11434 --host-header="localhost:11434"
```

ngrok will display output like this in the terminal:

```
Session Status    online
Account           your-email@gmail.com (Plan: Free)
Forwarding        https://exact-evoke-outgrow.ngrok-free.app -> http://localhost:11434
```

Copy the full forwarding URL shown after `Forwarding`, for example:
```
https://exact-evoke-outgrow.ngrok-free.app
```

---

### Step 5 — Add the ngrok URL into app.py

1. Open `app.py` in any text editor
2. Search for the function `ask_ollama()` (around line 400)
3. Find this block inside the function:

```python
response = requests.post(
    "https://exact-evoke-outgrow.ngrok-free.dev/api/generate",
    json={
        "model": "gemma",
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": 200,
            "temperature": 0.6,
            "top_p": 0.9,
        }
    },
    timeout=120
)
```

4. Replace the URL on the first line with your own ngrok forwarding URL:

```python
response = requests.post(
    "https://YOUR-OWN-NGROK-URL.ngrok-free.app/api/generate",   # ← paste your URL here
    json={
        "model": "gemma",
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": 200,
            "temperature": 0.6,
            "top_p": 0.9,
        }
    },
    timeout=120
)
```

5. Save `app.py`, then start the dashboard:

```bash
python app.py
```

The chatbot is now live and connected. 🎉

> **Important:** ngrok free-tier URLs change every time you restart ngrok. Each new session, copy the new URL from the ngrok terminal output and update the URL in `ask_ollama()` in `app.py` before running the dashboard. To avoid this, upgrade to a paid ngrok plan which gives you a fixed static domain.

---

### Chatbot Quick-Start Checklist

| Step | Command / Action |
|---|---|
| Install Ollama | Download from https://ollama.com/download or use `curl` install |
| Install Gemma model | `ollama pull gemma` |
| Start Ollama server | `ollama serve` |
| Get ngrok auth token | https://dashboard.ngrok.com/get-started/your-authtoken |
| Add auth token | `ngrok config add-authtoken <YOUR_TOKEN>` |
| Start ngrok tunnel | `ngrok http 11434 --host-header="localhost:11434"` |
| Update URL in app.py | Paste ngrok URL into `ask_ollama()` function |
| Run dashboard | `python app.py` |

---

## ⚙️ Configuration

### Google Sheets
Sheet IDs are configured in `app.py` under `SHEETS` and `VILLAGE_CONFIG`. Each village maps to five Google Sheets (overview, human, animal, environment, interconnectedness).

To use your own sheets:
1. Publish the sheet (File → Share → Publish to web → CSV)
2. Replace the sheet ID strings in `VILLAGE_CONFIG`

### AI Chatbot
The chatbot connects to a local Ollama instance tunneled via ngrok. To configure:
- Update the endpoint URL in the `ask_ollama()` function inside `app.py`
- The model used is `gemma` — change via the `"model"` key in the request payload

### Local Data Fallback
If Google Sheets is unreachable, the app automatically reads from the `.xlsx` files in the `data/` directory. Keep these files up to date as a backup.

---

## 📦 Key Dependencies

| Package | Purpose |
|---|---|
| `dash` | Web application framework |
| `plotly` | Interactive charts and visualizations |
| `pandas` | Data loading and manipulation |
| `numpy` | Numerical operations |
| `requests` | HTTP requests (Google Sheets, live AQI scraping) |
| `beautifulsoup4` | HTML parsing for AQI/weather scraping |
| `openpyxl` / `xlrd` | Reading local `.xlsx` fallback files |
| `Flask` | Underlying web server (via Dash) |

Full dependency list: see `requirements.txt`.

---

## 📱 Responsive Design

The dashboard is fully responsive with:
- Sticky header and tab navigation
- Mobile-specific village and section nav strips
- Horizontal-scrollable tables and charts on narrow screens
- Grid layouts that collapse gracefully from 5-column → 2-column → 1-column

---

## 🔒 Notes

- Google Sheets links and data source URLs are **never exposed** through the chatbot
- Live AQI data is cached for 10 minutes to avoid rate limiting
- The chatbot strictly avoids sharing internal data sources or storage details

---

## 🔗 Village Spreadsheet URLs

All data is sourced from Google Sheets. Below are the direct links to each village's spreadsheets.

> **Access Note:** These sheets must be shared with anyone who needs to view or edit them. Contact the project team if you need access.

---

### 🏘️ Village 1 — Bettahalasuru

| Pillar | URL |
|---|---|
| Human | https://docs.google.com/spreadsheets/d/1kMzWtBm-cKM8kQLgGRnfCQS8_cxizlTm |
| Animal | https://docs.google.com/spreadsheets/d/1hmixQht8zdETU0vA3w1-bduZeRqdp-2m |
| Environment | https://docs.google.com/spreadsheets/d/1AGIFjGQy4Y2hpMjF-ZwfW5OVAOVMU04y |
| Interconnectedness | https://docs.google.com/spreadsheets/d/1uYM6V-usylcrgVyD57J7stv-NGUKchBK |
| Overview | https://docs.google.com/spreadsheets/d/19gLj_SxcjJCwppnn1Y7q_2MmXzdG_-ik |

---

### 🏘️ Village 2

| Pillar | URL |
|---|---|
| Human | https://docs.google.com/spreadsheets/d/18hsiTzjLEpyzBgQffjiwSYGtRJ9z5CErXPa7jL1YwAs |
| Animal | https://docs.google.com/spreadsheets/d/18hsiTzjLEpyzBgQffjiwSYGtRJ9z5CErXPa7jL1YwAs |
| Environment | https://docs.google.com/spreadsheets/d/19fLxsu8N1oJbZYy6PeN6-OrvOVqdl4BzqyyJk5Nx7MQ |
| Interconnectedness | https://docs.google.com/spreadsheets/d/1X1sO3dDjkve83bDCdl-6JR0Q-gp1wBYlyM_n0GC7muM |
| Overview | https://docs.google.com/spreadsheets/d/1rirF-jWznc0r6_7GKoRKKPk5gKFaS9XvefnVOoXxrzY |

---

### 🏘️ Village 3

| Pillar | URL |
|---|---|
| Human | https://docs.google.com/spreadsheets/d/15zx59Ur6jJ2Jm4gp810TvQO9C0nPzEi_9aopd3AbLVo |
| Animal | https://docs.google.com/spreadsheets/d/1pupQs4Meh8B9e_7rsCAVcZkcePksiVSZiBjnYhFsbaI |
| Environment | https://docs.google.com/spreadsheets/d/1iKzI2I0EE1evn31DZrJyPE_FqQ5Zn03JX_9m5ELx1PA |
| Interconnectedness | https://docs.google.com/spreadsheets/d/1RfTZ779n7s2ijZar4FqXRe-7Haec4reGVrDEaJP_VVg |
| Overview | https://docs.google.com/spreadsheets/d/16qOZaoSGC4qJojdyREPT-5KBe7oiUlHBgymnsweAyV8 |

---

### 🏘️ Village 4

| Pillar | URL |
|---|---|
| Human | https://docs.google.com/spreadsheets/d/1yh8K61b-fEWWZ50QtHNTQ42mDLxHtxZWrqHpxv-fJ6o |
| Animal | https://docs.google.com/spreadsheets/d/1TRT5UkZxRsiQJFGKZ8E_RX2whZHzOiVmmgi39IKATMc |
| Environment | https://docs.google.com/spreadsheets/d/1J5GXl8OgreBu0eUUui3eryY2ZVEjwbXNscajCDP9SVU |
| Interconnectedness | https://docs.google.com/spreadsheets/d/1mdQ7_ABCdtTtQa8YWG-ZOQLE7U4Tfpynw_aX8QJzzTE |
| Overview | https://docs.google.com/spreadsheets/d/1hm-t_N2ztGZUEFsQwtR872FvvPFirvUccOYbVWgFxYg |

---

> **Note:** Village 2 Human and Animal pillars currently share the same Google Sheet (`18hsiTzjLEpyzBgQffjiwSYGtRJ9z5CErXPa7jL1YwAs`). This is as configured in `app.py` — update if separate sheets are created.

---

## 📄 License

Internal project — Planetary Health Foundation, IISc Bangalore. Not for public redistribution.

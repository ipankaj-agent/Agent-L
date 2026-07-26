# 🚀 Agent-L

> **A modular AI-powered automation framework for browser-based workflows.**

Agent-L is an extensible automation platform that combines **LLMs**, **browser automation**, and **AI-driven decision making** to automate repetitive web workflows.

The first implementation targets **LinkedIn Easy Apply**, enabling autonomous job discovery, application submission, intelligent form completion, and application tracking. Its modular architecture allows the same automation engine to be reused for other websites by simply adding a new site adapter.

---

## ✨ Features

* 🤖 End-to-end LinkedIn Easy Apply automation
* 🧠 LLM-powered form understanding and question answering
* 📄 Resume-aware response generation
* ⚡ Redis caching to reduce LLM cost and latency
* 💾 SQLite-based application tracking
* 🔄 Persistent browser sessions for long-running automation
* 📊 Interactive dashboard with reports and analytics
* 🌐 Extensible site adapter architecture
* 📝 Detailed logging and execution reports

---

## 🏗️ Architecture

Agent-L is designed as a collection of reusable modules where each component has a single responsibility.

```text
linkagent/
├── browser/        # Playwright browser automation
├── dashboard/      # Report generation and dashboard APIs
├── database/       # SQLite database layer
├── llm/            # LLM integration and prompts
├── resume/         # Resume parsing and processing
├── sites/
│   └── linkedin/   # LinkedIn implementation
├── ui/             # TypeScript dashboard frontend
├── utils/          # Shared utilities
├── workflows/      # Automation workflows
└── main.py         # Application entry point
```

---

## 🌐 Extensible Site Modules

The automation engine is **website-independent**.

Each website is implemented as a separate module under:

```text
linkagent/sites/
```

A site module is responsible for:

* Website navigation
* Authentication
* Search workflow
* Form parsing
* Submission logic
* Website-specific automation

This design makes it straightforward to support platforms such as:

* LinkedIn ✅
* Indeed
* Wellfound
* Naukri
* Greenhouse
* Lever
* Any custom web application

while reusing the same:

* AI Engine
* Browser Automation
* Resume Processing
* Database
* Redis Cache
* Dashboard
* Reporting

---

## 📊 Dashboard & Reporting

Agent-L includes a built-in reporting system for monitoring automation runs.

Features include:

* 📈 Application statistics
* 📄 Generated application reports
* 📊 Success and failure metrics
* 🔍 Execution logs
* 📋 Job application history

The dashboard consists of:

* **Fast API** backend
* **TypeScript** frontend
* Real-time report visualization

---

## 🛠️ Technology Stack

| Category           | Technology                |
| ------------------ | ------------------------- |
| Language           | Python                    |
| Browser Automation | Playwright                |
| AI Models          | OpenRouter (GPT-OSS-120B) |
| Cache              | Redis                     |
| Database           | SQLite                    |
| Dashboard API      | FastAPI                   |
| Frontend           | TypeScript                |
| Validation         | Pydantic                  |
| Package Manager    | uv                        |

---

## 🚀 Getting Started

### Clone

```bash
git clone <repository-url>
cd Agent-L
```

### Install

```bash
uv sync
```

### Configure

Create a `.env` file.

```env
OPENROUTER_API_KEY=your_api_key
```

### Run

```bash
uv run python -m linkagent.main "<linkedin-job-search-url>"
```

---

## 📁 Project Structure

```text
src/
└── linkagent
    ├── browser
    ├── dashboard
    ├── database
    ├── llm
    │   └── prompts
    ├── resume
    ├── sites
    │   └── linkedin
    ├── ui
    │   └── dist
    ├── utils
    ├── workflows
    └── main.py
```

---

## 🤝 Contributing

Contributions, feature requests, and bug reports are welcome.

Feel free to open an issue or submit a pull request.

---

## 📄 License

Licensed under the MIT License.

---

## ⚠️ Disclaimer

This project is intended for educational and research purposes. Users are responsible for complying with the Terms of Service of the websites they automate and all applicable laws and policies.

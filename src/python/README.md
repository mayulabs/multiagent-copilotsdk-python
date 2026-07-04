# Agent Orchestrator - Python 🐍

Multi-agent property search system powered by GitHub Copilot SDK.

This is the Python implementation of the Agent Orchestrator demo from Microsoft Build 2026 session **BRK206: Your agent, anywhere**.

## 🎯 Overview

This application demonstrates how to use the **GitHub Copilot SDK** to build intelligent agents that autonomously process customer enquiries through a multi-phase pipeline:

1. **Validation Phase** - Checks if enquiry is genuine (not spam)
2. **Search Phase** - Searches property database and performs web research
3. **Report Phase** - Generates a report for salespeople

The AI agent autonomously transitions between phases, calls tools, and makes decisions without hardcoded logic - it's all driven by natural language instructions.

## 🏗️ Architecture

### Backend
- **FastAPI** - Modern async web framework
- **SQLAlchemy** - ORM for database operations
- **WebSockets** - Real-time UI updates
- **GitHub Copilot SDK** - AI agent runtime

### Frontend
- **HTML + JavaScript** - Dynamic UI with WebSocket communication
- **SVG** - Pipeline visualization
- **Real-time updates** - Agents move through phases automatically

### Database
- **SQLite** - Lightweight database with 100 sample properties
- **Async operations** - Non-blocking database queries

## 📋 Prerequisites

- **Python 3.10+**
- **GitHub CLI** authenticated (`gh auth login`)
- **GitHub Copilot subscription** (for SDK access)

## 🚀 Getting Started

### 1. Install Dependencies

```bash
cd src/python
pip install -r requirements.txt
```

**Note**: The main dependencies installed are:
- `github-copilot-sdk` - GitHub Copilot SDK for Python
- `fastapi` - Web framework  
- `sqlalchemy` - Database ORM
- `aiosqlite` - Async SQLite support

### 2. Authenticate with GitHub

The Copilot SDK uses your GitHub CLI credentials:

```bash
gh auth login
```

### 3. Test the SDK

First, verify that the Copilot SDK is working:

```bash
python test_sdk.py
```

You should see a successful test with a greeting from Copilot in Portuguese! 🎉

### 4. Run the Full Application

**⚠️ Work in Progress**: The full FastAPI application is being finalized. Currently available:
- ✅ Core agent logic
- ✅ Database models
- ✅ Phase management
- 🚧 Web interface integration (in progress)

To test the agent directly:

## 📁 Project Structure

```
src/python/
├── app.py                  # FastAPI application (main entry point)
├── agent.py                # AI agent implementation
├── app_state.py            # Global state management
├── property_database.py    # Database models and ORM
├── phase.py                # Pipeline phase definitions
├── requirements.txt        # Python dependencies
├── templates/
│   └── index.html         # Frontend HTML template
└── static/
    └── app.css            # Styles
```

## 🔑 Key Technologies

- **FastAPI** - High-performance async web framework
- **WebSockets** - Real-time bidirectional communication
- **SQLAlchemy** - Powerful SQL toolkit and ORM
- **Python async/await** - Native asynchronous programming
- **GitHub Copilot SDK** - AI agent runtime and orchestration
- **SQLite** - Embedded relational database
- **Jinja2** - Template engine for HTML

## 🛠️ How It Works

### Agent Lifecycle

1. **User submits enquiry** → Frontend sends via WebSocket
2. **Agent created** → Unique ID generated, added to state
3. **Copilot session starts** → SDK creates AI session with tools
4. **AI processes enquiry** → Autonomously calls tools and transitions phases
5. **Real-time updates** → WebSocket pushes state changes to frontend
6. **Completion** → Agent finishes or is rejected

### Tools Available to AI

The AI agent can call these tools during execution:

- `set_current_phase(phase)` - Transitions to a new phase
- `report_intent(intent)` - Updates current status message
- `search(...)` - Searches property database with filters
- `web_fetch` - Built-in web search capability

## 📊 Sample Enquiries

Click the **+** button in the UI to try these:

- "I want a 3-bedroom house in Toronto with a backyard"
- "Looking for a condo in Vancouver under $500,000"
- "Need a family home near good schools in Calgary"
- "Want a waterfront property with 4+ bedrooms"

## 🔧 Configuration

### Database

By default, uses SQLite with 100 sample properties loaded from `Data/Properties/*.json`.

To use custom data:
1. Add JSON files to a data directory
2. Update `data_dir` in `app.py` lifespan
3. Ensure JSON files match the property schema

### Copilot SDK

The SDK stores its cache in `.copilot/` directory. Authentication is handled via GitHub CLI.

## 🐛 Troubleshooting

### "copilot-sdk-python not found"

The SDK package name might vary. Check the official docs:
```bash
pip install copilot-sdk-python
```

### "Database file not found"

Make sure you're running from the `src/python/` directory, or update the `data_dir` path in `app.py`.

### WebSocket connection fails

- Check if port 8000 is already in use
- Verify the WebSocket URL matches your host/port
- Check browser console for errors

## 📚 Learn More

- [GitHub Copilot SDK Documentation](https://github.com/github/copilot-sdk)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://www.sqlalchemy.org/)

## 🎓 Related Resources

- **Build 2026 Session**: BRK206 - Your agent, anywhere
- [GitHub Copilot SDK Documentation](https://github.com/github/copilot-sdk)
- [Copilot SDK Cookbooks](https://github.com/github/awesome-copilot)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

## 🤝 Contributing

This is a demo project for Microsoft Build 2026. Feel free to:
- Report issues
- Suggest improvements
- Create your own agent variations

## 📄 License

See [LICENSE](../../LICENSE) for details.

---

**Built with ❤️ for Microsoft Build 2026**

# Urban-Grid

AI-powered predictive traffic management platform that forecasts congestion before it happens, dynamically optimizes routes and signals, and visualizes the city through a real-time 3D digital twin.

---

## 1. Prerequisites

### Python Environment
- Python **3.10+** (tested up to Python 3.14)
- Virtual environment recommended:
  ```bash
  python -m venv .venv
  # Linux/macOS
  source .venv/bin/activate
  # Windows (PowerShell)
  .venv\Scripts\Activate.ps1
  # Windows (Command Prompt)
  .venv\Scripts\activate.bat
  ```

### SUMO Installation
The backend simulation relies on [Eclipse SUMO](https://eclipse.dev/sumo/) (v1.18.0 or newer).

1. Install Eclipse SUMO from the official website or distribution package manager:
   - **Windows**: Download installer or zip from Eclipse SUMO releases.
   - **Linux (Ubuntu/Debian)**: `sudo apt install sumo sumo-tools sumo-doc`
   - **macOS (Homebrew)**: `brew install sumo`
2. Configure environment variables:
   - Set `SUMO_HOME` pointing to your SUMO installation root directory (containing `bin/` and `tools/`).
   - Ensure the `bin/` subdirectory (`$SUMO_HOME/bin` or `%SUMO_HOME%\bin`) is included in your system `PATH`.
   - Optionally ensure `$SUMO_HOME/tools` is in `PYTHONPATH` if using system-installed TraCI/sumolib tools.

---

## 2. Dependency Installation

Install all backend and test dependencies using `pip`:

```bash
pip install -r requirements.txt
```

Alternatively, install in editable mode with development dependencies:

```bash
pip install -e ".[dev]"
```

---

## 3. Running the Backend Server

Start the FastAPI application with Uvicorn:

```bash
uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Upon startup:
- The FastAPI lifespan automatically initializes the `TraCIBridge` and connects to the SUMO network (`urban_grid.sumocfg`).
- The API is available at `http://localhost:8000`.
- Interactive OpenAPI documentation is accessible at `http://localhost:8000/docs`.
- The live WebSocket stream is served at `ws://localhost:8000/ws/traffic`.

---

## 4. Running the SUMO-Backed System

The simulation can be operated interactively or autonomously:

1. **Closed-Loop Step**:
   Advance the simulation and trigger M1 AI decisions/actuations in a single cycle:
   ```bash
   curl -X POST http://localhost:8000/api/control/loop/step
   ```
2. **Simulation Step**:
   Advance SUMO by $N$ steps and broadcast state to WebSocket clients:
   ```bash
   curl -X POST http://localhost:8000/api/simulation/step -H "Content-Type: application/json" -d '{"steps": 1}'
   ```
3. **Control Mode Switching**:
   Switch between `AUTO`, `MANUAL`, and `EMERGENCY` modes:
   ```bash
   curl -X POST http://localhost:8000/api/control/mode -H "Content-Type: application/json" -d '{"mode": "EMERGENCY"}'
   ```
4. **WebSocket Streaming**:
   Connect any WebSocket client to `ws://localhost:8000/ws/traffic` to receive real-time canonical `traffic.update` event frames.

---

## 5. Running Tests

Execute the complete test suite:

```bash
python -m pytest
```

Execute focused backend and simulation tests:

```bash
# Run WebSocket tests
python -m pytest backend/tests/test_websocket.py

# Run TraCI concurrency and serialization tests
python -m pytest simulation/sumo/tests/test_traci_concurrency.py

# Run control mode tests
python -m pytest backend/tests/test_control_modes_api.py simulation/sumo/tests/test_control_modes.py
```

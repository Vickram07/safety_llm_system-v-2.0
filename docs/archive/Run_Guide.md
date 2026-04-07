# INFERNAL X Run Guide

## Recommended Review Launch

From the project root:

```powershell
python -m uvicorn server:app --host 127.0.0.1 --port 5101
```

Open:

```text
http://localhost:5101
```

This is the safest launch method for review use because it avoids common conflicts on port `8000`.

## Before You Run

Make sure:

1. Python dependencies are installed
2. Ollama is running
3. the `infernalx` model exists locally

Useful checks:

```powershell
ollama list
ollama show infernalx
```

## If You Want The Default Built-In Launch

You can also run:

```powershell
python server.py
```

Then open:

```text
http://localhost:8000
```

Use this only if port `8000` is free.

## If Port 8000 Is Busy

Check:

```powershell
netstat -ano | Select-String ':8000'
```

If needed, stop the old process:

```powershell
Stop-Process -Id <PID> -Force
```

Or just use the recommended `5101` command above.

## Frontend

You do not need to run a separate frontend command for the review build.

The backend serves the built frontend automatically.

## Optional Frontend Dev Mode

Only use this if you are actively editing the React UI:

```powershell
cd ui
npm.cmd run dev -- --port 5102
```

Then open:

```text
http://localhost:5102
```

For review/demo, prefer the backend-served UI on `5101`.

## Quick Demo Commands

After the app opens, you can trigger the demo fire pipeline with:

```powershell
Invoke-RestMethod -Method Post http://localhost:5101/api/sensor_demo
```

Then ask in the assistant:

- `status report`
- `which zone is most critical?`
- `how many occupants are trapped?`
- `which exits are blocked?`
- `is the sprinkler active?`
- `should i deploy suppression now?`

## Main Endpoints

- `GET /` - frontend
- `WS /ws` - live simulation state
- `POST /api/chat` - operator assistant
- `POST /api/summarize` - current emergency summary
- `POST /api/sensor_demo` - inject demo sensor packet
- `GET /api/sensor_snapshot` - fused sensor state

## If The Page Does Not Open

Check these in order:

1. Is Ollama running?
2. Did the backend command start without errors?
3. Are you opening the same port you launched?
4. Is another process already using that port?

## Review-Safe Launch Summary

Use this:

```powershell
python -m uvicorn server:app --host 127.0.0.1 --port 5101
```

Then open:

```text
http://localhost:5101
```

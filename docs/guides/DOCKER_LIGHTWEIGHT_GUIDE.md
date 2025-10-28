# Lightweight Docker Workflow

This project now ships with a compact Alpine-based container image and optional infrastructure services that stay off unless you explicitly opt-in. Use this guide to keep local development snappy on constrained hardware.

---

## 🐋 Rebuild the Alpine image

1. From the project root (`Autotrader/`), rebuild once to pick up the new base image:

   ```powershell
   docker compose build
   ```

2. Subsequent `docker compose up` commands reuse the slimmer image (~40% smaller than the previous Debian "slim" build).

---

## ⚙️ Minimal service set

Only the core API + dependencies start by default:

- `app`
- `postgres`
- `redis`

Bring them up together:

```powershell
docker compose up app postgres redis
```

Add `-d` to run them in the background when you need the terminal back.

---

## 🔌 Opt-in add-ons

Heavyweight services are now tagged with Compose profiles. They stay idle until you request them.

| Profile        | Services                                                                 |
|----------------|---------------------------------------------------------------------------|
| `observability`| `metrics`, `compliance-exporter`, `prometheus`, `grafana`                 |
| `mlops`        | `mlflow`, `prefect`                                                       |
| `infra`        | `kafka`, `minio`                                                          |
| `workers`      | `worker-*` (already profiled)                                             |

Start only what you need:

```powershell
# Core API + observability dashboards
docker compose --profile observability up app

# Experimentation day (MLflow + Prefect)
docker compose --profile mlops --profile infra up mlflow prefect
```

> Profiles are additive. If a profiled service depends on another profiled service (e.g., `worker-ingestion` → `kafka`), enable both profiles in the same command.

---

## 🧹 Shutting down background services

Keep RAM free by stopping optional containers when you finish a task:

```powershell
# Stop all profiled services
docker compose --profile observability --profile mlops --profile infra stop

# Or stop individual containers
docker compose stop grafana minio mlflow
```

For a full cleanup (including volumes), remember the optimizer script you created earlier:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\optimize-docker-wsl2.ps1
```

---

## ✅ Quick checklist

- [x] Alpine-based runtime (~150 MB smaller)
- [x] Optional services gated behind Compose profiles
- [x] Minimal commands to start/stop heavy workloads

Ping me if you want presets (e.g., a `docker-compose.dev-lite.yml`) or automation scripts to toggle these profiles automatically.

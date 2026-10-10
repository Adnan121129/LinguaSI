# Deploying LinguaSI

LinguaSI is four deployable pieces plus two optional services. Nothing needs Kubernetes or a
message queue; a managed PostgreSQL database and two small web services are enough.

| Piece | What it is | Good places to run it |
| --- | --- | --- |
| Database | PostgreSQL 16 | Neon, Supabase, Railway, Render, Amazon RDS, any managed Postgres |
| API | FastAPI app, image built from `backend/Dockerfile` | Railway, Render, Fly.io, any container or Python host |
| Web app | Next.js app (`web/`) | Vercel, or the `web/Dockerfile` image anywhere |
| Mobile app | Expo app (`mobile/`), built with EAS | App Store and Google Play (or internal distribution) |
| Redis (optional) | Shared rate-limit counters | Needed only when two or more API instances run |
| S3-compatible bucket (optional) | Speaking recordings | Needed when the API's disk is not persistent |

## Before you start: AI costs

LinguaSI works completely in **Mock AI Mode** (the default): no AI keys, no AI costs, deterministic
feedback from LinguaSI's own analysis engines. Real AI feedback needs an API key with billing
enabled from the provider you choose (Anthropic, OpenAI or Google). A Claude or ChatGPT chat
subscription, or a Claude Code subscription, does not include API credits for your deployment.
Keys are set only in the API's environment; the web and mobile apps never see them.

Cost controls that are on by default: a per-learner hourly cap on AI requests
(`AI_USER_HOURLY_LIMIT`, 80), fast/cheap models for short tasks and strong models only for
evaluations and generation, and a per-task output budget. The admin panel shows AI usage per day and
per task.

## 1. Database

1. Create a PostgreSQL 16 database and copy its connection URL. URLs that start with `postgres://` or
   `postgresql://` are accepted as they are (LinguaSI selects the psycopg 3 driver itself). Add
   `?sslmode=require` if your provider requires TLS and the URL doesn't include it.
2. Migrations run automatically when the API container starts (`alembic upgrade head`). On a host
   without the Docker image, run `alembic upgrade head` from `backend/` as a release or pre-deploy
   command.
3. The curated learning content (vocabulary, tasks, passages, scripts, topics, achievements) is
   loaded automatically on the first start (`AUTO_SEED=true`). `python -m app.cli seed` reloads it.
4. Create an admin account, or promote an existing one:
   `python -m app.cli create-admin --email you@example.com` (it asks for a password for a new
   account). Alternatively, list the address in `ADMIN_EMAILS` before you register.
5. Optional, for demos: `python -m app.cli demo` creates the demo learner with 28 days of history
   (`--days 7-60`, `--reset` to recreate it).

Use your provider's automated backups or point-in-time recovery. For the Compose setup, see
[section 6](#6-one-server-with-docker-compose).

## 2. API

### Settings for production

Every setting is listed with a comment in [`backend/.env.example`](../backend/.env.example). The
ones that matter for a deployment:

| Setting | Value |
| --- | --- |
| `ENVIRONMENT` | `production` (the Docker image sets it). The API refuses to start with the development JWT secret. |
| `JWT_SECRET` | A random value of at least 32 characters, e.g. `openssl rand -hex 32` (or `JWT_SECRET_FILE`: the path of a file that holds it) |
| `DATABASE_URL` | The database URL from step 1 |
| `AI_MOCK_MODE`, `AI_PROVIDER`, `<PROVIDER>_API_KEY` | Keep mock mode, or `AI_MOCK_MODE=false`, the provider and its key |
| `STT_PROVIDER`, `TTS_PROVIDER` | `openai` for server speech recognition and voices (uses `OPENAI_API_KEY`), otherwise `mock` |
| `STORAGE_BACKEND` + `S3_*` | `s3` when the API's disk is wiped on deploy (most platforms without a volume) |
| `REDIS_URL` | When you run more than one API instance, so rate limits are shared |
| `FORWARDED_ALLOW_IPS`, `PROXY_SHARED_SECRET` | See [client addresses](#4-client-addresses-and-rate-limits) |
| `CORS_ORIGINS` | Only browser apps that call the API directly. The web app calls it server-side and needs no entry. |
| `ADMIN_EMAILS` | Optional: addresses that become admins when they register |

Health checks: `GET /health` (process up) and `GET /health/ready` (database reachable). Interactive
API documentation is served at `/docs` (OpenAPI schema at `/openapi.json`).

### Railway

1. New project → **Deploy from GitHub repo** → choose this repository.
2. In the service's **Variables**, set `RAILWAY_DOCKERFILE_PATH=backend/Dockerfile` (the build
   context stays the repository root, which the image needs for migrations and seed content).
3. Add a **PostgreSQL** database to the project and set `DATABASE_URL=${{Postgres.DATABASE_URL}}`.
4. Add `JWT_SECRET` and the other settings above. Railway provides `PORT`; the image listens on it.
5. Settings → **Healthcheck Path**: `/health/ready`. Generate a public domain.
6. Recordings: attach a volume at `/app/backend/storage`, or use `STORAGE_BACKEND=s3`.

### Render

1. **New Web Service** → this repository → Runtime **Docker**.
2. **Dockerfile Path** `backend/Dockerfile`, **Docker Build Context Directory** `.` (repository root).
3. Create a Render PostgreSQL database and use its internal URL as `DATABASE_URL`.
4. Add the settings above; **Health Check Path** `/health/ready`.
5. Recordings: add a persistent disk mounted at `/app/backend/storage`, or use S3.

### Any other host (no Docker)

Python 3.12, then from `backend/`:

```sh
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --proxy-headers --forwarded-allow-ips "<your proxy's address>"
```

## 3. Web app

### Vercel (recommended)

1. **Add New Project** → import this repository → **Root Directory** `web` (Next.js is detected).
2. Environment variables:
   - `BACKEND_URL` = the API's public URL, e.g. `https://api.example.com` (read on the server only)
   - `PROXY_SHARED_SECRET` = the same random value as the API's (see section 4)
3. Deploy. Session cookies are `Secure` by default in production builds, so serve the app over
   HTTPS (Vercel does).

The `output: "standalone"` setting in `next.config.ts` is for the Docker image; Vercel ignores it.

### Docker (Railway, Render, your own server)

```sh
docker build -t linguasi-web web
docker run -p 3000:3000 -e BACKEND_URL=https://api.example.com -e PROXY_SHARED_SECRET=... linguasi-web
```

On Railway set the service's root directory to `web` (its Dockerfile is picked up automatically);
on Render use Dockerfile path `web/Dockerfile` with build context `web`. Put the server behind
HTTPS; keep `COOKIE_SECURE` unset (true) in production.

## 4. Client addresses and rate limits

The API limits requests per client address: sign-in (30 per 5 minutes), registration (10 per hour)
and token refresh (60 per minute). Sign-in is also limited per account (10 per 5 minutes) and AI
activities per learner (`AI_USER_HOURLY_LIMIT` per hour). For the per-address limits to count each
learner separately, the API must see each learner's own address:

- **The mobile app** calls the API directly. If the API sits behind your platform's load balancer,
  set `FORWARDED_ALLOW_IPS` to the address range that load balancer connects from (your platform's
  documentation lists it; private ranges such as `10.0.0.0/8` are typical). Uvicorn then takes the
  right-most address the load balancer added. Never use `*`: Uvicorn then takes the left-most
  entry, which the client can set.
- **The web app** calls the API from its server (the browser never talks to the API). Either:
  - **The web server has fixed addresses** (your own server): add them to `FORWARDED_ALLOW_IPS`.
  - **The web server's addresses change** (Vercel, serverless, Docker Compose): set the same random
    `PROXY_SHARED_SECRET` (32+ characters) on the API and the web app. The web server then reports
    each learner's address in `X-LinguaSI-Client-IP`, and the API accepts it only from requests
    carrying the secret. With Docker Compose, put it in `.env`; the Compose file passes it to both.
- Run the web server behind a proxy or platform that sets `X-Forwarded-For` (Vercel, Railway,
  Render, nginx and Caddy all do). Exposed directly on the internet, it can't tell a real client
  address from one the client wrote itself.

Without this setup LinguaSI still works, but all web learners share the web server's allowance.

## 5. Mobile app

1. Set `EXPO_PUBLIC_API_URL` to the API's public HTTPS URL as an EAS environment variable for each
   profile (`npx eas-cli@latest env:create`). It is compiled into the app and is public by design;
   no secrets go into the app.
2. Change the bundle identifier / package (`app.linguasi.mobile` in `mobile/app.json`) to your own.
3. Build: `npx eas-cli@latest build --profile production --platform all`, then
   `npx eas-cli@latest submit`. `development` builds include the dev client; `preview` builds are
   for internal testing.

See [`mobile/README.md`](../mobile/README.md) for local development builds.

## 6. One server with Docker Compose

`docker-compose.yml` runs PostgreSQL, the API, the web app and a browser preview of the mobile app
on one machine. It needs no configuration ([GETTING-STARTED.md](../GETTING-STARTED.md) covers running
it on a personal computer); for a server, create `.env` from `.env.example` first:

```sh
cp .env.example .env    # AI keys, COOKIE_SECURE=true behind HTTPS, PROXY_SHARED_SECRET, ports
docker compose up -d --build --wait
docker compose exec api python -m app.cli create-admin --email you@example.com
```

- Web app on port 3000, API (and `/docs`) on port 8000, mobile app preview on port 8081 (change
  them with `WEB_PORT`, `API_PORT`, `MOBILE_PORT`). For a public server, put a TLS reverse proxy
  (Caddy, nginx) in front and set `COOKIE_SECURE=true` in `.env`. The mobile preview is compiled
  against `http://localhost:API_PORT`, so it is for local use; phones use the EAS builds (section 5).
- Without `JWT_SECRET` the API creates a random secret on its first start and keeps it in the
  `recordings` volume (`JWT_SECRET_FILE`). Set `JWT_SECRET` to manage it yourself.
- For per-learner rate limits behind the reverse proxy, set `PROXY_SHARED_SECRET` (section 4), and
  `FORWARDED_ALLOW_IPS` to the proxy's address if mobile apps call the API through it.
- Data lives in the `db-data` and `recordings` volumes. Back up the database with
  `docker compose exec db pg_dump -U linguasi linguasi > backup.sql`.

## 7. Check the deployment

```sh
curl https://api.example.com/health/ready   # {"status":"ready"}
curl https://api.example.com/meta           # AI provider, mock mode, speech providers
```

Then sign up in the web app, or run the acceptance journey against a staging deployment (it creates
a test learner account):

```sh
cd web && E2E_BASE_URL=https://staging.example.com npm run e2e
```

## Production checklist

- [ ] `ENVIRONMENT=production` and a random `JWT_SECRET` (or `JWT_SECRET_FILE`)
- [ ] HTTPS for the web app and the API; `COOKIE_SECURE` not set to `false`
- [ ] AI keys only in the API's environment; `AI_MOCK_MODE=false` only with provider credits in place
- [ ] `AI_USER_HOURLY_LIMIT` suits your budget; `AI_LOG_CONTENT=false` (the default)
- [ ] Client addresses configured (section 4)
- [ ] Persistent storage for recordings (volume or S3)
- [ ] `REDIS_URL` if more than one API instance runs
- [ ] Database backups enabled
- [ ] An admin account created

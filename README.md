# First AD (Assistant Director)

**A production office that reads a screenplay and hands back a stripboard, a clearance report, a budget, and call sheets.**

Nine Gemini agents on Google Cloud, orchestrated as a deterministic seven-stage pipeline, grounded in the Parallel Search API.

---

## The problem

Between "we have a script" and "we're shooting" sits two to three weeks of unglamorous work that nobody has automated:

- A **1st AD** reads all 110 pages and tags every prop, vehicle, stunt, and effect onto a breakdown sheet, then packs the scenes into shooting days that minimise company moves without stranding an actor on hold pay.
- A **clearance researcher** checks every proper name, business, phone number, licence plate, and address in the script against the real world, because a corrupt alderman named Grant Holloway is a defamation suit if a real Chicago alderman is named Grant Holloway. This costs $2,000 to $5,000 and takes 5 to 10 business days, and no film gets errors-and-omissions insurance without it.
- A **line producer** turns all of that into a budget top sheet that a financier will actually read.

First AD does the whole package in about five minutes. That figure is measured, not projected: a 14-scene short runs end to end in 323 seconds on the Gemini free tier, with agent concurrency deliberately gated to stay inside its rate limit.

## Why it needs both Google Cloud and Parallel

The two halves are load-bearing in different ways.

**Gemini** does the reading and the judgement: what a scene actually needs, which day is too heavy because of what is in it rather than how long it is, which schedule change clears a turnaround breach.

**Parallel Search** does the part a language model structurally cannot. Ask any model "is there a real Chicago alderman named Grant Holloway" and it will answer with total confidence either way, because the question is about the world today and not about the model's weights. A clearance report built on a confabulation is worse than no report at all. So every risk verdict in First AD is anchored to a URL a production lawyer can open, and every permit figure comes from a source rather than a guess.

That is also why the clearance module is not a chatbot. It is a fixed pipeline that fans out one grounded search per entity and grades the evidence.

---

## Architecture

Seven stages, fixed order, a typed Pydantic contract between every one. Concurrency appears only where the work is genuinely independent.

```
                    ┌─────────────────────────────┐
   screenplay  ───► │ 1  Script Supervisor        │  parse, measure, synopsise
                    └──────────────┬──────────────┘
                                   │  ParsedScript
              ┌────────────────────┴────────────────────┐
              ▼                                         ▼
   ┌──────────────────────┐                ┌──────────────────────────┐
   │ 2a 1st AD            │                │ 2b Clearance Researcher  │
   │    Breakdown         │                │    Entity extraction     │
   └──────────┬───────────┘                └────────────┬─────────────┘
              │ Breakdown                                │ ClearanceEntity[]
              ▼                                          ▼
   ┌──────────────────────┐                ┌──────────────────────────┐
   │ 3a Location Manager  │◄─ Parallel ─►  │ 3b Clearance Analyst     │
   │    permits, hazards  │    Search      │    risk + citations      │
   └──────────┬───────────┘                └────────────┬─────────────┘
              └────────────────────┬────────────────────┘
                                   ▼
                    ┌─────────────────────────────┐
                    │ 4  1st AD  · Stripboard     │  + deterministic optimiser
                    ├─────────────────────────────┤
                    │ 5  UPM     · Compliance     │  turnaround, minors, safety
                    ├─────────────────────────────┤
                    │ 6  Line Producer · Budget   │
                    ├─────────────────────────────┤
                    │ 7  2nd AD  · Call sheets    │
                    └─────────────────────────────┘
```

## Google Cloud integration

Complete and verified end to end. Every agent call in the pipeline goes through the Agent Development Kit, and the full nine-agent run has been executed against live Gemini, not mocked.

### What is used, and where

| Package | Version | Where it is called |
| --- | --- | --- |
| `google-adk` | 1.16.0 | [`agents/crew.py`](services/api/app/agents/crew.py) builds nine `LlmAgent` instances. [`core/adk_runtime.py`](services/api/app/core/adk_runtime.py) executes each one through `Runner.run_async()` with an `InMemorySessionService`. |
| `google-genai` | 1.41.0 | Model transport and `types.Content` construction, in the same runtime module. |

Nothing here is decorative. There is no path through the product that produces a stripboard, a clearance verdict, a budget or a call sheet without the ADK running an agent.

### How the ADK is used

Each of the nine crew members is an `LlmAgent` carrying an `output_schema`, so it returns a validated Pydantic model rather than prose. That single constraint is what makes a seven-stage pipeline deterministic: stage N+1 receives a typed object, never a paragraph it has to re-interpret.

The ADK forbids combining `output_schema` with tool use, which shaped the architecture. All deterministic work — screenplay parsing, Parallel search fan-out, stripboard optimisation — happens in the orchestrator between stages and is handed to the next agent as structured context, rather than being exposed as agent tools. Agents also carry `disallow_transfer_to_parent` and `disallow_transfer_to_peers`, because an agent that owes a typed answer must not hand control to a peer.

Model tiering is deliberate and per-agent. Stages that make consequential judgements can be pointed at `gemini-2.5-pro`; high-volume mechanical stages stay on `gemini-2.5-flash`, because a feature-length script runs those hundreds of times.

### Two Gemini backends, switchable

Both paths are wired and neither is aspirational:

```bash
# Developer path: an AI Studio API key
GOOGLE_API_KEY=...
GOOGLE_GENAI_USE_VERTEXAI=FALSE

# Google Cloud path: Vertex AI on a project
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=your-project
GOOGLE_CLOUD_LOCATION=us-central1
```

`GET /api/health` reports which backend is live, so there is never any ambiguity about what a given deployment is running:

```json
{ "gemini_configured": true, "gemini_backend": "vertex-ai", "parallel_configured": true }
```

Vertex is the better production path: no key to leak, and access governed by the service account's IAM role rather than a shared secret. [`cloudbuild.yaml`](cloudbuild.yaml) deploys to Cloud Run with `GOOGLE_GENAI_USE_VERTEXAI=TRUE` and expects `roles/aiplatform.user` on the runtime service account. The API-key path exists because it needs no billing account, which matters for anyone cloning this to try it.

### Safety configuration

Every agent runs with the four harm categories set to `BLOCK_ONLY_HIGH` rather than the defaults.

This is not a shortcut. These agents read screenplays, and drama is made of the things safety filters are tuned to catch: a bribe changing hands, a chase, a character thrown against a dumpster. Under default thresholds the breakdown agent can refuse to tag the props in a fight scene, and a refusal is not a transient failure, so the retry path does not rescue it. The stage simply dies on the exact material the product exists to process.

`BLOCK_ONLY_HIGH` rather than `BLOCK_NONE` or `OFF`, deliberately: loose enough for professional creative material, still refusing what is genuinely egregious. Turning the filters off in a tool anyone can upload to would be careless.

### Partner integration

Parallel is reached through its official `parallel-web` SDK — the "API frameworks" route — in [`tools/parallel_search.py`](services/api/app/tools/parallel_search.py), with bounded concurrency, per-run memoisation, and a per-run search budget. The consuming model is declared to Parallel via `client_model` so it can shape excerpt compression for Gemini specifically.

---

## Stack

| Layer | Technology |
| --- | --- |
| Agents | **Google ADK** (`google-adk`) — 9 `LlmAgent`s with typed `output_schema` |
| Models | **Gemini 2.5 Flash / Pro** via `google-genai`, on API key or Vertex AI |
| Grounding | **Parallel Search API** (`parallel-web`) — bounded concurrency, per-run memoisation |
| API | FastAPI, server-sent events for live crew progress |
| Web | Next.js 16, React 19, Tailwind v4 |

---

## Running it

### Requirements

- Python 3.12
- Node 20+
- A **Gemini API key** — free at [aistudio.google.com/apikey](https://aistudio.google.com/apikey). The free tier runs this end to end.
- A **Parallel API key** — [platform.parallel.ai](https://platform.parallel.ai). New accounts start with free credits, and the per-run search budget is capped at 12 entities by default to keep a full run cheap.

Both providers are optional to *boot*: the API reports which are configured at `/api/health` and the UI shows it, so you can see the interface without keys. The pipeline needs Gemini to run at all, and without Parallel the two research stages report themselves as unsourced rather than inventing findings.

### Backend

```bash
cd services/api
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt  # macOS/Linux

cp .env.example .env        # then fill in the keys
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
```

Set either path in `.env`:

```bash
# Gemini API key
GOOGLE_API_KEY=your-key

# or Vertex AI
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=your-project
GOOGLE_CLOUD_LOCATION=us-central1

PARALLEL_API_KEY=your-key
```

Check it came up configured:

```bash
curl http://localhost:8000/api/health
```

### Frontend

```bash
cd apps/web
npm install
npm run dev
```

Open <http://localhost:3000>, hit **Load sample script**, then **Send it up**.

---

## The sample screenplay

[`samples/the-projectionist.fountain`](samples/the-projectionist.fountain) is original material written for this project. It is a 14-scene short about a night projectionist at a dying single-screen cinema, and it is deliberately seeded with clearance landmines across the risk spectrum:

- a named alderman shown taking a bribe on camera — the textbook red
- a savings and loan, a bar, and a development firm
- a real Chicago street address
- an Illinois licence plate
- a phone number in the `555-01xx` range reserved for fiction, which should come back green and demonstrates the system knows the safe range

It also covers all four stripboard colours and repeats locations, so the scheduler has something real to optimise.

---

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Configuration status for both providers |
| `GET` | `/api/crew` | The agent roster and pipeline order |
| `GET` | `/api/sample` | The sample screenplay |
| `POST` | `/api/analyse` | Run the pipeline, streamed as SSE |
| `POST` | `/api/analyse/upload` | Same, from a file upload (`.fountain`, `.txt`, `.pdf`) |
| `GET` | `/api/runs` | Stored packages, newest first |
| `GET` | `/api/runs/{id}` | One stored package |
| `DELETE` | `/api/runs/{id}` | Discard a stored package |
| `GET` | `/api/runs/{id}/export/{document}.csv` | One document as a spreadsheet |
| `GET` | `/api/runs/{id}/export.json` | The whole package as JSON |
| `GET` | `/api/demo` | The recorded run bundled with the repo |
| `POST` | `/api/runs/{id}/promote` | Capture a stored run as the bundled demo |

`{document}` is one of `stripboard`, `day-out-of-days`, `breakdown`, `clearance`, `budget`, `call-sheets`. The literal id `demo` also works on both export routes.

Runs are persisted the moment they complete, so a refresh does not throw away a two minute run and every finished package has a permalink (`/?run=<id>`). Run ids coming off a URL are matched against a strict pattern before they touch the filesystem.

---

## Deliverables

| Tab | What it is |
| --- | --- |
| Stripboard | Shooting days with the real strip colours, plus a day-out-of-days grid that marks hold days, because a hold day is paid |
| Clearance | Risk verdicts, each carrying the sources it was reached from |
| Annotated script | The screenplay with every checked reference marked in place. Click a mark for the verdict, the collisions, and the citations |
| Locations | Permit authority, fee, lead time, and hazards per set |
| Compliance | Turnaround, minors, meal, and safety flags, each with the specific schedule change that clears it |
| Budget | Top sheet where every line names what in the script drives the cost |
| Call sheets | One per shooting day, with cast calls, department pre-calls, and safety notes |
| Breakdown | Every tagged element, with the ones forcing a department call highlighted |

---


```bash
cd services/api
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv/Scripts/python.exe -m pytest -q
```

### API on Render

1. Push the repository, then open <https://dashboard.render.com/blueprints> and create a Blueprint Instance pointed at it. Render reads [`render.yaml`](render.yaml).
2. When prompted, set `GOOGLE_API_KEY` and `PARALLEL_API_KEY`. They are marked `sync: false` so no secret is ever committed.
3. Leave `CORS_ORIGINS` for now; the web origin does not exist yet.

The image builds from the repository root with `-f services/api/Dockerfile`, because the API resolves `samples/` relative to the repo layout.

### Web app on Vercel

```bash
cd apps/web && npx vercel --prod
```

Root directory `apps/web`, and one environment variable:

```
NEXT_PUBLIC_API_BASE=https://firstad-api.onrender.com
```

Never put a provider key on Vercel. Anything prefixed `NEXT_PUBLIC_` is compiled into the browser bundle.

### Close the loop

Set `CORS_ORIGINS` on Render to the Vercel origin and redeploy. The API rejects the browser until the two match.

```bash
curl https://firstad-api.onrender.com/api/health
# gemini_configured and parallel_configured should both be true
```
---

## Imagery and originality

All screenplay material in [`samples/`](samples/) is original, written for this project.

Photography in `apps/web/public/img/` is from Unsplash under the Unsplash License, stored locally rather than hot-linked so the app has no runtime dependency on a CDN. Provenance is listed in [`CREDITS.txt`](apps/web/public/img/CREDITS.txt).

No copyrighted film artwork, posters, logos, or trademarks appear anywhere in the project. This is deliberate: a candidate hero image turned out to be a wall of VHS covers and was rejected for exactly that reason.

## Licence

MIT. See [LICENSE](LICENSE).

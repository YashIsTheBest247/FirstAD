# Greenlight

**A production office that reads a screenplay and hands back a stripboard, a clearance report, a budget, and call sheets.**

Nine Gemini agents on Google Cloud, orchestrated as a deterministic seven-stage pipeline, grounded in the Parallel Search API.

---

## The problem

Between "we have a script" and "we're shooting" sits two to three weeks of unglamorous work that nobody has automated:

- A **1st AD** reads all 110 pages and tags every prop, vehicle, stunt, and effect onto a breakdown sheet, then packs the scenes into shooting days that minimise company moves without stranding an actor on hold pay.
- A **clearance researcher** checks every proper name, business, phone number, licence plate, and address in the script against the real world, because a corrupt alderman named Grant Holloway is a defamation suit if a real Chicago alderman is named Grant Holloway. This costs $2,000 to $5,000 and takes 5 to 10 business days, and no film gets errors-and-omissions insurance without it.
- A **line producer** turns all of that into a budget top sheet that a financier will actually read.

Greenlight does the whole package in about two minutes.

## Why it needs both Google Cloud and Parallel

The two halves are load-bearing in different ways.

**Gemini** does the reading and the judgement: what a scene actually needs, which day is too heavy because of what is in it rather than how long it is, which schedule change clears a turnaround breach.

**Parallel Search** does the part a language model structurally cannot. Ask any model "is there a real Chicago alderman named Grant Holloway" and it will answer with total confidence either way, because the question is about the world today and not about the model's weights. A clearance report built on a confabulation is worse than no report at all. So every risk verdict in Greenlight is anchored to a URL a production lawyer can open, and every permit figure comes from a source rather than a guess.

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

The agent roster is not a metaphor. It is how the work actually divides on a film, and dividing it the same way keeps each instruction narrow enough to be reliable.

### Design decisions worth calling out

**Deterministic where it can be, model where it must be.** Slugline detection and page-eighth measurement have exact answers, so they are solved in code ([`core/screenplay.py`](services/api/app/core/screenplay.py)). Page eighths are measured against *typeset* row widths rather than source lines, because an action paragraph written as one long line wraps to three rows on a real page. `CONTINUOUS` headings inherit the previous scene's lighting state, which changes both the strip colour and which day the scene lands on.

**The optimiser proposes, the agent disposes.** Packing scenes into days to minimise company moves is a constraint problem, so [`core/scheduling.py`](services/api/app/core/scheduling.py) solves it and hands the Scheduler agent a candidate board. The agent then applies what an optimiser cannot encode: do not strand cast 3 on hold for four days, this day is too heavy because there is a stunt in it, that permit will not come through in time.

**Typed handoffs, not prose.** Every agent carries an `output_schema`, so stage N+1 receives a validated object and never re-interprets a paragraph. This is what makes a seven-stage LLM pipeline reproducible.

**Runs on the free tier by design.** Both model tiers default to `gemini-2.5-flash`, which is what the Gemini API free tier gives useful quota on, and agent concurrency is gated to 3 with exponential backoff on rate limits so a long script degrades into a slower run rather than a failed one. Setting `MODEL_REASONING=gemini-2.5-pro` measurably improves the four stages making consequential judgements (schedule, compliance, budget, risk) if you have paid quota. The Parallel search budget is capped per run for the same reason: every researched entity is a billable call.

**Honest gaps.** When the search budget is reached, remaining entities are reported as *unreviewed* rather than silently graded green. When research returns no permit figure, the Location Manager says what is unknown instead of inventing a number.

**Verified alternatives.** Suggesting a replacement name without checking it just moves the liability, so proposed alternatives are themselves run through a live search and only offered when they come back clear.

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

---

## Imagery and originality

All screenplay material in [`samples/`](samples/) is original, written for this project.

Photography in `apps/web/public/img/` is from Unsplash under the Unsplash License, stored locally rather than hot-linked so the app has no runtime dependency on a CDN. Provenance is listed in [`CREDITS.txt`](apps/web/public/img/CREDITS.txt).

No copyrighted film artwork, posters, logos, or trademarks appear anywhere in the project. This is deliberate: a candidate hero image turned out to be a wall of VHS covers and was rejected for exactly that reason.

## Licence

MIT. See [LICENSE](LICENSE).

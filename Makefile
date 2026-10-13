.PHONY: install dev dev-api dev-web check check-api check-web eval eval-api eval-browser spar fmt deploy smoke

install:
	cd backend && uv sync
	cd frontend && pnpm install

dev:
	$(MAKE) -j2 dev-api dev-web

dev-api:
	cd backend && uv run uvicorn kataribe.main:app --reload --port 8000

dev-web:
	cd frontend && pnpm dev

check: check-api check-web

check-api:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest -q

check-web:
	cd frontend && pnpm lint && pnpm test && pnpm build

# Streams real Japanese audio at the Live API. Costs quota and runs in real time.
eval: eval-api eval-browser

eval-api:
	cd backend && uv run pytest -m live -v

eval-browser:
	cd frontend && pnpm test:e2e

# Interviewer versus a simulated interviewee, on live audio both ways.
# PERSONA=haru|shigeru|kimiko  PATIENCE=5000  SECONDS=75  CLOSE=60 (closing cue, seconds)
spar:
	cd backend && uv run python spar.py \
		--persona $(or $(PERSONA),haru) \
		--seconds $(or $(SECONDS),75) \
		$(if $(PATIENCE),--patience $(PATIENCE),) \
		$(if $(CLOSE),--close-after $(CLOSE),)

fmt:
	cd backend && uv run ruff format . && uv run ruff check --fix .

# --- The deployed service (Cloud Run, Tokyo). See docs/deploy.md. ------------
PROJECT ?= gen-lang-client-0821244556
REGION ?= asia-northeast1
SERVICE ?= kataribe
BUCKET ?= kataribe-recordings-0821244556
# For strangers trying it from the start page; see docs/roadmap.md, "Judges try
# it themselves". Kept here, since every deploy replaces the service's settings.
#   TRY_LANGUAGES  en, then en,ja once the native-speaker review has passed
#   SHOWCASE       the demo persona's id: its family page, read-only, on the start page
#   VIDEO_URL      the public demo video
#   MIN_INSTANCES  1 while judges may arrive (until Nov 6), so none waits on a cold
#                  start of about five seconds; 0 afterwards
TRY_LANGUAGES ?= en
SHOWCASE ?=
VIDEO_URL ?=
MIN_INSTANCES ?= 1

# Built remotely by Cloud Build from the Dockerfile; nothing git-ignored is sent.
deploy:
	gcloud run deploy $(SERVICE) --source . --region $(REGION) --project $(PROJECT) \
		--service-account kataribe-run@$(PROJECT).iam.gserviceaccount.com \
		--allow-unauthenticated --no-cpu-throttling --max-instances 2 --memory 1Gi \
		--min-instances $(MIN_INSTANCES) \
		--set-env-vars "^;^KATARIBE_STORAGE=cloud;KATARIBE_GCP_PROJECT=$(PROJECT);KATARIBE_RECORDINGS_BUCKET=$(BUCKET);KATARIBE_TRY_LANGUAGES=$(TRY_LANGUAGES);KATARIBE_SHOWCASE_SENIOR=$(SHOWCASE);KATARIBE_VIDEO_URL=$(VIDEO_URL)" \
		--set-secrets KATARIBE_GEMINI_API_KEY=kataribe-gemini-api-key:latest,KATARIBE_TEAM_PASSWORD=kataribe-team-password:latest

# Real conversations on the deployed service, one from the console and one as a
# stranger from the start page, checked in the cloud, then forgotten. Costs a few
# cents of Gemini, and one of the day's visitor conversations.
smoke:
	cd frontend && \
		KATARIBE_URL=$$(gcloud run services describe $(SERVICE) --region $(REGION) --project $(PROJECT) --format='value(status.url)') \
		KATARIBE_TEAM_PASSWORD=$$(gcloud secrets versions access latest --secret=kataribe-team-password --project $(PROJECT)) \
		KATARIBE_STORAGE=cloud KATARIBE_GCP_PROJECT=$(PROJECT) KATARIBE_RECORDINGS_BUCKET=$(BUCKET) \
		pnpm exec playwright test -c playwright.smoke.config.ts

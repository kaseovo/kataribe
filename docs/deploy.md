# Deployment

The app runs on Cloud Run in Tokyo, from one image that serves both the API and the built frontend.

**Live:** <https://kataribe-uxxefqeqqq-an.a.run.app> (also <https://kataribe-398069256773.asia-northeast1.run.app>)

| | |
| --- | --- |
| Project | `gen-lang-client-0821244556` ("AI Builder Cup 2026"), the same project as the Gemini key |
| Region | `asia-northeast1` (Tokyo), so the seniors' voices and stories stay in Japan |
| Service | `kataribe`, running as the `kataribe-run` service account |
| Records | Firestore, `(default)` database, native mode |
| Recordings | Cloud Storage, `gs://kataribe-recordings-0821244556`, private, public access prevented |
| Secrets | `kataribe-gemini-api-key`, `kataribe-team-password` in Secret Manager, readable only by `kataribe-run` |
| Budget | ¥4,500 a month on the project, emails at 50%, 90%, 100% and a forecast of 100% |

## Who can reach what

Everything sits behind the team password except the start page, what a family page needs, and visitors' screens.

- **The start page**, `/`: open to anyone. A stranger, such as a judge, makes a persona of their own there and talks to it. See *Judges try it themselves* in [roadmap.md](roadmap.md).
- **Family page**, `/family/{senior_id}`: open to anyone with the link. It shows only stories that were agreed to be shared. The showcase persona's (`SHOWCASE` in the Makefile) takes no questions.
- **A senior's own screen**, `/talk/{senior_id}`: the page is open, but talking needs the team password, which the browser asks for. A tablet in someone's home stays signed in. A stranger able to talk as someone could put invented stories into their life story, which their family reads.
- **Visitor personas**, made from the start page: their screen works for anyone with its link, which is 128 random bits. All visitors together get 30 conversations and 100 new personas a day, counted in Japan time.
- **The console**, `/console`, every transcript and every recording: the team password.

To sign in, open the URL and enter any user name and the password:

```sh
gcloud secrets versions access latest --secret=kataribe-team-password
```

## Deploying a change

```sh
make deploy   # builds the Dockerfile on Cloud Build, rolls out a new revision
make smoke    # a real conversation on the live service, checked, then forgotten
```

`make deploy` sends the working tree minus anything git-ignored, so `backend/.env` never leaves the machine. Every revision is kept: a bad one is undone by sending traffic back to the previous revision in the Cloud Run console.

`make smoke` costs a few cents of Gemini. It checks that a stranger reaches only the start page and a family page, then holds a conversation with a person of its own, confirms the recording reached the bucket, the transcript reached Firestore and a story was extracted after the upload. Then it does what a judge does, with no password: makes a visitor persona from the start page, talks, ends early, shares on the end screen, and plays a quote from its family page. It forgets both people and everything they produced.

A health check cannot see a Gemini key that has stopped working, which is what judges would hit, so `make smoke` is run by hand every morning while judging lasts.

The `gcloud` CLI needs a Python with SSL. If it fails to load, point it at one: `export CLOUDSDK_PYTHON=/opt/homebrew/bin/python3`.

## While judges may arrive

From the submission on Oct 17 to the end of judging on Nov 6. Decided in [roadmap.md](roadmap.md), *Judges try it themselves*.

- **Gemini must be paid for.** The key bills against prepaid credits in AI Studio, and when they ran out on 2026-10-12 every conversation was refused with `1011 Your prepayment credits are depleted`. Token minting kept working, so nothing but a real conversation shows it. The Cloud trial credit does not cover Gemini.
- **The nightly eval gets a key of its own**, in the repository's `KATARIBE_GEMINI_API_KEY` secret, so testing cannot use up what judges need.
- **One instance stays warm**, `MIN_INSTANCES=1`, the Makefile's default until Nov 6. A cold start measured 4.6 s, nearly all of it Cloud Run starting the container; startup CPU boost was already on.
- **The deploy sets** `TRY_LANGUAGES=en` (`en,ja` once the native-speaker review passes), `SHOWCASE` to the demo persona and `VIDEO_URL` to the video.
- **Watched by** an uptime check on `/api/health`, Error Reporting by email, the budget above, and `make smoke` each morning.
- **Frozen.** The submitted commit is tagged and deployed. Only an outage is fixed, and each fix is noted in the README.
- **Afterwards**, on Nov 7 unless the project is shortlisted, every visitor persona is forgotten, as the start page promises, and `MIN_INSTANCES` goes back to 0:

```sh
cd backend
KATARIBE_STORAGE=cloud KATARIBE_GCP_PROJECT=gen-lang-client-0821244556 \
  KATARIBE_RECORDINGS_BUCKET=kataribe-recordings-0821244556 \
  uv run python forget.py --visitors
```

## Forgetting a person

When a family asks for someone to be removed:

```sh
cd backend
KATARIBE_STORAGE=cloud KATARIBE_GCP_PROJECT=gen-lang-client-0821244556 \
  KATARIBE_RECORDINGS_BUCKET=kataribe-recordings-0821244556 \
  uv run python forget.py --senior-id <id>
```

Their sessions and every recording go, with their stories, plan and family questions.

## Why it is set up this way

Each of these was a real failure, or would have been.

- **Cloud storage, not the container's disk.** Cloud Run's disk does not survive a restart or a redeploy, and the service has to keep its data through the evaluation period.
- **Recordings upload in 16 MiB parts.** Cloud Run refuses any HTTP/1 request over 32 MiB, and ten minutes of conversation is close to 60 MB. The parts are joined inside the bucket, so a recording never passes through the server whole.
- **`--no-cpu-throttling`.** Stories are extracted after the upload's response has been sent. By default Cloud Run all but stops the CPU at that point, and processing would stall. The cost is that an instance is billed for as long as it is up, which `--max-instances 2` caps.
- **The microphone worklet is public.** `/capture-processor.js` is fetched apart from the page's other requests. Behind the password it got 401 in the smoke test and the microphone never opened.
- **No startup recovery of stalled processing.** With more than one instance, each would claim the same session. A session whose processing stalled shows "Process again" in the console instead.

## Setting it up again from nothing

This was done once, on 2026-10-10. Kept so it can be repeated or audited.

```sh
P=gen-lang-client-0821244556; R=asia-northeast1; B=kataribe-recordings-0821244556
SA=kataribe-run@$P.iam.gserviceaccount.com

gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  firestore.googleapis.com storage.googleapis.com secretmanager.googleapis.com --project $P
gcloud firestore databases create --location=$R --type=firestore-native --project $P
gcloud storage buckets create gs://$B --project $P --location=$R \
  --uniform-bucket-level-access --public-access-prevention

gcloud iam service-accounts create kataribe-run --display-name="kataribe on Cloud Run" --project $P
gcloud projects add-iam-policy-binding $P --member=serviceAccount:$SA --role=roles/datastore.user --condition=None
gcloud storage buckets add-iam-policy-binding gs://$B --member=serviceAccount:$SA --role=roles/storage.objectAdmin

# The key, from backend/.env; the password, made up fresh.
gcloud secrets create kataribe-gemini-api-key --data-file=- --replication-policy=user-managed --locations=$R --project $P
gcloud secrets create kataribe-team-password --data-file=- --replication-policy=user-managed --locations=$R --project $P
for s in kataribe-gemini-api-key kataribe-team-password; do
  gcloud secrets add-iam-policy-binding $s --member=serviceAccount:$SA \
    --role=roles/secretmanager.secretAccessor --project $P
done
```

To run the store's contract tests against the real services, after `gcloud auth application-default login`:

```sh
cd backend
KATARIBE_TEST_GCP_PROJECT=gen-lang-client-0821244556 \
  KATARIBE_TEST_BUCKET=kataribe-recordings-0821244556 uv run pytest tests/test_store.py
```

Each run works under its own prefix and removes everything it made.

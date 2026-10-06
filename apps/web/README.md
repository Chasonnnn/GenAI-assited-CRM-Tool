# Surrogacy Force - Web Frontend

Next.js 14 frontend for the Surrogacy Force platform.

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Components**: shadcn/ui
- **State**: React Query (TanStack Query)
- **Auth**: Cookie-based sessions via backend

## Getting Started

```bash
# Install dependencies
pnpm install

# Start dev server (requires backend running on :8000)
pnpm dev

# Build for production
pnpm build
```

## End-to-End Tests (local pilot)

These tests run locally only; CI does not run them. They live in `e2e/tests/` and use the
[`e2e`](https://github.com/tester-army/e2e) runner with exact locators, so a run makes no model calls.

```bash
# Requires the compose database and a synced API virtualenv
docker compose up -d db
(cd ../api && uv sync)

pnpm run test:e2e               # all tests
pnpm run test:e2e --tag forms   # one flow
E2E_RESEED=1 pnpm run test:e2e  # rebuild the seeded template first
```

Each run starts its own stack: a fresh `crm_e2e` database, the API on `:8100`, and the web app on `:3100`.
The API loads no `.env`, so it holds no provider credentials and cannot send email or SMS.
Its encryption and hash keys are fixed test values that protect only the generated mock data.

`crm_e2e` is a clone of `crm_e2e_template`, which holds the mock data from `seed_mock_data.py`:
5,000 surrogates, 100 intended parents, and 300 matches by default (`E2E_SEED_SURROGATES`,
`E2E_SEED_INTENDED_PARENTS`, `E2E_SEED_MATCH_COUNT`). The first run builds the template in about
two minutes; later runs clone it in seconds. The template rebuilds itself when the migrations, the
seeder, or the seed sizes change, or on `E2E_RESEED=1`. Drop it to free space:
`docker compose exec db dropdb -U postgres crm_e2e_template`.

Tests sign in with the saved sessions from `e2e/tests/auth.setup.e2e.ts` (`admin`, `case-manager`).
A failed run writes the screen at failure and a trace under `.e2e/`.
Stop a running `pnpm dev` first: Next.js allows one dev server per project.

## Structure

```
app/
├── (app)/           # Authenticated routes (sidebar layout)
│   ├── dashboard/
│   ├── surrogates/
│   ├── intended-parents/
│   ├── donors/            # Egg and sperm donor tabs and record detail
│   ├── tasks/
│   ├── reports/
│   ├── ai-assistant/
│   └── settings/
├── (auth)/          # Login/logout flows
└── layout.tsx       # Root layout with providers

components/
├── ui/              # shadcn/ui primitives
└── *.tsx            # App-specific components

lib/
├── api/             # API client functions
├── hooks/           # React Query hooks
└── *.ts             # Utilities
```

## Environment Variables

See `apps/api/.env.example` for required backend config.

Frontend expects:
- Backend at `http://localhost:8000` (dev)
- Cookie `crm_session` set by backend

## Design System

Uses shadcn/ui with custom theming. See `globals.css` for:
- CSS custom properties for colors
- View Transitions API for theme toggle
- Noto Sans font

## Surrogate Email Compose Attachments

The surrogate compose dialog supports Gmail-style drag-and-drop attachments.

- Users can upload new files directly in compose, or select existing surrogate attachments.
- Send is blocked until all selected attachments are malware-scanned and `clean`.
- Compose send limits are:
  - Max `10` attachments
  - Max `18 MiB` total selected bytes (pre-encoding)

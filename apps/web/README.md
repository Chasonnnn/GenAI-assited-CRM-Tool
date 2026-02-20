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

## Structure

```
app/
├── (app)/           # Authenticated routes (sidebar layout)
│   ├── dashboard/
│   ├── surrogates/
│   ├── intended-parents/
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

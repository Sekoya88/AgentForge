# Frontend Sentry Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Sentry error tracking to the Next.js frontend so runtime errors, unhandled rejections, and API failures are captured automatically, mirroring the backend Sentry integration that already exists.

**Architecture:** Use `@sentry/nextjs` v8+ SDK with Next.js instrumentation hook (stable in Next.js 15, no flag needed). Sentry is disabled by default (no `NEXT_PUBLIC_SENTRY_DSN` set) so no cost impact in dev. Errors are captured globally via `global-error.tsx` (App Router requirement) and the instrumentation hook.

**Tech Stack:** `@sentry/nextjs` v8+, Next.js 15 App Router instrumentation.ts, `global-error.tsx`, `NEXT_PUBLIC_SENTRY_DSN` env var

---

### Task 1: Install Sentry SDK

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Install `@sentry/nextjs`**

```bash
cd frontend && npm install @sentry/nextjs
```

Expected: package added at v8+, no peer dep errors.

- [ ] **Step 2: Verify installation**

```bash
cd frontend && node -e "require('@sentry/nextjs'); console.log('ok')"
```

Expected: prints `ok`.

---

### Task 2: Sentry config files

**Files:**
- Create: `frontend/sentry.client.config.ts`
- Create: `frontend/sentry.server.config.ts`
- Create: `frontend/sentry.edge.config.ts`

- [ ] **Step 1: Write `sentry.client.config.ts`**

```typescript
// frontend/sentry.client.config.ts
import * as Sentry from "@sentry/nextjs";

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT ?? "development",
    tracesSampleRate: 0.1,
    integrations: [Sentry.replayIntegration({ maskAllText: false })],
    replaysSessionSampleRate: 0.0,
    replaysOnErrorSampleRate: 1.0,
  });
}
```

- [ ] **Step 2: Write `sentry.server.config.ts`**

```typescript
// frontend/sentry.server.config.ts
import * as Sentry from "@sentry/nextjs";

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT ?? "development",
    tracesSampleRate: 0.1,
  });
}
```

- [ ] **Step 3: Write `sentry.edge.config.ts`**

```typescript
// frontend/sentry.edge.config.ts
import * as Sentry from "@sentry/nextjs";

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT ?? "development",
    tracesSampleRate: 0.1,
  });
}
```

---

### Task 3: Next.js instrumentation hook

**Files:**
- Create: `frontend/instrumentation.ts`

`instrumentation.ts` is stable in Next.js 15 — no experimental flag needed.

- [ ] **Step 1: Write `instrumentation.ts`**

```typescript
// frontend/instrumentation.ts
import * as Sentry from "@sentry/nextjs";

export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("./sentry.server.config");
  }
  if (process.env.NEXT_RUNTIME === "edge") {
    await import("./sentry.edge.config");
  }
}

// Correct Next.js 15 signature — delegate directly to Sentry
export const onRequestError = Sentry.captureRequestError;
```

---

### Task 4: Global error boundary (App Router requirement)

**Files:**

- Create: `frontend/src/app/global-error.tsx`

Without this, unhandled errors in the root layout are not caught by Sentry in App Router.

- [ ] **Step 1: Write `global-error.tsx`**

```tsx
// frontend/src/app/global-error.tsx
"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html>
      <body>
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
          <h2 className="text-xl font-semibold">Something went wrong</h2>
          <button
            onClick={reset}
            className="rounded bg-primary px-4 py-2 text-primary-foreground"
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
```

---

### Task 5: Update Next.js config

**Files:**

- Modify: `frontend/next.config.ts`

Current content is minimal (empty config). Replace entirely:

- [ ] **Step 1: Wrap with `withSentryConfig` using v8 API**

```typescript
// frontend/next.config.ts
import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs";

const nextConfig: NextConfig = {
  /* config options here */
};

export default withSentryConfig(nextConfig, {
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  authToken: process.env.SENTRY_AUTH_TOKEN,
  // Only upload source maps when SENTRY_AUTH_TOKEN is set (CI/prod)
  sourcemaps: {
    disable: !process.env.SENTRY_AUTH_TOKEN,
  },
  telemetry: false,
});
```

Note: `silent`, `disableServerWebpackPlugin`, `disableClientWebpackPlugin` were removed in v8. Use `sourcemaps.disable` instead.

---

### Task 6: Environment variables

**Files:**

- Modify: `.env.example`

- [ ] **Step 1: Add Sentry vars to `.env.example`**

Add at the end of the root `.env.example`:

```bash
# Sentry (frontend) — optional, leave blank to disable
NEXT_PUBLIC_SENTRY_DSN=
NEXT_PUBLIC_SENTRY_ENVIRONMENT=development
# Sentry source maps upload (CI/prod only — set as repo secrets)
SENTRY_AUTH_TOKEN=
SENTRY_ORG=
SENTRY_PROJECT=
```

- [ ] **Step 2: Update CI frontend build step in `.github/workflows/ci.yml`**

Find the frontend build step (it has `run: npm run build` under the `frontend` working-directory). Replace that entire step with:

```yaml
      - name: Build frontend
        working-directory: frontend
        env:
          NEXT_PUBLIC_API_URL: http://localhost:8000
          SENTRY_AUTH_TOKEN: ${{ secrets.SENTRY_AUTH_TOKEN }}
          SENTRY_ORG: ${{ secrets.SENTRY_PROJECT }}
          SENTRY_PROJECT: ${{ secrets.SENTRY_PROJECT }}
        run: npm run build
```

If those secrets are not set in the repo, `SENTRY_AUTH_TOKEN` will be empty → `sourcemaps.disable: true` → no upload attempt → build succeeds.

---

### Task 7: Verify build

- [ ] **Step 1: Build with no DSN (default dev mode)**

```bash
cd frontend && npm run build
```

Expected: Builds successfully. No Sentry errors (DSN is empty, Sentry skips init).

- [ ] **Step 2: Verify no runtime errors in dev**

```bash
cd frontend && npm run dev
```

Open `http://localhost:3000`, check browser console — no Sentry-related errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/sentry.client.config.ts frontend/sentry.server.config.ts \
        frontend/sentry.edge.config.ts frontend/instrumentation.ts \
        frontend/src/app/global-error.tsx \
        frontend/next.config.ts frontend/package.json frontend/package-lock.json \
        .env.example .github/workflows/ci.yml
git commit -m "feat(frontend): add Sentry error tracking (opt-in via NEXT_PUBLIC_SENTRY_DSN)"
```

import type { E2EConfig } from "e2e"
import { web } from "@e2e-dev/web"

import { API_PORT, DEV_SECRET, WEB_PORT, WEB_URL } from "./e2e/local-stack"

// Local-only pilot: runs on demand and is not part of CI. No `agents` entry is
// configured, so tests use exact locators and assertions and make no model calls.
export default {
    tests: "e2e/tests/**/*.e2e.ts",
    targets: [
        {
            engine: web(),
            app: {
                url: WEB_URL,
                command: {
                    executable: "node",
                    args: ["e2e/stack.mjs"],
                    env: {
                        E2E_WEB_PORT: String(WEB_PORT),
                        E2E_API_PORT: String(API_PORT),
                        E2E_DEV_SECRET: DEV_SECRET,
                        E2E_PG_PORT: process.env.E2E_PG_PORT ?? "5432",
                    },
                    startupTimeout: 180_000,
                    log: ".e2e/logs/stack.log",
                },
            },
        },
    ],
    // Every run starts from a fresh database, so tests share one worker and one org.
    workers: 1,
} satisfies E2EConfig

/* global process, console, fetch, setTimeout */
// Starts the disposable stack that local e2e runs drive: a fresh `crm_e2e` database,
// the API, and the Next.js dev server. `e2e.config.ts` runs this as the target's
// `app.command` and stops it when the run ends.
//
// The API starts in a directory without a `.env` and receives only the variables built
// here. It therefore holds no provider credentials, and no test can send email or SMS.
//
// `crm_e2e` is cloned from `crm_e2e_template`, which holds the migrated schema and the mock
// data of apps/api/scripts/seed_mock_data.py at the sizes in E2E_SEED_*. The template is
// rebuilt when a migration, the seeder, a size, or E2E_RESEED=1 changes its stamp.
import { spawn, spawnSync } from "node:child_process"
import { createHash, randomBytes } from "node:crypto"
import { existsSync, mkdirSync, readdirSync, readFileSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const webDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")
const apiDir = path.resolve(webDir, "../api")
const python = path.join(apiDir, ".venv/bin/python")
const stackDir = path.join(webDir, ".e2e/stack")

const webPort = requireEnv("E2E_WEB_PORT")
const apiPort = requireEnv("E2E_API_PORT")
const devSecret = requireEnv("E2E_DEV_SECRET")
const pgPort = process.env.E2E_PG_PORT ?? "5432"
const database = "crm_e2e"
const templateDatabase = "crm_e2e_template"
const seedSizes = {
    SEED_RANDOM_SEED: "20260224",
    SEED_SURROGATES: requireEnv("E2E_SEED_SURROGATES"),
    SEED_INTENDED_PARENTS: requireEnv("E2E_SEED_INTENDED_PARENTS"),
    SEED_MATCH_COUNT: requireEnv("E2E_SEED_MATCH_COUNT"),
}

function requireEnv(name) {
    const value = process.env[name]
    if (!value) {
        console.error(`${name} is not set; start the stack through \`e2e run\`.`)
        process.exit(2)
    }
    return value
}

if (!existsSync(python)) {
    console.error(`${python} is missing; run \`uv sync\` in apps/api first.`)
    process.exit(2)
}
mkdirSync(stackDir, { recursive: true })

// The encryption and hash keys are fixed because the template database outlives a run and
// every run must read it. They protect generated mock data on a local database only, so they
// are test values, not credentials. The session key stays random: sessions never persist.
const fixedKey = (label) => createHash("sha256").update(`e2e-local-${label}`).digest()
const fernetKey = fixedKey("fernet").toString("base64url") + "="
const databaseUrl = (name) => `postgresql+psycopg://postgres:postgres@127.0.0.1:${pgPort}/${name}`
const apiEnv = {
    PATH: process.env.PATH ?? "",
    HOME: process.env.HOME ?? "",
    PYTHONPATH: apiDir,
    ENV: "test",
    TESTING: "1",
    DATABASE_URL: databaseUrl(database),
    JWT_SECRET: randomBytes(32).toString("hex"),
    FERNET_KEY: fernetKey,
    META_ENCRYPTION_KEY: fernetKey,
    VERSION_ENCRYPTION_KEY: fernetKey,
    DATA_ENCRYPTION_KEY: fernetKey,
    PII_HASH_KEY: fixedKey("pii-hash").toString("hex"),
    DEV_SECRET: devSecret,
    API_BASE_URL: `http://localhost:${apiPort}`,
    FRONTEND_URL: `http://localhost:${webPort}`,
    CORS_ORIGINS: `http://localhost:${webPort}`,
    // The seeded developer opens the ops console; outside production the allowlist alone
    // grants platform access.
    PLATFORM_ADMIN_EMAILS: "developer@test.com",
    // Every request comes from 127.0.0.1, so the production limit of 5 per minute on the
    // invite and login endpoints would fail a run that opens several invite pages.
    RATE_LIMIT_AUTH: "60",
}

function runOrExit(label, args, env = apiEnv) {
    const result = spawnSync(python, args, { cwd: stackDir, env, stdio: ["inherit", "pipe", "inherit"], encoding: "utf8" })
    if (result.status !== 0) {
        console.error(`${label} failed.`)
        process.exit(1)
    }
    return result.stdout
}

const seederPath = path.join(apiDir, "scripts/seed_mock_data.py")
const stamp = createHash("sha256")
    .update(readdirSync(path.join(apiDir, "alembic/versions")).sort().join("\n"))
    .update(readFileSync(seederPath))
    .update(JSON.stringify(seedSizes))
    .update(fernetKey)
    .digest("hex")
const forceRebuild = process.env.E2E_RESEED ? "1" : "0"

// Drops `crm_e2e`, then clones the template when its stamp matches; otherwise prints "rebuild".
const prepareDatabase = `
import psycopg, sys
with psycopg.connect("postgresql://postgres:postgres@127.0.0.1:${pgPort}/postgres", autocommit=True) as connection:
    connection.execute("DROP DATABASE IF EXISTS ${database} WITH (FORCE)")
    row = connection.execute(
        "SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname = %s", ("${templateDatabase}",)
    ).fetchone()
    if row is not None and row[0] == sys.argv[1] and sys.argv[2] == "0":
        connection.execute("CREATE DATABASE ${database} TEMPLATE ${templateDatabase}")
        print("cloned")
    else:
        connection.execute("DROP DATABASE IF EXISTS ${templateDatabase} WITH (FORCE)")
        connection.execute("CREATE DATABASE ${templateDatabase}")
        print("rebuild")
`
const prepared = runOrExit("Database reset (is `docker compose up -d db` running?)", ["-c", prepareDatabase, stamp, forceRebuild])
if (prepared.trim() === "rebuild") {
    console.log(`Seeding ${templateDatabase} with ${seedSizes.SEED_SURROGATES} surrogates; later runs clone it.`)
    const templateEnv = { ...apiEnv, ...seedSizes, DATABASE_URL: databaseUrl(templateDatabase) }
    runOrExit("Migration", ["-m", "alembic", "-c", path.join(apiDir, "alembic.ini"), "upgrade", "head"], templateEnv)
    runOrExit("Seeding", ["-m", "scripts.seed_mock_data"], templateEnv)
    const publishTemplate = `
import psycopg, sys
from psycopg import sql
with psycopg.connect("postgresql://postgres:postgres@127.0.0.1:${pgPort}/postgres", autocommit=True) as connection:
    # COMMENT is a utility statement and takes no bind parameters.
    connection.execute(sql.SQL("COMMENT ON DATABASE ${templateDatabase} IS {}").format(sql.Literal(sys.argv[1])))
    connection.execute("CREATE DATABASE ${database} TEMPLATE ${templateDatabase}")
`
    runOrExit("Template publish", ["-c", publishTemplate, stamp])
}

const children = []
let stopping = false

function start(label, command, args, options) {
    const child = spawn(command, args, { stdio: "inherit", ...options })
    children.push(child)
    child.on("exit", (code) => {
        if (stopping) return
        console.error(`${label} exited with code ${code}.`)
        stop(1)
    })
    return child
}

function stop(exitCode) {
    if (stopping) return
    stopping = true
    for (const child of children) child.kill("SIGTERM")
    // The runner allows 10 s for shutdown; leave it room to report.
    setTimeout(() => {
        for (const child of children) child.kill("SIGKILL")
        process.exit(exitCode)
    }, 8_000).unref()
    Promise.all(children.map((child) => new Promise((resolve) => child.once("exit", resolve)))).then(
        () => process.exit(exitCode),
    )
}

process.on("SIGTERM", () => stop(0))
process.on("SIGINT", () => stop(0))

start(
    "API",
    python,
    ["-m", "uvicorn", "app.main:app", "--app-dir", apiDir, "--host", "127.0.0.1", "--port", apiPort],
    { cwd: stackDir, env: apiEnv },
)

async function waitForApi() {
    const deadline = Date.now() + 60_000
    while (Date.now() < deadline) {
        try {
            const response = await fetch(`http://127.0.0.1:${apiPort}/health`)
            if (response.ok) return
        } catch {
            // Not listening yet.
        }
        await new Promise((resolve) => setTimeout(resolve, 500))
    }
    console.error("API did not become healthy within 60 s.")
    stop(1)
}

await waitForApi()

// The web server starts only after the API is healthy, so a ready web URL means a ready stack.
if (!stopping) {
    start("Web", path.join(webDir, "node_modules/.bin/next"), ["dev", "--port", webPort], {
        cwd: webDir,
        env: {
            PATH: process.env.PATH ?? "",
            HOME: process.env.HOME ?? "",
            NEXT_PUBLIC_API_BASE_URL: `http://localhost:${apiPort}`,
            NEXT_TELEMETRY_DISABLED: "1",
        },
    })
}

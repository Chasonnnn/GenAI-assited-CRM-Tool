# Operations template CLI

`ops` manages version-controlled email, form, and workflow templates in the Ops template library.
It does not import application code, access the database directly, install templates into tenant
records, send email, execute workflows, activate or delete records, or change system-email
settings. Publishing makes a template available in the library to its audience; it does not update
copies that organizations have already adopted.

Python 3.14 is required.

## Quick start

```sh
uv tool install ./apps/ops-cli

# Configure a named target once.
ops config set-env staging \
  --api-url https://api.example.com \
  --ops-url https://ops.example.com

# Complete the normal Ops browser login and MFA, then enter the displayed code at /ops/cli.
ops login --env staging
ops whoami --env staging

# Create, validate, push, preview, and publish one template.
ops templates init email welcome
ops templates validate welcome --env staging
ops templates push welcome --env staging
ops templates preview email welcome --env staging --output welcome-preview.html
ops templates publish welcome --env staging --org agency-one

# Revoke the CLI session when finished.
ops logout --env staging
```

`ops login` opens the configured Ops site for its normal browser login and MFA flow. The CLI shows
a short one-time verification code, which you enter on `/ops/cli`, and waits up to ten minutes for
approval. `--no-browser` does not open a local browser; it prints the URL and code so the flow can
be completed in another browser. There is no token copying or manual credential management.

The browser session remains distinct from the automatically stored, template-scoped CLI session.
The CLI session lasts eight hours, and `ops logout` revokes it remotely and removes it locally. If
remote revocation fails, logout fails and retains the local session so revocation can be retried.
Session material is stored by API origin in the OS keyring when the optional `keyring` extra is
installed, with a mode `0600` XDG configuration file as fallback. It is never a command argument or
bundle content.

## Global behavior

```text
ops [--json] COMMAND ...
```

Put `--json` before the command to emit stable JSON on stdout. Normal structured command results
are also JSON; diagnostics go to stderr. Successful commands exit `0`. Invalid input, unavailable
authentication, network/server errors, and incomplete write batches exit nonzero. The HTTP client
has a 20-second request timeout, refuses redirects, sanitizes server errors, and permits plain HTTP
only for explicit localhost/loopback development. `COMMAND --help` displays Click's generated help.

## Complete command reference

### Configuration and authentication

#### `ops config set-env NAME --api-url URL --ops-url URL`

Creates or replaces the named environment profile in the XDG user configuration directory.
`--api-url` must be an HTTPS origin with no path; `--ops-url` is the browser-facing Ops origin.
Loopback HTTP is accepted for development. Output confirms the configured environment.

```sh
ops config set-env production \
  --api-url https://api.example.com --ops-url https://ops.example.com
```

#### `ops login --env NAME [--no-browser]`

Starts the browser approval flow described above, displays its one-time code, and waits for up to
ten minutes. By default it opens the approval URL. `--no-browser` prints the URL/code for use in a
different or browserless environment. On approval, it automatically stores a separate eight-hour,
template-scoped CLI session and prints the authenticated identity. It never asks the operator to
copy or paste a token.

#### `ops whoami --env NAME`

Prints the identity and expiry associated with the stored CLI session. It has no remote side
effects.

#### `ops logout --env NAME`

Revokes the CLI session remotely, then deletes it locally, and prints a confirmation. It does not
log out the distinct browser session. The local session is retained if remote revocation fails.

### Local templates and inspection

`KIND` is exactly `email`, `form`, or `workflow`. A `PATH` accepted by bundle-aware commands may be
a template directory, a bundle directory, or a `bundle.json` path; where optional it defaults to
`.`.

#### `ops templates init KIND NAME`

Creates a new `NAME/` template directory with a minimal example. `NAME` must be a lowercase stable
slug. Email scaffolds also include `body.html` and `sample-data.json`. The command refuses an
existing path and makes no server request.

```sh
ops templates init form intake
ops templates init workflow follow-up
```

#### `ops templates validate [PATH] [--env NAME]`

Loads every local template and reports validity, warnings, and bindings. Without `--env`, checks
cover only strict file shape, path containment, key syntax, duplicate identities, and draft-object
shape. With `--env`, each draft is also sent for canonical server validation, which detects current
fields, bindings, sanitization, and warnings. Validation does not save a draft.

#### `ops templates list KIND --env NAME`

Lists remote library records of the selected kind. It makes no changes.

#### `ops templates show KIND KEY --env NAME`

Prints one remote library record, including its draft/publication and revision metadata. `KEY` must
match the key rules below.

#### `ops templates pull KIND KEY --env NAME [--output DIR] [--force]`

Writes the remote draft to `DIR/KEY/template.json` (`DIR` defaults to `.`) and records its ID and
revision in `DIR/KEY/.ops-state.json`. It refuses a nonempty target unless `--force` is given.
`--force` permits writing into that directory but does not delete unrelated files. Pulling does not
publish or alter the server record.

#### `ops templates diff [PATH] --env NAME [--published]`

Server-validates each local draft, then reports its canonical local and remote values and whether
they differ. By default it compares with the remote draft; `--published` compares with the current
published value. It does not write locally or remotely.

### Writes and publication

#### `ops templates push [PATH] --env NAME`

Server-validates all templates before any write, then saves their canonical drafts sequentially.
It does not publish them or change their audience. Each success updates local `.ops-state.json`.

#### `ops templates publish [PATH] --env NAME AUDIENCE [--replace-audience]`

Validates and publishes canonical drafts sequentially. Choose exactly one audience form:

* `--org SLUG_OR_ID` (repeatable) publishes to those exact organizations;
* `--all-orgs` publishes to every organization;
* `--keep-audience` retains an already-published template's audience.

Organization values resolve only by exact slug or ID across all result pages. If an existing
publication's audience would change, `--replace-audience` is also required. `--keep-audience`
cannot be used for an unpublished template. Publication is library-only: it neither installs a
tenant copy nor updates a previously adopted copy.

```sh
ops templates publish templates --env staging \
  --org agency-one --org 00000000-0000-0000-0000-000000000001
ops templates publish templates --env staging --all-orgs
ops templates publish templates --env staging --keep-audience
ops templates publish templates --env staging --org agency-one --replace-audience
```

#### `ops templates bind KIND KEY --id RECORD_UUID --env NAME [--path PATH]`

Explicitly adopts an existing remote record found by ID under the local stable `KEY`. `PATH`
defaults to `.` and must contain that kind/key. Bind applies the existing canonical server draft
with its observed revision precondition and records the resulting ID/revision locally. Local draft
content is intentionally left unchanged—and may therefore be stale—until reviewed and pushed.

Writes use optimistic revisions from each template directory's `.ops-state.json`. Existing remote
keys cannot be changed without a local baseline; pull or bind first. Stale writes and concurrent
creates are not silently rebased. For bundles, every item is validated before the first write;
writes then run in manifest order and stop at the first failure. Output labels items successful,
failed, or unattempted and a partial batch exits nonzero. There is no bundle rollback. Publication
is atomic per template, and an unchanged desired state creates no publication version. Following a
lost response, recovery succeeds only if a reread exactly matches the entire desired canonical
draft, published value when publishing, and explicit audience.

### Organizations and status

#### `ops orgs list --env NAME [--search TEXT]`

Prints the first page of organizations matching `TEXT` (empty by default), with a limit of 100 and
offset 0. It does not modify organizations.

#### `ops status --env NAME --org SLUG_OR_ID`

Resolves one exact organization and reports every library template's status, audience eligibility,
organization-specific hidden state, and computed visibility. A template is visible only when it is
eligible, not hidden, and has `published_version > 0`. This is an Ops library/audience view: it
cannot prove tenant installation or downstream runtime health.

### Safe previews

#### `ops templates preview email PATH --env NAME [--output FILE]`

Requires exactly one email template. The server renders it using `sample-data.json` (or an empty
object), and the CLI writes the returned HTML to `FILE`, defaulting to `preview.html`. Output reports
the file, rendered subject, and warnings. It never sends email. Treat rendered HTML as untrusted
when opening it locally.

#### `ops templates preview form PATH --env NAME [--open|--no-open]`

Requires exactly one form with a baseline from a prior push/pull/bind. It verifies that the server's
saved canonical draft exactly matches the local canonical draft, then prints the saved Ops form URL
and ID. It opens that URL by default; `--no-open` only prints it. This is not an unsaved local form
preview: push local changes first.

#### `ops templates preview workflow PATH`

Requires exactly one workflow and prints its local draft as a structured summary with
`executed: false`. It is entirely local and never executes the workflow.

## Bundle format

`bundle.json` has exactly these fields and must contain at least one relative template directory:

```json
{"version": 1, "templates": ["emails/welcome", "forms/intake"]}
```

Each template directory contains `template.json`:

```json
{"version": 1, "type": "email", "key": "welcome", "body_file": "body.html",
 "draft": {"name": "Welcome", "subject": "Welcome, {{first_name}}"}}
```

Keys match `[a-z0-9][a-z0-9-]*` and are at most 100 characters. Email `body_file` replaces—and
cannot be combined with—`draft.body`. Optional `sample-data.json` must be an object. Null draft
values are retained. Manifest and envelope fields are strict, duplicate type/key pairs are
rejected, and paths are checked after symlink resolution to prevent escaping their bundle/template
directory. Generated `.ops-state.json` files contain only API-origin-specific IDs and observed
revisions, never secrets; state follows each template between standalone and bundle layouts.

## Server rollout and limitations

Deploy the API and Ops web changes together after applying all three additive migrations through
the normal authorized migration process:

* `20260919_0100_ops_cli_tokens`
* `20260919_0200_template_cli_identity`
* `20260919_0300_ops_cli_login`

Existing templates keep their IDs and content; keys remain unset until explicitly bound. Existing
browser tabs must reload: template update and publication requests require `expected_version`,
including workflow edit revisions (`current_version`). The CLI provides neither historical rollback
nor tenant-copy updates. Installation performs no production migration or deployment.

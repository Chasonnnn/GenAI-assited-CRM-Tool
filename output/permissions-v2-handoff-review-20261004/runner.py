"""Clone metadata collection; only aggregates and an encrypted ledger reach stdout."""

from __future__ import annotations

import base64
import contextlib
import gzip
import hashlib
import json
import logging
import os
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlsplit

SOURCE_COMMIT = "91da87428dc6d90ac051f96a25ae2decf0f6de43"
SENTINEL = "permission_handoff_review_guard_app"
PHASE = "configuration"
MAX_LEDGER_BYTES = 64 * 1024 * 1024
CHUNK_CHARACTERS = 120_000
COLLECTOR_CODES = {
    "metadata_row_limit_exceeded",
    "invalid_source_commit",
    "session_has_pending_writes",
    "read_only_transaction_required",
    "consistent_snapshot_required",
    "utc_database_session_required",
    "canonical_phase_query_disagreement",
}


class CollectionBlocked(Exception):
    """Only a static, non-sensitive condition may be emitted."""


def require(condition, code):
    if not condition:
        raise CollectionBlocked(code)


def safe_error_diagnostics(error):
    sqlstate = None
    for source in (error, getattr(error, "orig", None), error.__cause__):
        value = getattr(source, "sqlstate", None)
        if isinstance(value, str) and re.fullmatch(r"[0-9A-Z]{5}", value):
            sqlstate = value
            break
    frames = []
    trace = error.__traceback__
    inspected = 0
    while trace is not None and inspected < 48:
        filename = Path(trace.tb_frame.f_code.co_filename).name
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,119}\.py", filename):
            frames.append({"file": filename, "line": trace.tb_lineno})
        trace = trace.tb_next
        inspected += 1
    return {
        "sqlstate": sqlstate,
        "frames": frames,
        "frames_truncated": trace is not None,
    }


def load_binding():
    binding = json.loads(Path(__file__).with_name("binding.json").read_text())
    require(binding["source_commit"] == SOURCE_COMMIT, "binding_source_mismatch")
    require(
        bool(binding["expected_clone_ip"] and binding["run_id"]),
        "binding_not_finalized",
    )
    for env, key in (
        ("SOURCE_COMMIT", "source_commit"),
        ("EXPECTED_CLONE_IP", "expected_clone_ip"),
        ("EXPECTED_DATABASE", "expected_database"),
        ("REHEARSAL_RUN_ID", "run_id"),
    ):
        require(os.environ.get(env) == binding[key], "clone_binding_mismatch")
    require(
        binding["expected_database_user"] == "crm_user"
        and unquote(urlsplit(os.environ.get("DATABASE_URL", "")).username or "")
        == binding["expected_database_user"],
        "clone_database_user_mismatch",
    )
    return binding


def verify_source(api_root):
    manifest = json.loads(Path(__file__).with_name("source-manifest.json").read_text())
    require(manifest["source_commit"] == SOURCE_COMMIT, "manifest_source_mismatch")
    for path, expected in manifest["files"].items():
        require(
            path.startswith("apps/api/") and ".." not in Path(path).parts,
            "manifest_path_invalid",
        )
        actual = hashlib.sha256(
            (api_root / path.removeprefix("apps/api/")).read_bytes()
        ).hexdigest()
        require(actual == expected, "frozen_source_hash_mismatch")
    return manifest


def verify_sentinel(connection, binding, *, initialize):
    require(
        connection.execute("SELECT current_database()").fetchone()[0] == "crm",
        "database_mismatch",
    )
    require(
        connection.execute("SELECT current_user").fetchone()[0] == "crm_user",
        "clone_database_user_mismatch",
    )
    if initialize:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS public.permission_handoff_review_guard_app "
            "(run_id text PRIMARY KEY, source_commit text NOT NULL)"
        )
        connection.execute(
            "LOCK TABLE public.permission_handoff_review_guard_app IN EXCLUSIVE MODE"
        )
    rows = connection.execute(
        "SELECT run_id, source_commit FROM public.permission_handoff_review_guard_app"
    ).fetchall()
    expected = (binding["run_id"], SOURCE_COMMIT)
    if initialize and not rows:
        connection.execute(
            "INSERT INTO public.permission_handoff_review_guard_app (run_id, source_commit) VALUES (%s, %s)",
            expected,
        )
    else:
        require(rows == [expected], "clone_sentinel_mismatch")
    if initialize:
        connection.commit()


def encrypted_ledger(ledger, binding):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    public_bytes = Path(__file__).with_name("ledger-public-key.pem").read_bytes()
    public_hash = hashlib.sha256(public_bytes).hexdigest()
    require(public_hash == binding["public_key_sha256"], "ledger_public_key_mismatch")
    public_key = serialization.load_pem_public_key(public_bytes)
    require(
        isinstance(public_key, rsa.RSAPublicKey) and public_key.key_size >= 3072,
        "ledger_key_invalid",
    )
    plaintext = json.dumps(ledger, separators=(",", ":"), sort_keys=True).encode()
    require(len(plaintext) <= MAX_LEDGER_BYTES, "ledger_size_exceeded")
    aad = json.dumps(
        {
            "format": "handoff-evidence-v1",
            "run_id": binding["run_id"],
            "source_commit": SOURCE_COMMIT,
            "public_key_sha256": public_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    key, nonce = AESGCM.generate_key(bit_length=256), os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, gzip.compress(plaintext, mtime=0), aad)
    wrapped_key = public_key.encrypt(
        key,
        padding.OAEP(
            mgf=padding.MGF1(hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=b"crm-handoff-review-v1",
        ),
    )
    encoded = base64.b64encode(ciphertext).decode()
    chunks = [
        encoded[start : start + CHUNK_CHARACTERS]
        for start in range(0, len(encoded), CHUNK_CHARACTERS)
    ]
    envelope = {
        "algorithm": "RSA-OAEP-SHA256+A256GCM",
        "compression": "gzip",
        "wrapped_key": base64.b64encode(wrapped_key).decode(),
        "nonce": base64.b64encode(nonce).decode(),
        "aad": base64.b64encode(aad).decode(),
        "ciphertext_sha256": hashlib.sha256(ciphertext).hexdigest(),
        "chunk_count": len(chunks),
    }
    return envelope, chunks


def validate_aggregate(summary):
    count_fields = {
        "handoff_records",
        "current_direct_owner_preservation_candidates",
        "role_audit_observations",
    }
    categories = {
        "historical_classification": {"ambiguous", "candidate", "verified"},
        "reason_counts": {
            "phase_requires_review",
            "no_explicit_approval_crossing",
            "multiple_approval_crossings",
            "approval_effective_time_differs_or_missing",
            "approval_is_undo",
            "same_timestamp_ownership_order_uncertain",
            "malformed_or_missing_owner_reference",
            "recorded_ownership_chain_conflict",
            "no_recorded_user_owner_at_approval",
            "candidate_not_current_active_intake",
            "role_chain_conflict",
            "same_timestamp_role_order_uncertain",
            "audited_other_role_observation",
            "historical_membership_activity_uncertain",
        },
    }
    require(
        set(summary)
        == count_fields
        | set(categories)
        | {"schema_version", "read_only", "grant_decisions_made"},
        "aggregate_schema_invalid",
    )
    require(
        summary["schema_version"] == 1
        and summary["read_only"] is True
        and summary["grant_decisions_made"] is False,
        "aggregate_contract_invalid",
    )
    values = [summary[field] for field in count_fields]
    for field, allowed in categories.items():
        require(set(summary[field]) <= allowed, "aggregate_category_invalid")
        values.extend(summary[field].values())
    require(
        all(type(value) is int and value >= 0 for value in values),
        "aggregate_count_invalid",
    )
    return summary


def collect(binding, manifest):
    import bootstrap_guards
    import rehearsal_guards
    from sqlalchemy import event, text
    from sqlalchemy.orm import Session

    bootstrap_guards.disable_crypto()
    rehearsal_guards.install_guards()
    from app.core.config import settings
    from app.db.session import engine
    from collector import CollectionBlocked as CollectorBlocked
    from collector import aggregate_summary, collect_handoff_evidence

    require(settings.ENV == "test", "test_environment_required")
    for name in (
        "DATA_ENCRYPTION_KEY",
        "META_ENCRYPTION_KEY",
        "FERNET_KEY",
        "PII_HASH_KEY",
        "VERSION_ENCRYPTION_KEY",
    ):
        require(
            not getattr(settings, name).get_secret_value(), "crypto_material_forbidden"
        )
    engine.echo = False
    engine.hide_parameters = True
    try:
        with Session(engine, autoflush=False) as db:
            event.listen(db, "do_orm_execute", rehearsal_guards.restrict_orm_reads)
            db.execute(
                text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            )
            db.execute(text("SET LOCAL TIME ZONE 'UTC'"))
            db.execute(text("SET LOCAL statement_timeout = '180s'"))
            db.execute(text("SET LOCAL lock_timeout = '10s'"))
            marker = db.execute(
                text(
                    "SELECT run_id, source_commit FROM public.permission_handoff_review_guard_app"
                )
            ).all()
            require(
                [tuple(row) for row in marker] == [(binding["run_id"], SOURCE_COMMIT)],
                "clone_sentinel_mismatch",
            )
            require(
                db.scalar(text("SELECT current_database()")) == "crm",
                "database_mismatch",
            )
            require(
                db.scalar(text("SELECT current_user")) == "crm_user",
                "clone_database_user_mismatch",
            )
            heads = (
                db.execute(text("SELECT version_num FROM public.alembic_version"))
                .scalars()
                .all()
            )
            require(
                heads == [manifest["schema_head"]],
                "schema_head_mismatch_no_migration_allowed",
            )
            org_ids = list(db.scalars(text("SELECT id FROM organizations ORDER BY id")))
            require(len(org_ids) <= 100, "organization_limit_exceeded")
            ledgers = [
                collect_handoff_evidence(db, org_id, SOURCE_COMMIT)
                for org_id in org_ids
            ]
            summaries = [
                validate_aggregate(aggregate_summary(ledger)) for ledger in ledgers
            ]
            require(
                not db.new and not db.dirty and not db.deleted,
                "collector_mutated_session",
            )
            ledger = {
                "format": "handoff-evidence-v1",
                "source_commit": SOURCE_COMMIT,
                "run_id": binding["run_id"],
                "schema_head": heads[0],
                "organizations": ledgers,
            }
            db.rollback()
        return ledger, summaries
    except CollectorBlocked as error:
        code = error.args[0] if len(error.args) == 1 else None
        raise CollectionBlocked(
            code
            if isinstance(code, str) and code in COLLECTOR_CODES
            else "collector_guard_blocked"
        ) from None
    finally:
        engine.dispose()


def main():
    global PHASE
    original_stdout = sys.stdout
    try:
        with (
            open(os.devnull, "w") as sink,
            contextlib.redirect_stdout(sink),
            contextlib.redirect_stderr(sink),
        ):
            import bootstrap_guards

            binding = load_binding()
            api_root = Path(__file__).resolve().parent.parent
            manifest = verify_source(api_root)
            bootstrap_guards.SOURCE_COMMIT = SOURCE_COMMIT
            safe = bootstrap_guards.validate_environment(dict(os.environ))
            allowed = bootstrap_guards.RUNTIME_ENV | {
                "DATABASE_URL",
                "EXPECTED_CLONE_IP",
                "EXPECTED_DATABASE",
                "REHEARSAL_RUN_ID",
                "SOURCE_COMMIT",
            }
            os.environ.clear()
            os.environ.update(
                {key: value for key, value in safe.items() if key in allowed}
            )
            os.environ.update(
                ENV="test",
                TESTING="1",
                DB_POOL_SIZE="1",
                DB_MAX_OVERFLOW="0",
                DB_CONNECT_TIMEOUT="10",
                DB_AUTO_MIGRATE="false",
                SENTRY_DSN="",
                GOOGLE_CALENDAR_SYNC_FALLBACK_ENABLED="false",
                GMAIL_SYNC_FALLBACK_ENABLED="false",
            )
            os.chdir(tempfile.mkdtemp(prefix="handoff-evidence-"))
            sys.path.insert(0, str(api_root))
            logging.disable(logging.CRITICAL)
            bootstrap_guards.install_network_guard(binding["expected_clone_ip"])
            PHASE = "clone_sentinel"
            with bootstrap_guards.connect_clone(
                os.environ["DATABASE_URL"]
            ) as connection:
                verify_sentinel(connection, binding, initialize=True)
            PHASE = "read_only_collection"
            ledger, summaries = collect(binding, manifest)
            PHASE = "encrypt_ledger"
            envelope, chunks = encrypted_ledger(ledger, binding)
        output = {
            "phase": "encrypted_ledger",
            "status": "complete",
            "source_commit": SOURCE_COMMIT,
            "run_id": binding["run_id"],
            "organization_count": len(summaries),
            "aggregate_summaries": summaries,
            "business_read_only": True,
            "envelope": envelope,
        }
        original_stdout.write(json.dumps(output, sort_keys=True) + "\n")
        for index, data in enumerate(chunks):
            original_stdout.write(
                json.dumps(
                    {
                        "phase": "encrypted_ledger_chunk",
                        "run_id": binding["run_id"],
                        "index": index,
                        "count": len(chunks),
                        "data": data,
                    },
                    sort_keys=True,
                )
                + "\n"
            )
        original_stdout.flush()
        return 0
    except BaseException as error:  # noqa: BLE001 - process boundary must suppress raw data
        code = (
            str(error) if isinstance(error, CollectionBlocked) else "collection_failed"
        )
        original_stdout.write(
            json.dumps(
                {
                    "phase": PHASE,
                    "status": "blocked",
                    "code": code,
                    "error_type": type(error).__name__,
                    **safe_error_diagnostics(error),
                },
                sort_keys=True,
            )
            + "\n"
        )
        original_stdout.flush()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

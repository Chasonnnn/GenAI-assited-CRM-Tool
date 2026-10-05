"""Decrypt one execution's JSON log export into a private local file; never print ledger data."""

import argparse
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = Path(__file__).resolve().parent


def decrypt(input_path, output_path):
    private_path = ROOT / "ledger-private-key.pem"
    if private_path.stat().st_mode & 0o077:
        raise ValueError("private_key_permissions_invalid")
    target = output_path.resolve()
    if not target.is_relative_to(ROOT) or target.is_relative_to(ROOT / "build"):
        raise ValueError("plaintext_output_must_stay_private_outside_build")
    raw = input_path.read_text()
    try:
        entries = json.loads(raw)
        if not isinstance(entries, list):
            entries = [entries]
    except json.JSONDecodeError:
        entries = [json.loads(line) for line in raw.splitlines() if line.strip()]
    messages = []
    for entry in entries:
        if isinstance(entry.get("textPayload"), str):
            try:
                messages.append(json.loads(entry["textPayload"]))
            except json.JSONDecodeError:
                continue
        else:
            messages.append(entry.get("jsonPayload", entry))
    heads = [
        entry
        for entry in messages
        if entry.get("phase") == "encrypted_ledger" and entry.get("status") == "complete"
    ]
    if len(heads) != 1:
        raise ValueError("one_complete_execution_required")
    head = heads[0]
    envelope = head["envelope"]
    chunks = [
        entry
        for entry in messages
        if entry.get("phase") == "encrypted_ledger_chunk" and entry.get("run_id") == head["run_id"]
    ]
    chunks.sort(key=lambda item: item["index"])
    if [entry["index"] for entry in chunks] != list(range(envelope["chunk_count"])) or any(
        entry["count"] != envelope["chunk_count"] for entry in chunks
    ):
        raise ValueError("encrypted_chunks_incomplete_or_duplicate")
    ciphertext = base64.b64decode("".join(entry["data"] for entry in chunks), validate=True)
    if hashlib.sha256(ciphertext).hexdigest() != envelope["ciphertext_sha256"]:
        raise ValueError("ciphertext_digest_mismatch")
    key = serialization.load_pem_private_key(private_path.read_bytes(), password=None)
    aes_key = key.decrypt(
        base64.b64decode(envelope["wrapped_key"], validate=True),
        padding.OAEP(
            mgf=padding.MGF1(hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=b"crm-handoff-review-v1",
        ),
    )
    aad = base64.b64decode(envelope["aad"], validate=True)
    metadata = json.loads(aad)
    if metadata["run_id"] != head["run_id"] or metadata["source_commit"] != head["source_commit"]:
        raise ValueError("ledger_metadata_mismatch")
    plaintext = gzip.decompress(
        AESGCM(aes_key).decrypt(base64.b64decode(envelope["nonce"], validate=True), ciphertext, aad)
    )
    ledger = json.loads(plaintext)
    if ledger["run_id"] != head["run_id"] or ledger["source_commit"] != head["source_commit"]:
        raise ValueError("ledger_identity_mismatch")
    with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as handle:
        handle.write(plaintext)
    return len(plaintext)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        size = decrypt(args.input, args.output)
    except Exception as error:  # noqa: BLE001 - keep decryption failures free of ledger contents
        print(json.dumps({"status": "blocked", "error_type": type(error).__name__}))
        raise SystemExit(1) from None
    print(json.dumps({"status": "decrypted_to_private_file", "bytes": size}))

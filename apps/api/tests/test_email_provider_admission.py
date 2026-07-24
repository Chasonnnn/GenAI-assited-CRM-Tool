"""Public-contract tests for distributed email-provider admission."""

from datetime import datetime, timedelta, timezone
from threading import Barrier, Event, Lock, Thread
import time
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.db.models import EmailProviderAdmission
from app.db.session import SessionLocal
from app.services.email_provider_admission_service import (
    reserve_provider_request_slot,
)


def test_default_resend_team_admission_limit_matches_provider_contract():
    settings = Settings(
        _env_file=None,
        ENV="test",
        DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/test",
    )

    assert settings.RESEND_PROVIDER_REQUESTS_PER_SECOND == 5


def test_concurrent_workers_reserve_ten_strictly_spaced_slots_per_second(
    db_engine,
):
    if db_engine.dialect.name != "postgresql":
        pytest.skip("Concurrent provider admission requires PostgreSQL row locks")

    provider_account_id = f"organization:{uuid4()}"
    fixed_now = datetime.now(timezone.utc).replace(microsecond=0)
    worker_count = 12
    barrier = Barrier(worker_count)
    result_lock = Lock()
    reserved_slots: list[datetime] = []
    errors: list[Exception] = []

    def reserve_once() -> None:
        session = SessionLocal(bind=db_engine)
        try:
            barrier.wait(timeout=10)
            reservation = reserve_provider_request_slot(
                session,
                provider="resend",
                provider_account_id=provider_account_id,
                requests_per_second=10,
                now=fixed_now,
            )
            with result_lock:
                reserved_slots.append(reservation.send_at)
        except Exception as exc:
            session.rollback()
            with result_lock:
                errors.append(exc)
        finally:
            session.close()

    threads = [Thread(target=reserve_once) for _ in range(worker_count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    assert all(not thread.is_alive() for thread in threads)
    assert errors == []
    assert sorted(reserved_slots) == [
        fixed_now + timedelta(milliseconds=100 * index) for index in range(worker_count)
    ]

    verification = SessionLocal(bind=db_engine)
    try:
        next_reservation = reserve_provider_request_slot(
            verification,
            provider="resend",
            provider_account_id=provider_account_id,
            requests_per_second=10,
            now=fixed_now,
        )
        assert next_reservation.send_at == fixed_now + timedelta(seconds=1.2)
    finally:
        verification.query(EmailProviderAdmission).filter(
            EmailProviderAdmission.provider == "resend",
            EmailProviderAdmission.provider_account_id == provider_account_id,
        ).delete()
        verification.commit()
        verification.close()


def test_reservation_uses_current_database_time_after_waiting_for_account_lock(
    db_engine,
):
    if db_engine.dialect.name != "postgresql":
        pytest.skip("Concurrent provider admission requires PostgreSQL row locks")

    provider_account_id = f"organization:{uuid4()}"
    seed = SessionLocal(bind=db_engine)
    locker = SessionLocal(bind=db_engine)
    result_lock = Lock()
    contender_started = Event()
    reservations = []
    errors: list[Exception] = []
    try:
        reserve_provider_request_slot(
            seed,
            provider="resend",
            provider_account_id=provider_account_id,
            requests_per_second=10,
        )
        (
            locker.query(EmailProviderAdmission)
            .filter(
                EmailProviderAdmission.provider == "resend",
                EmailProviderAdmission.provider_account_id == provider_account_id,
            )
            .with_for_update()
            .one()
        )

        def reserve_while_locked() -> None:
            contender = SessionLocal(bind=db_engine)
            try:
                contender_started.set()
                reservation = reserve_provider_request_slot(
                    contender,
                    provider="resend",
                    provider_account_id=provider_account_id,
                    requests_per_second=10,
                )
                with result_lock:
                    reservations.append(reservation)
            except Exception as exc:
                contender.rollback()
                with result_lock:
                    errors.append(exc)
            finally:
                contender.close()

        thread = Thread(target=reserve_while_locked)
        thread.start()
        assert contender_started.wait(timeout=2)
        time.sleep(0.25)
        released_at = datetime.now(timezone.utc)
        locker.commit()
        thread.join(timeout=5)

        assert thread.is_alive() is False
        assert errors == []
        assert len(reservations) == 1
        assert reservations[0].send_at >= released_at - timedelta(milliseconds=10)
    finally:
        locker.rollback()
        seed.query(EmailProviderAdmission).filter(
            EmailProviderAdmission.provider == "resend",
            EmailProviderAdmission.provider_account_id == provider_account_id,
        ).delete()
        seed.commit()
        locker.close()
        seed.close()

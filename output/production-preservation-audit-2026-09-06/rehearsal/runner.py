"""Clone-only, aggregate-output migration rehearsal. Never starts the application."""
import hashlib
import hmac
import json
import os
import secrets
import time

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from alembic import command
from alembic.config import Config


def emit(event, **fields):
    print(json.dumps({'rehearsal': event, **fields}), flush=True)


def main():
    url = make_url(os.environ['DATABASE_URL'])
    assert url.host == '10.9.0.14' and url.database == 'crm'
    assert os.environ.get('REHEARSAL_TARGET') == 'crm-match-rehearsal-0906'
    engine = create_engine(url, hide_parameters=True, connect_args={'connect_timeout': 20})
    key = secrets.token_bytes(32)
    with engine.connect() as c:
        baseline = c.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
        assert baseline == '20260830_0100'
        inspector = inspect(c)
        columns = {t: [x['name'] for x in inspector.get_columns(t)] for t in inspector.get_table_names() if t != 'alembic_version'}
        size = c.execute(text('SELECT pg_database_size(current_database())')).scalar_one()
        conflicts = c.execute(text("SELECT count(*) FROM (SELECT organization_id, surrogate_id FROM matches WHERE status IN ('accepted','cancel_pending') GROUP BY organization_id,surrogate_id HAVING count(*)>1) c")).scalar_one()
        emit('inventory', revision=baseline, tables=len(columns), database_bytes=size, commitment_conflicts=conflicts)
    assert conflicts == 0

    def snapshot():
        result = {}
        with engine.connect() as c:
            quote = c.dialect.identifier_preparer.quote
            for table, cols in sorted(columns.items()):
                query = 'SELECT row_to_json(r)::text FROM (SELECT '+','.join(map(quote, cols))+' FROM '+quote(table)+') r'
                count = total = 0
                for row in c.execution_options(stream_results=True).execute(text(query)):
                    total = (total + int.from_bytes(hmac.digest(key, row[0].encode(), 'sha256'))) % (1 << 256)
                    count += 1
                result[table] = (count, total)
        return result

    initial = snapshot()
    emit('baseline_counts', counts={k:v[0] for k,v in initial.items()})
    def compare(stage):
        now = snapshot()
        changed = [t for t in initial if initial[t] != now[t]]
        emit(stage, unchanged_tables=len(initial)-len(changed), changed_tables=changed, rows=sum(v[0] for v in now.values()))
        assert not changed

    def migrate(target, down=False):
        config = Config('/app/alembic.ini')
        start = time.monotonic()
        with engine.begin() as c:
            config.attributes['connection'] = c
            (command.downgrade if down else command.upgrade)(config, target)
        return round(time.monotonic()-start, 3)

    # Prove the lock budget aborts instead of hanging or partially changing data.
    with engine.connect() as blocker:
        blocker.execute(text('LOCK TABLE matches IN ACCESS SHARE MODE'))
        try:
            migrate('head')
        except Exception as exc:
            code = getattr(getattr(exc, 'orig', None), 'sqlstate', None)
            emit('contention_abort', sqlstate=code)
            assert code == '55P03'
        else:
            raise AssertionError('Migration unexpectedly bypassed blocker')
        finally:
            blocker.rollback()
    with engine.connect() as c:
        assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == baseline
    compare('failed_upgrade_preservation')
    emit('upgrade', seconds=migrate('head'))
    compare('upgrade_preservation')
    emit('downgrade', seconds=migrate(baseline, down=True))
    compare('downgrade_preservation')
    emit('reupgrade', seconds=migrate('head'))
    compare('reupgrade_preservation')
    emit('success', scope='database migration only; application rollout not tested')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        emit('failure', error_type=type(exc).__name__, sqlstate=getattr(getattr(exc, 'orig', None), 'sqlstate', None))
        raise SystemExit(1) from None

FROM us-central1-docker.pkg.dev/probable-dream-484923-n7/crm/api@sha256:ec62076572fd7cfd6951df01c8b331b42795f2458812013f63048a90564e7ffa
WORKDIR /app
RUN python -c "import hashlib; from pathlib import Path; expected={'pyproject.toml': '651cf13c39237943784592d283489d85218e9f04ab9e04555fda01bb3fd8bb26', 'uv.lock': '35a0386c64595ad6e231c7d6291a245f0af13b8231d62768c603287b5a4ff645'}; assert all(hashlib.sha256(Path(name).read_bytes()).hexdigest()==value for name,value in expected.items()), \"base_dependency_hash_mismatch\""
USER root
RUN rm -rf /app && mkdir /app
COPY --chown=appuser:appuser source/apps/api/ /app/
USER appuser
ENV ENV=test PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app
HEALTHCHECK NONE
ENTRYPOINT ["python", "/app/_handoff/runner.py"]
CMD []

From the CI logs:
```
2026-03-05T05:29:42.2359270Z Blocking vulnerabilities with fixes available:
2026-03-05T05:29:42.2359820Z - pypdf 6.7.4 CVE-2026-28804 (fix: 6.7.5)
```

The issue is a vulnerability in `pypdf` in `apps/api/pyproject.toml` (and `uv.lock`). I need to update it to `6.7.5` and then run `uv lock` or `uv sync` to update `uv.lock`.

Let's do that!

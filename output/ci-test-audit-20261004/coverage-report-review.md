# Independent coverage reporting review

Result: no blocking findings. Reviewed the two-file diff against `0d2943db2d624d99fbf1b5d74da67376c2598a60`; no installs or tests run.

| File | Reviewed SHA-256 |
| --- | --- |
| `.github/workflows/ci.yml` | `26d05acb01fd772ad55796ab30a0641ca7cc164fee769f7538dcc5c5dc225f85` |
| `apps/api/tests/test_release_ci.py` | `94270beff1dfa18a853a423dca13a77be1ef753cb27100e39952ffea8a6617f9` |

- Removing `uv run coverage report` removes one redundant text-report analysis pass. It does not remove collection, coverage merging, a threshold, or a downstream artifact.
- Installed `coverage/cmdline.py:878-942` obtains a numeric total from both `xml_report` and `json_report`, then applies the same configured `report:fail_under` and `report:precision` logic used by the text report. Below-floor results return a nonzero failure status, which fails the existing shell step.
- `coverage/report.py`, `jsonreport.py`, `xmlreport.py`, and `results.py` compute the same combined statement-plus-branch percentage: covered statements plus covered branches divided by total statements plus total branches. The configured total floor remains 75.85 with precision 2; neither retained command overrides it.
- The explicit JSON checks retain the independent line floor 79.96, branch floor 63.03, and nonzero measurement checks. Source selection and branch collection are unchanged.
- `coverage.xml` is still generated, uploaded as `backend-coverage-xml`, and consumed by the existing non-blocking changed-line `diff-cover` step. `coverage.json` is still generated and consumed by the explicit line/branch checks. It was not separately uploaded before this change. No consumer of text-report output was found in the workflow or repository tooling.
- The existing configuration test now requires both executable report commands instead of the redundant text command and still requires a positive configured total floor. Its partition and required-gate assertions are unchanged.

This review establishes preserved coverage semantics. The next hosted CI run must establish the time saved; the prior 345-second result does not include this follow-up change.

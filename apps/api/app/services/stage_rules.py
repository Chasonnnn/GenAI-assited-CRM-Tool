"""Stage visibility and mutation rules by role.

These rules are used for build-time frontend generation and backend enforcement.
"""

ROLE_STAGE_VISIBILITY: dict[str, dict[str, list[str]]] = {
    "intake_specialist": {
        "stage_types": ["intake", "terminal"],
        "extra_slugs": [],
    },
    "case_manager": {
        "stage_types": ["post_approval"],
        "extra_slugs": ["approved"],
    },
    "admin": {
        "stage_types": ["intake", "post_approval", "terminal"],
        "extra_slugs": [],
    },
    "developer": {
        "stage_types": ["intake", "post_approval", "terminal"],
        "extra_slugs": [],
    },
}

ROLE_STAGE_MUTATION: dict[str, dict[str, list[str]]] = {
    "intake_specialist": {
        "stage_types": ["intake", "terminal"],
        "extra_slugs": [],
    },
    "case_manager": {
        "stage_types": ["post_approval"],
        "extra_slugs": [],
    },
    "admin": {
        "stage_types": ["intake", "post_approval", "terminal"],
        "extra_slugs": [],
    },
    "developer": {
        "stage_types": ["intake", "post_approval", "terminal"],
        "extra_slugs": [],
    },
}

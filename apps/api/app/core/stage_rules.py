"""Stage visibility and mutation rules by role."""

ROLE_STAGE_VISIBILITY: dict[str, dict[str, list[str]]] = {
    "intake_specialist": {
        "stage_types": ["intake", "paused", "terminal"],
        "extra_slugs": [],
    },
    "case_manager": {
        "stage_types": ["post_approval", "paused"],
        "extra_slugs": ["approved", "lost", "disqualified"],
    },
    "admin": {
        "stage_types": ["intake", "post_approval", "paused", "terminal"],
        "extra_slugs": [],
    },
    "developer": {
        "stage_types": ["intake", "post_approval", "paused", "terminal"],
        "extra_slugs": [],
    },
}

ROLE_STAGE_MUTATION: dict[str, dict[str, list[str]]] = {
    "intake_specialist": {
        "stage_types": ["intake", "paused", "terminal"],
        "extra_slugs": [],
    },
    "case_manager": {
        "stage_types": ["post_approval", "paused"],
        "extra_slugs": ["lost", "disqualified"],
    },
    "admin": {
        "stage_types": ["intake", "post_approval", "paused", "terminal"],
        "extra_slugs": [],
    },
    "developer": {
        "stage_types": ["intake", "post_approval", "paused", "terminal"],
        "extra_slugs": [],
    },
}

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid5


_BENCHMARK_USER_NAMESPACE = UUID("7b72e9fd-2fd9-5adf-9ab2-05f9e97ae905")


def benchmark_user_id(profile_name: str, organization_slug: str, role: str) -> UUID:
    """Return stable synthetic user IDs for executable hot/cold scenarios."""
    return uuid5(
        _BENCHMARK_USER_NAMESPACE,
        f"{profile_name}:{organization_slug}:{role}",
    )


@dataclass(frozen=True)
class SeedOrganizationProfile:
    slug: str
    organization_id: UUID
    surrogates: int
    intended_parents: int
    matches: int
    tasks: int


@dataclass(frozen=True)
class SeedProfile:
    name: str
    organizations: tuple[SeedOrganizationProfile, ...]
    random_seed: int = 20260713
    activity_mode: str = "rich_core"
    match_mode: str = "balanced"

    @property
    def organization_count(self) -> int:
        return len(self.organizations)

    @property
    def total_surrogates(self) -> int:
        return sum(org.surrogates for org in self.organizations)

    @property
    def total_intended_parents(self) -> int:
        return sum(org.intended_parents for org in self.organizations)

    @property
    def total_matches(self) -> int:
        return sum(org.matches for org in self.organizations)

    @property
    def total_tasks(self) -> int:
        return sum(org.tasks for org in self.organizations)

    @property
    def organization_weights(self) -> tuple[float, ...]:
        total = self.total_surrogates
        return tuple(org.surrogates / total for org in self.organizations)


_PRODUCTION_ORGS = (
    SeedOrganizationProfile(
        "hot",
        UUID("00000000-0000-5000-8000-000000000201"),
        surrogates=4_000,
        intended_parents=400,
        matches=800,
        tasks=800,
    ),
    SeedOrganizationProfile(
        "warm",
        UUID("00000000-0000-5000-8000-000000000202"),
        surrogates=800,
        intended_parents=80,
        matches=160,
        tasks=160,
    ),
    SeedOrganizationProfile(
        "cold",
        UUID("00000000-0000-5000-8000-000000000203"),
        surrogates=200,
        intended_parents=20,
        matches=40,
        tasks=40,
    ),
)


def _scale_organizations(
    organizations: tuple[SeedOrganizationProfile, ...], factor: int
) -> tuple[SeedOrganizationProfile, ...]:
    return tuple(
        SeedOrganizationProfile(
            slug=organization.slug,
            organization_id=UUID(int=organization.organization_id.int + 0x100),
            surrogates=organization.surrogates * factor,
            intended_parents=organization.intended_parents * factor,
            matches=organization.matches * factor,
            tasks=organization.tasks * factor,
        )
        for organization in organizations
    )


SEED_PROFILES: dict[str, SeedProfile] = {
    "smoke": SeedProfile(
        name="smoke",
        organizations=(
            SeedOrganizationProfile(
                "hot",
                UUID("00000000-0000-5000-8000-000000000101"),
                surrogates=50,
                intended_parents=10,
                matches=5,
                tasks=10,
            ),
            SeedOrganizationProfile(
                "cold",
                UUID("00000000-0000-5000-8000-000000000102"),
                surrogates=10,
                intended_parents=2,
                matches=1,
                tasks=2,
            ),
        ),
    ),
    "production": SeedProfile(name="production", organizations=_PRODUCTION_ORGS),
    "growth10x": SeedProfile(
        name="growth10x",
        organizations=_scale_organizations(_PRODUCTION_ORGS, 10),
    ),
}


def get_seed_profile(name: str) -> SeedProfile:
    try:
        return SEED_PROFILES[name]
    except KeyError as exc:
        choices = ", ".join(sorted(SEED_PROFILES))
        raise ValueError(f"Unknown seed profile {name!r}; expected one of: {choices}") from exc

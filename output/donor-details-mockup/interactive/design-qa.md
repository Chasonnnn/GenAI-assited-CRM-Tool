# Donor details mockup

This isolated prototype records the approved donor layout using synthetic data. State resets on reload.

The Overview was adapted directly from the surrogate Overview. It reuses the contact and demographics layout, personal information editors, medical and insurance card, activity timeline, and Notes/Attachments composition. `surrogate-overview-adaptation.diff` records the original source adaptation.

The tabs are Overview, Notes, Tasks, and History. Demographics includes date of birth and age, race/ethnicity, height, weight, and calculated BMI. Assignment remains in header actions. Overview has no Owner row, appointments, or match proposal card.

The six checklist questions cover education, college, nicotine, cannabis, infectious disease/STI history, and previous donation. Their saved template wording and options are in `src/donor-template-fields.json`. Missing answers remain distinct from Yes/No, and the infectious-disease answer preserves Prefer to discuss with the team. No clinical eligibility threshold is inferred.

Design checks verified weight/BMI updates, race labels, shared education state, checklist options, note creation, and the medical/header menus. Historical screenshots record those iterations.

On 2026-09-14, the archived prototype passed `pnpm run build` and all four `pnpm run test:sites` checks. Its lockfile and dependency policy are preserved. Production implementation and live API/database QA results are recorded in `../../donor-details-implementation/live-qa.md`.

# Permission UI generation prompts

Generator: built-in Image Gen.

Visual reference: `output/donor-ip-design-qa/donor-light-1440.png`.

## 1. roles

Use case: ui-mockup.
Create one realistic, production-quality desktop UI mock-up for Surrogacy Force permission management. Direction name for your design process: Role Workbench. Do not print this direction name or any option number.

REFERENCE: Attached image is the existing product's visual reference, not an edit target. Preserve its brand, white and pale gray surfaces, charcoal text, restrained pink-magenta accents, thin gray borders, clean sans-serif typography, familiar sidebar navigation and line icons. Redesign the information layout. Do not copy donor content, dates, telephone numbers, developer badges or QA labels. Use synthetic names and no dates.

TARGET: exactly 1440 x 1024 desktop web app, app content only, no browser frame. Crisp readable text, body14–16px, headings24–28px. Purpose is for agency Admin to configure one supplied role by module without a giant matrix of toggles. Focus on the primary screen, generous whitespace, alignment and simple dividers instead of cards inside cards. One clear pink primary action. No explanatory subtitles, taglines, decorative art or metrics.

COMPOSITION:
Retain a 232px light gray global sidebar with Surrogacy Force brand, small agency label "Sample Agency", familiar nav items Dashboard, Surrogates, Intended Parents, Donors, Matches, Tasks & Scheduling, Automation, Reports and Settings selected.
Main header breadcrumb "Settings / Team", large title "Permissions", top-right subtle "Changes" and pink "Review changes".
Below header a horizontal navigation row "Roles" selected, "People", "Check access".
Below, a narrow role list separated by a vertical rule: Intake Specialist, Case Manager selected with pale pink background, Operations with small gray "Setup pending" text, Admin with lock icon, Dev with lock icon. No Create role button.
Content right of role list: "Case Manager" title and tabs "Surrogates" selected, "Donors", "Intended Parents", "More". Do not assign Operations defaults.
Primary section "Record access", two neatly aligned select controls side by side: label "Assignment" value "All records"; label "Phase" value "Approved and later". Below these, one short functional sentence: "The same records are used for View and Edit." This is necessary permission explanation.
Next "Actions": a clean table with Action and Allowed columns. Rows View records on, Edit records on, Approve applicants off, Reassign records off. Enabled switches pink; disabled permissions gray. These are editable ROLE settings, not individual denials. This screen illustrates a sample edited baseline and must not call all settings universal defaults.
Bottom small section "Access preview" on a lightly tinted flat strip: "Visible and editable" and "Approved and later surrogates, regardless of owner." A second row "Before approval" with "Outside this role's scope".
Use space for a quiet footer "Unsaved changes" and secondary "Discard" near Review changes only if layout fits. Avoid duplicate main action.
Constraints: One role per person. Fixed supplied roles, Admin/Dev protected. No custom roles, multi-role stacking, negative user overrides, separate view/edit scope, separate workflow activation permission, or invented Operations settings. Keep this a polished focused admin tool matching reference style.

## 2. people

Use case: ui-mockup.
Create one realistic, production-quality desktop UI mock-up for Surrogacy Force permission management. Direction name for your design process: Person Access Workspace. Do not print that name or an option number. One focused screen, no montage.

REFERENCE IMAGE: actual existing product visual reference, not an edit target. Keep white and light gray surfaces, charcoal sans-serif type, muted pink-magenta active states, fine dividers, familiar sidebar and line icons. Redesign the layout for clarity, less card-heavy than reference. Do not copy donor details, dates, QA labels or developer badges. Only synthetic names; no timestamps.

TARGET 1440 x 1024, app only, no browser or device chrome. Readable14–16px body and26px heading. One main action. Prefer alignment, grouping and whitespace before borders; no cards inside cards, no metrics, illustrations, marketing copy or subtitles.

TASK: Agency Admin inspecting one member's access. This is a different structural approach from a role editor: person-oriented, showing inherited permissions separately from individual additions and retained collaboration. Build on existing brand.

LAYOUT:
232px familiar light global sidebar, Surrogacy Force / Sample Agency at top; standard Dashboard, Surrogates, Intended Parents, Donors, Matches, Tasks & Scheduling, Automation, Reports, Settings selected.
Main content top breadcrumb Settings / Team, heading "Permissions"; nav row "Roles", "People" selected, "Check access".
Under row left narrow member list, small search "Find a person", three entries with initials: "Alice Morgan" Intake Specialist selected with pale pink tint; "Jordan Lee" Case Manager; "Sam Chen" Admin. Do not add other roles or invite action.
Right spacious editor header "Alice Morgan" with alice@example.com and single role selector "Intake Specialist". Pink primary button "+ Add access".
Main panel tabs "Permissions" selected and "Collaborators". Small module selector "Surrogates".
"Role access" heading with restrained text link "View role". Flat definition rows: "Records" / "Assigned to Alice · Before approval"; "Actions" / "View · Edit · Approve". Lock icon beside inherited values. One short necessary behavior note: "Inherited from Intake Specialist." No removable toggles here.
Next "Individual additions" heading. Table columns "Access", "Source", and unlabeled remove column. Single sample row "Change stage" / "Individual addition" / "Remove". It illustrates an explicit additional action, not baseline. Label a small text field/empty state beneath: "No additional record scope".
Next "Retained collaboration" heading, with a compact two-row table: Record, Phase, Access source. "Taylor Morgan · Egg Donor" / "Approved" / "Intake collaborator"; "Jamie Ellis · Surrogate" / "Matching" / "Intake collaborator". Each row may have a quiet right chevron to inspect. Do not display blanket postapproval access. Small necessary sentence "These records remain accessible after handoff." The role's actions apply within covered module.
Bottom right supporting button "Check access" or text link, not another primary.
Constraints: Exactly one role per person, no custom role creation, no Allow/Deny radio buttons, no blocking inherited permissions, no toggling away inherited rights. Remove controls only on additions. Don't give Alice Case Manager role or all Approved records. Collaborator grants record route; linked intended-parent data is not automatically included. Shared View/Edit record scope. Operations settings unresolved so do not display any. No separate workflow activation permission. Clean readable mockup, not implementation or promotional diagram.

## 3. check

Use case: ui-mockup.
Create one realistic, production-quality desktop UI mockup of Surrogacy Force permissions. Direction name for internal design process: Access Inspector. Do not render direction name or an option number. One focused screen, not a montage.
REFERENCE: Attached real product screenshot is a visual reference, not an edit target. Preserve brand and recognizable navigation, Noto Sans style, white #FFFFFF surfaces, off-white #FAFAFA shell, charcoal #2B2B2B text, #6B6B6B secondary text, thin #E5E5E5 rules, restrained #E444A4 magenta primary, 8px rounded controls, simple outline icons. No donor screenshot contents, QA labels, dates or developer badges.

TARGET: 1440 x1024 desktop app screenshot, no device/browser chrome. Clear14–16px text,28px heading, generous whitespace, strong aligned hierarchy. Use simple dividers instead of nested cards. No marketing copy, subtitles, dashboard metrics, decorative imagery or dense permissions matrix. Focus one primary task: Admin understanding exactly why one staff member can or cannot perform an action on a record.

COMPOSITION:
Keep a256px pale sidebar with Surrogacy Force / Sample Agency and familiar Dashboard, Surrogates, Intended Parents, Donors, Matches, Tasks & Scheduling, Automation, Reports, Settings selected.
Main page breadcrumb "Settings / Team", heading "Permissions"; navigation "Roles", "People", "Check access" selected pink underline.
Wide slim query form across main pane with three aligned labeled selectors: "Person" value "Alice Morgan"; "Record" value "Taylor Morgan · Egg Donor"; "Action" value "Edit record". Primary pink button "Check access". No second primary action.
Below about30px whitespace, two-column result. Main column approx620px: a small green check with heading "Allowed" and one functional sentence "Alice can edit this donor as an Intake collaborator." Under a divider heading "Why access is allowed". Present readable numbered rows with short labels on left, explanations on right:
1 "Active member" — "Sample Agency"
2 "Action granted" — "Edit donor records · Intake Specialist"
3 "Record included" — "Intake collaborator after approval"
Under these, a subdued single row "Role scope alone" / "Does not include this approved donor". This must clearly not contradict effective Allowed.
Separate final row below "Linked intended-parent data" / "Requires separate access". Do not reveal linked names or private data.
Right supporting column approx300px, very subtle pale gray tint with "Record access" heading. Compact definition rows "Stage" / "Approved"; "Owner" / "Jordan Lee"; "Intake collaborator" / "Alice Morgan"; "Added" / "At approval handoff". Horizontal divider. Text link "View Alice's access". No dates, no scope grant/edit control inside this checker.
Below main trace use a clean compact table heading "Other actions", rows "View record" Allowed, "Change stage" Not granted, "Reassign record" Not granted. Use clear textual statuses not only color. This is a different synthetic scenario where Alice has no extra stage-change addition. Avoid implying approval is needed for normal view/edit. No explicit user deny override.
At bottom subtle tabs or scope toggle "Person" selected and "Organization work" only if it fits naturally; these represent separate check contexts, do not falsely treat organization authority as Alice's own record scope. Prefer omit if it clutters.
Constraints: One role per user, actions and record scope both required. Intake collaboration retains postapproval record access but not Case Manager powers, stage/reassignment need separate permissions. No inherited deny switches, no custom role builder, no multi-role UI. View/Edit use shared scope. No Operations defaults. Source attribution should be readable functional content, not technical logs. This is a polished agency admin mock-up with restrained brand styling.

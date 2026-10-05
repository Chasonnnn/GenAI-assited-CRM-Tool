"""Render a private, offline review page. Standard library only; no API writes."""

import argparse
import base64
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from uuid import UUID

STAGES = {
    "anatomy_scanned": "Anatomy Scanned",
    "application_submitted": "Application Submitted",
    "approved": "Approved",
    "available": "Available",
    "closed": "Closed",
    "cold_leads": "Cold Leads",
    "collection_in_progress": "Collection in Progress",
    "contacted": "Contacted",
    "cycle_in_progress": "Cycle in Progress",
    "delivered": "Delivered",
    "disqualified": "Disqualified",
    "donation_complete": "Donation Complete",
    "heartbeat_confirmed": "Heartbeat Confirmed",
    "interview_scheduled": "Interview Scheduled",
    "legal_clearance_passed": "Legal Clearance Passed",
    "life_insurance_application_started": "Life Insurance Application Started",
    "lost": "Lost",
    "matched": "Matched",
    "medical_clearance_passed": "Medical Clearance Passed",
    "medical_genetic_screening": "Medical & Genetic Screening",
    "medical_records_review": "Medical Records Review",
    "new": "New",
    "new_unread": "New Unread",
    "ob_care_established": "OB Care Established",
    "on_hold": "On-Hold",
    "pbo_process_started": "PBO Process Started",
    "pending_docusign": "Pending-DocuSign",
    "pre_qualified": "Pre-Qualified",
    "pre_screening": "Pre-Screening",
    "psychological_screening": "Psychological Screening",
    "ready_to_match": "Ready to Match",
    "reschedule_needed": "Reschedule Needed",
    "retrieval_complete": "Retrieval Complete",
    "second_hcg_confirmed": "Second hCG confirmed",
    "semen_analysis": "Semen Analysis",
    "transfer_cycle": "Transfer Cycle Initiated",
    "under_review": "Under Review",
}
ROLE_LABELS = {
    "intake_specialist": "Intake",
    "case_manager": "Case Manager",
    "operations": "Operations",
    "admin": "Admin",
    "developer": "Developer",
}
GAPS = {
    "phase_requires_review": "Approval phase needs review",
    "no_explicit_approval_crossing": "No explicit approval crossing recorded",
    "multiple_approval_crossings": "Multiple approval crossings",
    "approval_effective_time_differs_or_missing": "Approval effective time differs from recording time or is missing",
    "approval_is_undo": "Approval transition is an undo",
    "same_timestamp_ownership_order_uncertain": "Ownership events share a timestamp; order is uncertain",
    "malformed_or_missing_owner_reference": "An ownership event has an invalid or missing reference",
    "recorded_ownership_chain_conflict": "Recorded ownership changes conflict",
    "no_recorded_user_owner_at_approval": "No recorded user owner at approval; absence is not proof of no owner",
    "candidate_not_current_active_intake": "Candidate is not a current active Intake member",
    "role_chain_conflict": "Recorded role changes conflict",
    "same_timestamp_role_order_uncertain": "Role event order at approval is uncertain",
    "audited_other_role_observation": "Role audit indicates a different role",
    "historical_membership_activity_uncertain": "Historical membership activity is uncertain",
}
UUID_FIELDS = {
    "id",
    "actor_user_id",
    "changed_by_user_id",
    "request_id",
    "event_id",
    "from_id",
    "to_id",
    "owner_id",
    "old_owner_id",
    "new_owner_id",
    "user_id",
}
TIMES = {"at", "recorded_at", "effective_at"}
ENUMS = {
    "from_type": {"user", "queue"},
    "to_type": {"user", "queue"},
    "owner_type": {"user", "queue"},
    "old_owner_type": {"user", "queue"},
    "new_owner_type": {"user", "queue"},
    "old_role": set(ROLE_LABELS),
    "new_role": set(ROLE_LABELS),
    "event_type": {
        "assigned",
        "unassigned",
        "surrogate_claimed",
        "surrogate_released",
        "surrogate_assigned_to_queue",
        "surrogate_assigned",
        "user_role_changed",
        "user_deactivated",
        "member.update",
    },
}


def identifier(value):
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return None


def digest(value):
    return (
        value
        if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
        else None
    )


def timestamp(value):
    return (
        value
        if isinstance(value, str) and re.fullmatch(r"[0-9T:.+Z-]{19,40}", value)
        else None
    )


def projected_event(event, source, stages):
    result = {"source": source}
    for key in UUID_FIELDS:
        if event.get(key) is not None:
            result[key] = identifier(event[key])
    for key in TIMES:
        if event.get(key) is not None:
            result[key] = timestamp(event[key])
    for key, allowed in ENUMS.items():
        if event.get(key) in allowed:
            result[key] = event[key]
    for key in (
        "is_undo",
        "approval_crossing_current_configuration",
        "required_references_valid",
        "new_active",
        "old_active",
    ):
        if isinstance(event.get(key), bool):
            result[key] = event[key]
    for key in ("from_stage_id", "to_stage_id"):
        if event.get(key) is not None:
            stage_id = identifier(event[key])
            result[key] = stage_id
            result[key.replace("_id", "")] = stages.get(stage_id, "Unknown stage")
    return result


def prepare(ledger, organization_id):
    organization_id = str(UUID(organization_id))
    organizations = ledger.get("organizations", [ledger])
    matches = [
        item for item in organizations if item.get("organization_id") == organization_id
    ]
    if len(matches) != 1:
        raise ValueError("target_organization_not_unique")
    org = matches[0]
    members, counters = {}, {}
    for member in sorted(org["members"], key=lambda item: item["user_id"]):
        user_id = identifier(member["user_id"])
        if not user_id:
            raise ValueError("invalid_member_identifier")
        role = member.get("role")
        label = ROLE_LABELS.get(role, "Member")
        counters[label] = counters.get(label, 0) + 1
        members[user_id] = {
            "id": user_id,
            "alias": f"{label} {counters[label]}",
            "active_intake": role == "intake_specialist"
            and member["membership_active"] is True
            and member["user_active"] is True,
        }
    stages = {
        identifier(stage["id"]): STAGES.get(
            stage.get("stage_key"), "Custom / unknown stage"
        )
        for stage in org["stages"]
    }
    records = []
    for record in org["records"]:
        kind, record_id = record["kind"], identifier(record["record_id"])
        if kind not in {"surrogate", "donor"} or not record_id:
            raise ValueError("invalid_record_reference")
        number = record.get("record_number")
        if not isinstance(number, str) or not re.fullmatch(
            r"S[0-9]+" if kind == "surrogate" else r"D[0-9]+", number
        ):
            number = f"{kind.title()} {record_id[:8]}"
        classification = record["review_classification"]
        historical = classification["historical_classification"]
        if historical not in {"verified", "candidate", "ambiguous"}:
            raise ValueError("invalid_classification")
        timeline = []
        for key, label in (
            ("status_history", "Stage"),
            ("ownership_activity", "Ownership activity"),
            ("ownership_audit_observations", "Ownership audit"),
            ("workflow_owner_observations", "Workflow observation"),
        ):
            timeline.extend(
                projected_event(event, label, stages) for event in record.get(key, [])
            )
        references = {
            value
            for event in timeline
            for key, value in event.items()
            if key in UUID_FIELDS and value
        }
        owner_id = identifier(record["current_owner"].get("id"))
        candidate = identifier(classification.get("candidate_user_id"))
        references.update(value for value in (owner_id, candidate) if value)
        timeline.extend(
            projected_event(event, "Role audit", stages)
            for event in org["role_history"]
            if event.get("user_id") in references
        )
        timeline.sort(
            key=lambda event: (
                event.get("at") or event.get("recorded_at") or "",
                event.get("source", ""),
                event.get("id") or "",
            )
        )
        records.append(
            {
                "id": record_id,
                "kind": kind,
                "number": number,
                "url": f"https://ewi.surrogacyforce.com/{'surrogates' if kind == 'surrogate' else 'donors'}/{record_id}",
                "stage": stages.get(identifier(record["stage_id"]), "Unknown stage"),
                "archived": record["is_archived"] is True,
                "owner_type": record["current_owner"].get("type")
                if record["current_owner"].get("type") in {"user", "queue"}
                else "unknown",
                "owner_id": owner_id,
                "candidate_id": candidate,
                "classification": historical,
                "direct_owner": classification["current_direct_owner"][
                    "scope_preservation_candidate"
                ]
                is True,
                "gaps": [
                    GAPS.get(reason, "Unrecognized evidence gap")
                    for reason in classification["reasons"]
                ],
                "timeline": timeline,
                "record_fingerprint": digest(record["record_fingerprint"]),
                "evidence_fingerprint": digest(record["evidence_fingerprint"]),
            }
        )
    if any(
        not record["record_fingerprint"] or not record["evidence_fingerprint"]
        for record in records
    ):
        raise ValueError("missing_record_fingerprint")
    return {
        "organization_id": organization_id,
        "source_commit": org["source_commit"],
        "evidence_fingerprint": digest(org["evidence_fingerprint"]),
        "members": members,
        "records": records,
    }


CSS = """
:root{color-scheme:light;font:14px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#292824;background:#faf9f6}*{box-sizing:border-box}body{margin:0;padding:32px}main{max-width:1600px;margin:auto}header{display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin-bottom:24px}h1{font-size:24px;font-weight:600;letter-spacing:-.5px;margin:0}#status{color:#68655e;margin-right:auto}button,select,textarea{font:inherit;border:1px solid #d4d0c8;border-radius:6px;background:white;color:inherit}button{padding:9px 14px;cursor:pointer;background:#393f34;color:white;border-color:#393f34}button:hover{background:#252b21}select{padding:8px;width:100%;min-width:180px}textarea{width:100%;min-height:68px;padding:8px;resize:vertical;margin-top:8px}select:focus,textarea:focus,button:focus-visible,summary:focus-visible,a:focus-visible{outline:3px solid #9baf94;outline-offset:2px}.table-scroll{overflow:auto;border:1px solid #ddd9d1;border-radius:9px;background:#fff}table{border-collapse:collapse;width:100%;min-width:1100px}th{text-align:left;background:#f3f1ec;color:#5d5a53;font-size:12px;font-weight:600;padding:12px 16px;border-bottom:1px solid #ddd9d1}td{padding:16px;vertical-align:top;border-bottom:1px solid #ebe8e1}tr:last-child td{border-bottom:0}tbody tr:hover{background:#fcfbf8}a{color:#345943;text-underline-offset:3px;font-weight:600}small{display:block;color:#747067}.mono{font:11px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;overflow-wrap:anywhere}.badge{display:inline-block;border-radius:4px;padding:2px 6px;background:#eeeae2;font-size:12px;margin-top:5px}.decision{min-width:265px}.gaps{padding:0 0 0 16px;margin:6px 0;font-size:12px;color:#6b5741}details{margin-top:8px}summary{cursor:pointer;color:#59664e}details p{margin:6px 0}.timeline{max-width:750px;max-height:420px;overflow:auto;padding:8px;background:#f7f5f0}.event{border-bottom:1px solid #dedad2;padding:10px 0}.event:first-child{padding-top:0}.event:last-child{border:0}pre{white-space:pre-wrap;font:11px/1.5 ui-monospace,SFMono-Regular,monospace;margin:5px 0}#notice{font-size:12px;color:#746b5b;margin:0 0 12px}#error{color:#9a3028;min-height:22px;margin:8px 0}[hidden]{display:none!important}label{font-size:12px;color:#5d5a53;display:block;margin-top:6px}@media(max-width:700px){body{padding:16px}h1{font-size:21px}header{gap:10px}#status{width:100%}}@media print{body{padding:0}button,.decision{display:none}.table-scroll{overflow:visible}table{min-width:0}details{break-inside:avoid}}
"""

JS = r"""
'use strict';
const data=JSON.parse(document.getElementById('review-data').textContent);
const decisions=new Map();
const $=id=>document.getElementById(id);
const make=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
const alias=id=>data.members[id]?.alias || (id ? 'Unlisted member' : 'None recorded');
const activeIntake=Object.values(data.members).filter(member=>member.active_intake).sort((a,b)=>a.alias.localeCompare(b.alias,undefined,{numeric:true}));
function identity(id,type){const box=make('div',type==='queue'?'Queue':type==='unknown'?'Unknown owner':alias(id));if(id){const d=make('details');d.append(make('summary','ID'),make('span',id,'mono'));box.append(d);}return box;}
function update(){const count=[...decisions.values()].filter(row=>row.decision!==null).length;$('status').textContent=`${data.records.length} records · ${count} selected · ${data.records.length-count} unreviewed`;}
function option(value,label){const node=make('option',label);node.value=value;return node;}
for(const record of data.records){
 const key=`${record.kind}:${record.id}`;
 decisions.set(key,{decision:null,retained_user_id:null,evidence_reference:''});
 const tr=make('tr');
 const recordCell=make('td');const link=make('a',record.number);link.href=record.url;link.target='_blank';link.rel='noopener noreferrer';link.referrerPolicy='no-referrer';recordCell.append(link,make('small',record.stage));if(record.archived)recordCell.append(make('span','Archived','badge'));const rd=make('details');rd.append(make('summary','Record ID'),make('span',record.id,'mono'));recordCell.append(rd);tr.append(recordCell);
 const owner=make('td');owner.append(identity(record.owner_id,record.owner_type));if(record.direct_owner)owner.append(make('span','Current active Intake','badge'));tr.append(owner);
 const candidate=make('td');candidate.append(identity(record.candidate_id,'user'),make('span',record.classification==='verified'?'Existing human review':record.candidate_id?'Recorded assignment — unverified':'No owner identified','badge'));tr.append(candidate);
 const evidence=make('td');const gaps=make('ul',undefined,'gaps');for(const gap of record.gaps)gaps.append(make('li',gap));gaps.append(make('li','Ownership and historical role logs may be incomplete'));evidence.append(gaps);
 const detail=make('details');detail.append(make('summary',`Evidence timeline (${record.timeline.length})`));const timeline=make('div',undefined,'timeline');for(const event of record.timeline){const block=make('div',undefined,'event');block.append(make('strong',event.source),make('small',(event.at||event.recorded_at||'Time not recorded')+' · UTC'));const display={...event};delete display.source;for(const [field,value] of Object.entries(event)){if(field.endsWith('user_id')||field==='from_id'&&event.from_type==='user'||field==='to_id'&&event.to_type==='user'){if(value)display[field]=`${alias(value)} · ${value}`;}}block.append(make('pre',JSON.stringify(display,null,2)));timeline.append(block);}if(!record.timeline.length)timeline.append(make('p','No recognized metadata events'));detail.append(timeline);evidence.append(detail);tr.append(evidence);
 const controls=make('td',undefined,'decision');const choose=make('select');choose.setAttribute('aria-label',`Decision for ${record.number}`);choose.append(option('','Unreviewed'),option('retain_verified_owner','Retain specified active Intake'),option('no_verified_owner','No verified former Intake'));
 const userLabel=make('label','Active Intake member');const user=make('select');user.setAttribute('aria-label',`Retained Intake member for ${record.number}`);user.append(option('','Select member'));for(const member of activeIntake)user.append(option(member.id,`${member.alias} · ${member.id.slice(0,8)}`));const selectedId=make('small',undefined,'mono');userLabel.append(user,selectedId);userLabel.hidden=true;
 const noteLabel=make('label','Evidence reference / review note');const note=make('textarea');note.maxLength=500;note.setAttribute('aria-label',`Evidence reference for ${record.number}`);noteLabel.append(note);noteLabel.hidden=true;
 choose.addEventListener('change',()=>{const row=decisions.get(key);row.decision=choose.value||null;row.retained_user_id=null;user.value='';selectedId.textContent='';userLabel.hidden=choose.value!=='retain_verified_owner';noteLabel.hidden=!choose.value;update();});user.addEventListener('change',()=>{decisions.get(key).retained_user_id=user.value||null;selectedId.textContent=user.value;});note.addEventListener('input',()=>{decisions.get(key).evidence_reference=note.value;});controls.append(choose,userLabel,noteLabel);tr.append(controls);$('records').append(tr);
}
function collectDecisions(){
 return data.records.map(record=>{const draft=decisions.get(`${record.kind}:${record.id}`);if(draft.decision==='retain_verified_owner'&&!activeIntake.some(member=>member.id===draft.retained_user_id))throw new Error(`Select an active Intake member for ${record.number}.`);if(draft.decision&&!draft.evidence_reference.trim())throw new Error(`Add an evidence reference for ${record.number}.`);return {kind:record.kind,record_id:record.id,record_number:record.number,expected_fingerprint:record.record_fingerprint,evidence_fingerprint:record.evidence_fingerprint,decision:draft.decision,intake_user_id:draft.decision==='retain_verified_owner'?draft.retained_user_id:null,evidence_reference:draft.decision?draft.evidence_reference.trim():null};});
}
$('download').addEventListener('click',()=>{try{const rows=collectDecisions();const result={format:'handoff-review-decisions-v1',organization_id:data.organization_id,source_commit:data.source_commit,evidence_fingerprint:data.evidence_fingerprint,exported_at:new Date().toISOString(),all_reviewed:rows.every(row=>row.decision!==null),applied:false,decisions:rows};const blob=new Blob([JSON.stringify(result,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const link=make('a');link.href=url;link.download='handoff-review-decisions.json';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);$('error').textContent='';$('notice').textContent='Draft downloaded. No access changes applied.';}catch(error){$('error').textContent=error.message;}});
update();
"""


def render(ledger, organization_id):
    data = prepare(ledger, organization_id)
    embedded = (
        json.dumps(data, ensure_ascii=True, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )
    script_hash = base64.b64encode(hashlib.sha256(JS.encode()).digest()).decode()
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'sha256-{script_hash}'; style-src 'unsafe-inline'; connect-src 'none'; img-src 'none'; font-src 'none'; base-uri 'none'; form-action 'none'"><title>Historical handoff review</title><style>{CSS}</style></head>
<body><main><header><h1>Historical handoff review</h1><span id="status" aria-live="polite"></span><button id="download" type="button">Download decisions JSON</button></header><p id="notice">Local draft. Download saves decisions; nothing is applied to the CRM.</p><p id="error" role="alert"></p><div class="table-scroll"><table><thead><tr><th scope="col">Record / stage</th><th scope="col">Current owner</th><th scope="col">Historical candidate</th><th scope="col">Evidence gaps / timeline</th><th scope="col">Decision</th></tr></thead><tbody id="records"></tbody></table></div></main><script type="application/json" id="review-data">{embedded}</script><script>{JS}</script></body></html>"""
    return html, len(data["records"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("organization_id")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.ledger.stat().st_size > 50 * 1024 * 1024:
        raise SystemExit("ledger_size_exceeded")
    document, count = render(json.loads(args.ledger.read_text()), args.organization_id)
    args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=args.output.parent, delete=False
        ) as stream:
            name = stream.name
            os.chmod(name, 0o600)
            stream.write(document)
        os.replace(name, args.output)
    finally:
        if name and Path(name).exists():
            Path(name).unlink()
    print(f"Rendered {count} records; output permissions 0600.")


if __name__ == "__main__":
    main()

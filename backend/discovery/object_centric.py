"""Object-centric event log (OCEL 2.0-shaped) built from chat-derived activity.

Classic single-case mining collapses every observation onto one case, so a
process that really involves an invoice *and* a purchase order *and* a
shipment reads as one linear trace — hiding exactly the intersection points
where multi-object processes fail. This module re-expresses the same
evidence as an OCEL 2.0-style log:

- events reference **multiple typed objects** with qualified E2O links
  (case, actor, ticket, vendor, amount, email-domain),
- objects carry deduplicated co-observed O2O relationships,
- per-object traces and per-type summaries expose the intersections.

Extraction is deterministic regex over message content/metadata — no LLM in
the log-building path, so exports are reproducible and auditable. The output
mirrors the OCEL 2.0 JSON structure closely enough to load into OCPM tooling
after a key rename, while staying honest about what it is: an adapter, not a
certified serializer.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from ..models.schema import Activity, Message

TICKET_RE = re.compile(r"\b((?:INC|CASE|TICKET)[-#]?\d{2,})\b", re.IGNORECASE)
VENDOR_RE = re.compile(r"\bvendor[:\s]+([A-Za-z0-9][A-Za-z0-9_-]{1,30})", re.IGNORECASE)
AMOUNT_RE = re.compile(r"\$\s?(\d[\d,]*(?:\.\d{1,2})?)")
EMAIL_RE = re.compile(r"\b([\w.+-]+)@([\w-]+\.[\w.-]+)\b")

MAX_EVIDENCE_CHARS = 240


def extract_objects(activity: Activity,
                    messages_by_id: dict[str, Message]) -> dict[str, list[str]]:
    """Typed object ids touched by one activity.

    The case is always present; everything else is mined from the source
    messages' text and metadata. Deterministic by construction.
    """
    objects: dict[str, list[str]] = {"case": [f"case:{activity.case_id}"]}
    for actor in activity.actors:
        objects.setdefault("actor", []).append(f"actor:{actor}")

    texts: list[str] = []
    for mid in activity.source_messages:
        message = messages_by_id.get(mid)
        if message is None:
            continue
        texts.append(message.content)
        for email in EMAIL_RE.findall(message.content):
            domain = email[1].lower().rstrip(".")
            objects.setdefault("email-domain", []).append(f"domain:{domain}")
        for meta_ticket in (message.metadata or {}).get("ticket_ids", []) or []:
            objects.setdefault("ticket", []).append(f"ticket:{meta_ticket}")

    blob = "\n".join(texts).lower()
    for number in TICKET_RE.findall(blob):
        objects.setdefault("ticket", []).append(f"ticket:{number.upper()}")
    for vendor in VENDOR_RE.findall(blob):
        slug = re.sub(r"[^a-z0-9_-]", "-", vendor.lower()).strip("-")
        if slug:
            objects.setdefault("vendor", []).append(f"vendor:{slug}")
    for amount in AMOUNT_RE.findall(blob):
        normalized = amount.replace(",", "").replace("$", "")
        objects.setdefault("amount", []).append(f"amount:${normalized}")
    return objects


def _event_attributes(activity: Activity,
                      messages_by_id: dict[str, Message]) -> list[dict[str, str]]:
    evidence_parts = [
        messages_by_id[mid].content[:MAX_EVIDENCE_CHARS]
        for mid in activity.source_messages if mid in messages_by_id
    ]
    attributes = [
        {"name": "category", "type": "string", "value": activity.category},
        {"name": "confidence", "type": "float", "value": round(activity.confidence, 3)},
    ]
    if evidence_parts:
        attributes.append({"name": "evidence", "type": "string",
                           "value": " | ".join(evidence_parts)[:MAX_EVIDENCE_CHARS]})
    return attributes


def build_object_log(activities: list[Activity],
                     messages: list[Message]) -> dict[str, Any]:
    """OCEL 2.0-shaped log: eventTypes, events, objectTypes, objects."""
    messages_by_id = {m.id: m for m in messages}

    events: list[dict[str, Any]] = []
    object_relationships: dict[str, set[tuple[str, str]]] = defaultdict(set)
    seen_objects: dict[str, str] = {}  # object id -> type

    for activity in sorted(activities, key=lambda a: (a.timestamp, a.id)):
        objects = extract_objects(activity, messages_by_id)
        relationships: list[dict[str, str]] = []
        for obj_type, ids in objects.items():
            for object_id in ids:
                relationships.append({"objectId": object_id,
                                      "qualifier": obj_type})
                seen_objects.setdefault(object_id, obj_type)

        events.append({
            "id": f"evt:{activity.id}",
            "type": activity.name,
            "time": activity.timestamp.isoformat(),
            "attributes": _event_attributes(activity, messages_by_id),
            "relationships": relationships,
        })

        # O2O: objects co-observed by the same event relate to each other.
        flat = [(obj_type, oid) for obj_type, ids in objects.items() for oid in ids]
        for index, (type_a, id_a) in enumerate(flat):
            for type_b, id_b in flat[index + 1:]:
                if id_a == id_b:
                    continue
                pair = (id_a, id_b) if id_a < id_b else (id_b, id_a)
                object_relationships[pair].add(
                    f"{type_a}->{type_b}" if id_a < id_b else f"{type_b}->{type_a}")

    objects_out: list[dict[str, Any]] = []
    for object_id, obj_type in sorted(seen_objects.items()):
        relationships: list[dict[str, str]] = []
        for pair in sorted(object_relationships):
            if object_id not in pair:
                continue
            other = pair[0] if pair[1] == object_id else pair[1]
            for qualifier in sorted(object_relationships[pair]):
                relationships.append({"objectId": other, "qualifier": qualifier})
        objects_out.append({
            "id": object_id,
            "type": obj_type,
            "relationships": relationships,
        })

    event_types = sorted({event["type"] for event in events})
    object_types = sorted({o["type"] for o in objects_out})

    summaries = {
        obj_type: {
            "objects": sum(1 for o in objects_out if o["type"] == obj_type),
            "events_touching": sum(
                1 for e in events
                if any(r["qualifier"] == obj_type for r in e["relationships"])),
        }
        for obj_type in object_types
    }

    return {
        "ocel_version": "2.0-inspired",
        "generator": "autopilot-fde object_centric v1",
        "eventTypes": [{"name": name, "attributes": []} for name in event_types],
        "events": events,
        "objectTypes": [{"name": name, "attributes": []} for name in object_types],
        "objects": objects_out,
        "summaries": summaries,
    }


def object_trace(log: dict[str, Any], object_id: str) -> list[dict[str, Any]]:
    """Chronological slice of events touching one object."""
    touches = []
    for event in log["events"]:
        if any(rel["objectId"] == object_id for rel in event["relationships"]):
            touches.append(event)
    return sorted(touches, key=lambda e: e["time"])

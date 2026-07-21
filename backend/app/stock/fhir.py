"""
Mapping between the Stock grid rows and HL7 FHIR ``InventoryItem`` resources
(FHIR R5), so what we store and serve is HL7-compliant.

Grid columns -> FHIR InventoryItem:
  drug          -> code[0].coding[0].display (+ RxNorm system) and name[0].name
  location      -> instance.location.display
  on_hand       -> instance.quantity.value
  unit          -> netContent.unit  (and instance.quantity.unit)
  expiry_date   -> instance.expiry
  avg_daily_use -> characteristic{ "avg_daily_use", valueQuantity }
  supplier      -> characteristic{ "supplier", valueString }
  last_delivery -> characteristic{ "last_delivery", valueString }

The mapping is lossless in both directions for these fields.
"""

from __future__ import annotations

from typing import Any

RXNORM = "http://www.nlm.nih.gov/research/umls/rxnorm"

# The grid's column order (kept in sync with the frontend Stock screen).
STOCK_COLUMNS = [
    "drug",
    "location",
    "on_hand",
    "unit",
    "expiry_date",
    "avg_daily_use",
    "supplier",
    "last_delivery",
]


def _num(value: Any) -> float | None:
    if value in ("", None):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _char(resource: dict, name: str) -> Any:
    for c in resource.get("characteristic", []):
        if c.get("characteristicType", {}).get("text") == name:
            if "valueQuantity" in c:
                return c["valueQuantity"].get("value")
            return c.get("valueString")
    return None


def row_to_inventory_item(row: dict, resource_id: str) -> dict:
    """Build a FHIR R5 InventoryItem from a grid row."""
    drug = str(row.get("drug", "") or "")
    location = str(row.get("location", "") or "")
    unit = str(row.get("unit", "") or "")
    on_hand = _num(row.get("on_hand"))
    avg_daily = _num(row.get("avg_daily_use"))

    resource: dict = {
        "resourceType": "InventoryItem",
        "id": resource_id,
        "status": "active",
        "code": [{"coding": [{"system": RXNORM, "display": drug}], "text": drug}],
        "name": [{"nameType": {"text": "official"}, "language": "en", "name": drug}],
        "netContent": {"value": on_hand, "unit": unit} if unit or on_hand is not None else None,
        "instance": {
            "location": {"display": location} if location else None,
            "quantity": {"value": on_hand, "unit": unit} if on_hand is not None else None,
            "expiry": str(row.get("expiry_date", "") or "") or None,
        },
        "characteristic": [],
    }

    if avg_daily is not None:
        resource["characteristic"].append(
            {"characteristicType": {"text": "avg_daily_use"}, "valueQuantity": {"value": avg_daily, "unit": "unit/day"}}
        )
    for key in ("supplier", "last_delivery"):
        val = str(row.get(key, "") or "")
        if val:
            resource["characteristic"].append({"characteristicType": {"text": key}, "valueString": val})

    # Drop empty optional structures for cleaner FHIR.
    if resource["netContent"] is None:
        del resource["netContent"]
    if not resource["characteristic"]:
        del resource["characteristic"]
    inst = resource["instance"]
    resource["instance"] = {k: v for k, v in inst.items() if v is not None}
    return resource


def inventory_item_to_row(resource: dict) -> dict:
    """Recover a grid row from a FHIR InventoryItem."""
    code = (resource.get("code") or [{}])[0]
    drug = code.get("text") or (code.get("coding") or [{}])[0].get("display", "")
    instance = resource.get("instance", {})
    quantity = instance.get("quantity", {})
    net = resource.get("netContent", {})

    return {
        "drug": drug or "",
        "location": (instance.get("location") or {}).get("display", "") or "",
        "on_hand": quantity.get("value"),
        "unit": quantity.get("unit") or net.get("unit", "") or "",
        "expiry_date": instance.get("expiry", "") or "",
        "avg_daily_use": _char(resource, "avg_daily_use"),
        "supplier": _char(resource, "supplier") or "",
        "last_delivery": _char(resource, "last_delivery") or "",
    }


def to_bundle(resources: list[dict]) -> dict:
    """Wrap resources in a FHIR searchset Bundle."""
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "total": len(resources),
        "entry": [{"resource": r} for r in resources],
    }

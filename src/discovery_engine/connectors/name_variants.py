from __future__ import annotations

import re
from typing import Iterable

from .base import Connector, ConnectorContext
from ..models import Entity, Finding, Relationship, stable_id


class NameVariantConnector(Connector):
    """Generates name, username, and profile discovery candidates for a person-like seed."""

    name = "name_variants"
    entity_types = {"Person", "Username", "Profile"}
    relationship_types = {"has_name_variant", "uses_username", "has_profile"}

    def can_handle(self, task_query: str) -> bool:
        query = (task_query or "").strip()
        return bool(query) and not query.startswith(("http://", "https://"))

    def _name_variants(self, name: str) -> list[str]:
        text = re.sub(r"\s+", " ", name.strip())
        tokens = [t for t in text.split() if t]
        variants = {text}
        if len(tokens) >= 2:
            variants.add(f"{tokens[0]} {tokens[-1]}")
            variants.add(f"{tokens[0]} {''.join(tokens[1:])}")
            variants.add(f"{tokens[0]}_{tokens[-1]}")
            variants.add(f"@{tokens[0].lower()}_{tokens[-1].lower()}")
        if len(tokens) >= 3:
            variants.add(f"{tokens[0]} {tokens[1]} {tokens[-1]}")
        normalized = re.sub(r"[^a-zA-Z0-9_]", "", text.lower()).replace("_", "")
        if normalized:
            variants.add(normalized)
            variants.add(f"@{normalized}")
            variants.add(normalized.replace(" ", "_"))
        return sorted(v for v in variants if v)

    def _username_variants(self, name: str) -> list[str]:
        text = re.sub(r"\s+", " ", name.strip())
        tokens = [t for t in text.split() if t]
        handles = set()
        if len(tokens) >= 2:
            handles.add(f"{tokens[0].lower()}_{tokens[-1].lower()}")
            handles.add(f"{tokens[0].lower()}{tokens[-1].lower()}")
            handles.add(f"{tokens[0].lower()}.{tokens[-1].lower()}")
            handles.add(f"@{tokens[0].lower()}_{tokens[-1].lower()}")
        if tokens:
            handles.add(tokens[0].lower())
        return sorted(h for h in handles if h)

    def search(self, query: str, context: ConnectorContext) -> Iterable[Finding]:
        text = (query or "").strip()
        if not text:
            return []

        person_id = stable_id("person", text)
        person = Entity(
            person_id,
            "Person",
            text,
            {
                "name_variants": self._name_variants(text),
                "username_variants": self._username_variants(text),
                "seed_query": text,
            },
            "name_variant_connector",
            0.88,
        )

        findings: list[Finding] = [Finding(person, relationships=[])]

        for variant in self._name_variants(text):
            variant_id = stable_id("entity", "variant", variant)
            variant_entity = Entity(
                variant_id,
                "Profile",
                variant,
                {"variant_type": "name", "source_name": text},
                "name_variant_connector",
                0.72,
            )
            findings.append(
                Finding(
                    variant_entity,
                    relationships=[
                        Relationship(
                            stable_id("rel", person_id, variant_id, "has_name_variant"),
                            person_id,
                            variant_id,
                            "has_name_variant",
                            "name_variant_connector",
                            0.85,
                            attributes={"source": text, "variant": variant},
                        )
                    ],
                    source_url="",
                    attributes={"variant": variant},
                )
            )

        for handle in self._username_variants(text):
            handle_id = stable_id("user", handle)
            handle_entity = Entity(
                handle_id,
                "Username",
                handle,
                {"handle": handle, "owner": text},
                "name_variant_connector",
                0.79,
            )
            findings.append(
                Finding(
                    handle_entity,
                    relationships=[
                        Relationship(
                            stable_id("rel", person_id, handle_id, "uses_username"),
                            person_id,
                            handle_id,
                            "uses_username",
                            "name_variant_connector",
                            0.82,
                            attributes={"handle": handle},
                        )
                    ],
                    source_url="",
                    attributes={"handle": handle},
                )
            )

        return findings

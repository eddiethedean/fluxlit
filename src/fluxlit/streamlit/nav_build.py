"""Multipage nav: merge ``PageMeta.children`` with :class:`~fluxlit.pages.records.PageRecord`."""

from __future__ import annotations

import heapq
import warnings
from collections import defaultdict
from dataclasses import replace

from fluxlit.pages.records import PageRecord
from fluxlit.pages.slug import page_slug


def apply_children_overrides(records: list[PageRecord]) -> list[PageRecord]:
    """Merge ``title`` / ``icon`` from every ``PageMeta.children`` entry into matching records."""
    slug_to: dict[str, dict[str, str]] = {}
    for rec in records:
        meta = rec.page_meta
        if meta is None or not meta.children:
            continue
        for raw in meta.children:
            if not isinstance(raw, dict):
                continue
            p = raw.get("path") if raw.get("path") is not None else raw.get("url_path")
            if p is None:
                continue
            slug = page_slug(str(p))
            entry = slug_to.setdefault(slug, {})
            if raw.get("title") is not None:
                entry["title"] = str(raw["title"])
            if raw.get("icon") is not None:
                entry["icon"] = str(raw["icon"])

    out: list[PageRecord] = []
    for rec in records:
        slug = page_slug(rec.path)
        ovr = slug_to.get(slug)
        if not ovr:
            out.append(rec)
            continue
        title = ovr.get("title", rec.title)
        icon = ovr.get("icon", rec.icon)
        if title == rec.title and icon == rec.icon:
            out.append(rec)
        else:
            out.append(replace(rec, title=title, icon=icon))
    return out


def order_records_with_children(records: list[PageRecord]) -> list[PageRecord]:
    """Order pages so each ``PageMeta.children`` path appears after its declaring parent.

    Unknown child paths emit a warning and are ignored. When no ``children`` edges exist,
    order matches *records* (registration / prior sort order).
    """
    if not records:
        return []
    by_slug: dict[str, PageRecord] = {page_slug(r.path): r for r in records}
    index = {page_slug(r.path): i for i, r in enumerate(records)}
    edge_set: set[tuple[str, str]] = set()
    for rec in records:
        ps = page_slug(rec.path)
        meta = rec.page_meta
        if meta is None or not meta.children:
            continue
        for raw in meta.children:
            if not isinstance(raw, dict):
                continue
            p = raw.get("path") if raw.get("path") is not None else raw.get("url_path")
            if p is None:
                continue
            cslug = page_slug(str(p))
            if cslug == ps:
                continue
            if cslug not in by_slug:
                warnings.warn(
                    f"PageMeta.children references unknown path {p!r} (slug {cslug!r}); "
                    "skipping for navigation.",
                    UserWarning,
                    stacklevel=1,
                )
                continue
            edge_set.add((ps, cslug))

    if not edge_set:
        return list(records)

    adj: defaultdict[str, list[str]] = defaultdict(list)
    incoming: defaultdict[str, int] = defaultdict(int)
    nodes = list(by_slug.keys())
    for p, c in edge_set:
        adj[p].append(c)
        incoming[c] += 1
    for s in nodes:
        incoming.setdefault(s, 0)

    ready_slugs = sorted((s for s in nodes if incoming[s] == 0), key=lambda x: index[x])
    heap: list[tuple[int, str]] = [(index[s], s) for s in ready_slugs]
    heapq.heapify(heap)
    out_slugs: list[str] = []
    seen: set[str] = set()

    while heap:
        _, s = heapq.heappop(heap)
        if s in seen:
            continue  # pragma: no cover — duplicate heap entries are unexpected
        out_slugs.append(s)
        seen.add(s)
        for c in sorted(adj[s], key=lambda x: index[x]):
            incoming[c] -= 1
            if incoming[c] == 0:
                heapq.heappush(heap, (index[c], c))

    if len(seen) < len(nodes):
        warnings.warn(
            "PageMeta.children ordering contains a cycle among page paths; "
            "remaining pages are appended in registration order.",
            UserWarning,
            stacklevel=1,
        )

    for s in sorted(nodes, key=lambda x: index[x]):
        if s not in seen:
            out_slugs.append(s)

    return [by_slug[s] for s in out_slugs]


__all__ = [
    "apply_children_overrides",
    "order_records_with_children",
    "page_slug",
]

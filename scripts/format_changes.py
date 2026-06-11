"""Format Skycards data changes into Markdown Discord messages (stdlib only)."""

import argparse
import json
import sys

import country_data as cd

ARROW = "→"  # right arrow used in "old -> new"
HEADER_EMOJI = "\U0001F6A8"  # rotating light


def na(value, suffix=""):
    """Render a numeric stat; falsy (None/0/"") becomes N/A."""
    if not value:
        return "N/A"
    return f"{value}{suffix}"


def diff(old_list, new_list, key, fields):
    """Return (added, updated, removed).

    added/removed are record lists; updated is a list of (old, new) tuples whose
    tracked `fields` (list of (label, fn)) differ between old and new.
    """
    old_by = {r[key]: r for r in old_list if r.get(key) is not None}
    new_by = {r[key]: r for r in new_list if r.get(key) is not None}
    added = [new_by[k] for k in new_by if k not in old_by]
    removed = [old_by[k] for k in old_by if k not in new_by]
    updated = []
    for k in new_by:
        if k in old_by:
            o, n = old_by[k], new_by[k]
            if any(fn(o) != fn(n) for _, fn in fields):
                updated.append((o, n))
    return added, updated, removed


def _rarity(r):
    rn = r.get("rareness")
    return f"{rn / 100:.2f} ({r.get('xp')} xp)" if rn else "N/A"


def _weight(r):
    m = r.get("mtow")
    return f"{m / 1000:.2f}T" if m else "N/A"


MODEL_STATS = [
    ("Rarity", _rarity),
    ("First flight", lambda r: na(r.get("firstFlight"))),
    ("Wingspan", lambda r: na(r.get("wingspan"), "m")),
    ("Speed", lambda r: na(r.get("maxSpeed"), "kts")),
    ("Seats", lambda r: na(r.get("seats"))),
    ("Weight", _weight),
]
MODEL_CHANGE_FIELDS = MODEL_STATS + [("Name", lambda r: r.get("name") or "")]


def _model_title(r):
    name = f"{r.get('manufacturer', '')} {r.get('name', '')}".strip()
    return f"`{r['id']}` {name}".rstrip()


def _total_block(added_codes, updated_codes, removed_codes):
    def line(label, codes):
        body = f"`{','.join(codes)}`" if codes else "none"
        return f"- {label} ({len(codes)}): {body}"
    return "\n".join([
        "### TOTAL",
        line("Added", added_codes),
        line("Updated", updated_codes),
        line("Removed", removed_codes),
    ])


def _count_lines(rows):
    """Render [(label, count, codes), ...] as `- Label (count): \\`codes\\`` lines
    (count is the record total; codes may be a shorter list)."""
    def line(label, count, codes):
        body = f"`{','.join(codes)}`" if codes else "none"
        return f"- {label} ({count}): {body}"
    return [line(*r) for r in rows]


def _count_total_block(rows):
    """TOTAL block where the count is the number of records and the displayed
    codes are a (possibly shorter) list. `rows` is [(label, count, codes), ...]."""
    return "\n".join(["### TOTAL"] + _count_lines(rows))


def _assemble(thing, sections, total, link, footer=None):
    parts = [f"## {HEADER_EMOJI} Airpedia {thing} update", ""]
    for title, body in sections:
        parts.append(f"### {title}")
        if body:
            parts.append(body)
        parts.append("")
    parts.append(total)
    if footer:
        parts.append("")
        parts.append(footer)
    parts.append("")
    parts.append(f"For all changes see [commit](<{link}>)")
    return "\n".join(parts)


def _tldr(thing, added, updated, removed):
    return (f"{thing} update: {len(added)} added · "
            f"{len(updated)} updated · {len(removed)} removed")


MISC_TLDR_SUFFIX = "(non-gameplay)"


def _misc_message(thing, link):
    """Notice for updates that touched only non-gameplay fields (e.g. logoId,
    airport distance). The file still commits; this just flags it in Discord."""
    head = f"## {HEADER_EMOJI} Airpedia {thing} update"
    body = (f"Some miscellaneous changes were made to {thing}, not important "
            f"to gameplay. View them here: [commit](<{link}>)")
    return f"{head}\n\n{body}", f"Miscellaneous {thing} changes {MISC_TLDR_SUFFIX}"


def is_misc_tldr(tldr):
    """True when a TLDR came from _misc_message (non-gameplay-only change).
    The webhook uses this to suppress @everyone on misc notices."""
    return tldr.endswith(MISC_TLDR_SUFFIX)


def format_models(old_rows, new_rows, link):
    added, updated, removed = diff(old_rows, new_rows, "id", MODEL_CHANGE_FIELDS)
    if not (added or updated or removed):
        return _misc_message("aircraft", link)

    def added_block(r):
        lines = [_model_title(r)]
        lines += [f"\\- {label}: {fn(r)}" for label, fn in MODEL_STATS]
        return "\n".join(lines)

    def updated_block(o, n):
        lines = [_model_title(n)]
        for label, fn in MODEL_CHANGE_FIELDS:
            if fn(o) != fn(n):
                lines.append(f"\\- {label}: {fn(o)} {ARROW} {fn(n)}")
        return "\n".join(lines)

    def removed_block(r):
        return f"{_model_title(r)} — Rarity {_rarity(r)}"

    added.sort(key=lambda r: r["id"])
    removed.sort(key=lambda r: r["id"])
    updated.sort(key=lambda t: t[1]["id"])

    sections = [
        (f"Added ({len(added)})", "\n\n".join(added_block(r) for r in added)),
        (f"Updated ({len(updated)})", "\n\n".join(updated_block(o, n) for o, n in updated)),
        (f"Removed ({len(removed)})", "\n".join(removed_block(r) for r in removed)),
    ]
    total = _total_block(
        [r["id"] for r in added],
        [n["id"] for _, n in updated],
        [r["id"] for r in removed],
    )
    msg = _assemble("aircraft", sections, total, link,
                    footer=f"Total aircraft: {len(new_rows):,}")
    return msg, _tldr("Aircraft", added, updated, removed)


def _codes_span(iata, icao):
    return "/".join(f"`{c}`" for c in (iata, icao) if c)


def render_geo(records, get_place, name_key, render_entry, with_region):
    """Render records grouped continent -> country -> [region] as Markdown lines.

    render_entry(record) returns a list of relative lines (marker line first,
    sub-bullets indented by two spaces). Entries are sorted by name_key.
    """
    tree = {}
    for r in records:
        iso, region = cd.parse_place_code(get_place(r))
        cont = cd.continent(iso)
        key_region = region if with_region else None
        tree.setdefault(cont, {}).setdefault(iso, {}).setdefault(key_region, []).append(r)

    lines = []
    for cont in cd.CONTINENT_ORDER:
        if cont not in tree:
            continue
        lines.append(f"**{cont.upper()}**")
        for iso in sorted(tree[cont], key=lambda i: cd.country_name(i)):
            lines.append(f"{cd.flag(iso)} {cd.country_name(iso)}")
            regions = tree[cont][iso]
            # None (no region) first, then named regions alphabetically.
            for region in sorted(regions, key=lambda x: (x is not None, x or "")):
                entries = sorted(regions[region], key=name_key)
                base = "  " if region is None else "    "
                if region is not None:
                    lines.append(f"  {region}")
                for e in entries:
                    for ln in render_entry(e):
                        lines.append(base + ln)
    return "\n".join(lines)


def _airport_line(r, marker):
    name = r.get("name") or "Unknown airport"
    iata = r.get("iata")
    icao = r.get("icao")
    if iata:
        label = f"[{name}](<https://www.flightradar24.com/data/airports/{iata}>)"
    else:
        label = name
    codes = _codes_span(iata, icao)
    return f"{marker} {label} ({codes})" if codes else f"{marker} {label}"


AIRPORT_CHANGE_FIELDS = [
    ("Name", lambda r: r.get("name") or ""),
    ("City", lambda r: r.get("city") or ""),
    ("Country", lambda r: cd.country_name(cd.parse_place_code(r.get("placeCode"))[0])),
    ("Region", lambda r: cd.parse_place_code(r.get("placeCode"))[1] or ""),
]


AIRPORT_MAJOR_SIZE = 4000  # size >= this => "major" (unlockable) airport


def _is_major(r):
    s = r.get("size")
    return s is not None and s >= AIRPORT_MAJOR_SIZE


def _size_transitions(old_rows, new_rows):
    """IATA codes of airports that crossed the major/minor size threshold.

    Only considers airports present in both versions (matched by id); returns
    (became_major, became_minor) as sorted IATA code lists.
    """
    old_by = {r["id"]: r for r in old_rows}
    became_major, became_minor = [], []
    for n in new_rows:
        o = old_by.get(n["id"])
        if o is None or not n.get("iata") or _is_major(o) == _is_major(n):
            continue
        (became_major if _is_major(n) else became_minor).append(n["iata"])
    return sorted(became_major), sorted(became_minor)


def _unlockable_block(became_major, became_minor):
    lines = ["### Unlockable airports changes"]
    if became_major:
        lines.append(f"Became major: `{','.join(became_major)}`")
    if became_minor:
        lines.append(f"Became minor: `{','.join(became_minor)}`")
    return "\n".join(lines)


def _iata_codes(records):
    return sorted(r["iata"] for r in records if r.get("iata"))


def _airport_count_rows(added, updated_new, removed):
    """[(label, count, iata_codes), ...] shared by the TOTAL block and the
    Discord file-attachment caption."""
    return [
        ("Added", len(added), _iata_codes(added)),
        ("Updated", len(updated_new), _iata_codes(updated_new)),
        ("Removed", len(removed), _iata_codes(removed)),
    ]


def airports_caption(old_rows, new_rows):
    """Multi-line per-category IATA-code breakdown used as the Discord
    file-attachment caption. The one-line _tldr still feeds the commit body."""
    old_rows = [r for r in old_rows if r.get("iata")]
    new_rows = [r for r in new_rows if r.get("iata")]
    added, updated, removed = diff(old_rows, new_rows, "id", AIRPORT_CHANGE_FIELDS)
    rows = _airport_count_rows(added, [n for _, n in updated], removed)
    return "\n".join(_count_lines(rows))


def format_airports(old_rows, new_rows, link):
    # Upstream never deletes airports; it nulls their iata/icao while keeping
    # the id row. An airport without an iata is not a real (playable) airport
    # (see compare_airports.py, which skips them), so drop those before diffing
    # — a row that loses its iata then reads as a removal instead of vanishing.
    old_rows = [r for r in old_rows if r.get("iata")]
    new_rows = [r for r in new_rows if r.get("iata")]
    added, updated, removed = diff(old_rows, new_rows, "id", AIRPORT_CHANGE_FIELDS)
    became_major, became_minor = _size_transitions(old_rows, new_rows)
    if not (added or updated or removed or became_major or became_minor):
        return _misc_message("airports", link)
    place = lambda r: r.get("placeCode")
    name_key = lambda r: (r.get("name") or "")

    added_md = render_geo(added, place, name_key,
                          lambda r: [_airport_line(r, "+")], with_region=True)
    removed_md = render_geo(removed, place, name_key,
                            lambda r: [_airport_line(r, "\\-")], with_region=True)

    def updated_entry(pair):
        o, n = pair
        out = [_airport_line(n, "~")]
        for label, fn in AIRPORT_CHANGE_FIELDS:
            if fn(o) != fn(n):
                out.append(f"  \\- {label}: {na(fn(o))} {ARROW} {na(fn(n))}")
        return out

    updated_md = render_geo(updated, lambda t: t[1].get("placeCode"),
                            lambda t: (t[1].get("name") or ""),
                            updated_entry, with_region=True)

    sections = [
        (f"Added ({len(added)})", added_md),
        (f"Updated ({len(updated)})", updated_md),
        (f"Removed ({len(removed)})", removed_md),
    ]

    updated_new = [n for _, n in updated]
    total = _count_total_block(_airport_count_rows(added, updated_new, removed))
    if became_major or became_minor:
        total += "\n\n" + _unlockable_block(became_major, became_minor)
    msg = _assemble("airports", sections, total, link,
                    footer=f"Total airports: {len(new_rows):,}")
    return msg, _tldr("Airports", added, updated, removed)


def _comparison_records(diffs, kind):
    """Flatten airport_differences.json into airport-like records for one side."""
    records = []
    for iso, info in diffs.get("countries", {}).items():
        for ap in info.get(kind, []):
            records.append({
                "name": ap.get("name"),
                "iata": ap.get("iata") or None,
                "icao": ap.get("icao") or None,
                "link": ap.get("link"),
                "placeCode": iso,
            })
    return records


def _comparison_line(r, marker):
    name = r.get("name") or "Unknown airport"
    iata = r.get("iata")
    link = r.get("link") or (
        f"https://www.flightradar24.com/data/airports/{iata}" if iata else None)
    label = f"[{name}](<{link}>)" if link else name
    codes = _codes_span(iata, r.get("icao"))
    return f"{marker} {label} ({codes})" if codes else f"{marker} {label}"


def _airport_idents(airports_data):
    """Set of identities (IATA ∪ ICAO) present in an airports.json payload."""
    idents = set()
    for r in _rows(airports_data) or []:
        if r.get("iata"):
            idents.add(r["iata"])
        if r.get("icao"):
            idents.add(r["icao"])
    return idents


def _cmp_index(diffs, kind):
    """Flatten one side of the differences file into {identity: record}."""
    out = {}
    for r in _comparison_records(diffs or {}, kind):
        ident = r.get("iata") or r.get("icao")
        if ident:
            out[ident] = r
    return out


def _classify_side(old_idx, new_idx, old_iatas, new_iatas):
    """Classify one worklist side's transitions.

    Returns (new_records, resolved, skycards_driven):
    - new_records: FR24-driven items that newly entered the worklist (to list).
    - resolved: every transition that left the worklist, plus Skycards-driven
      entries (folded into the merged "resolved" count).
    - skycards_driven: transitions where airports.json membership flipped
      (used to detect a Skycards-update cycle).
    """
    new_records = []
    resolved = 0
    skycards_driven = 0
    for ident in set(old_idx) | set(new_idx):
        in_old = ident in old_idx
        in_new = ident in new_idx
        if in_old and in_new:
            continue
        changed = (ident in old_iatas) != (ident in new_iatas)
        if changed:
            skycards_driven += 1
        if in_new and not in_old:          # entered
            if changed:
                resolved += 1              # Skycards-driven -> airports webhook covers it
            else:
                new_records.append(new_idx[ident])
        else:                              # left the worklist
            resolved += 1
    return new_records, resolved, skycards_driven


def _country_idents(country, kind):
    return {a.get("iata") or a.get("icao")
            for a in country.get(kind, [])}


def _count_only(old_diffs, new_diffs):
    """Per-country net-standing deltas for countries whose airport identity sets
    did not change. Returns [(iso, delta), ...] sorted by iso, skipping zeros."""
    old_c = (old_diffs or {}).get("countries", {})
    new_c = (new_diffs or {}).get("countries", {})
    results = []
    for iso in sorted(set(old_c) | set(new_c)):
        o = old_c.get(iso, {})
        n = new_c.get(iso, {})
        if (_country_idents(o, "added_airports") != _country_idents(n, "added_airports")
                or _country_idents(o, "removed_airports") != _country_idents(n, "removed_airports")):
            continue
        old_net = o.get("fr24_count", 0) - o.get("skycards_count", 0)
        new_net = n.get("fr24_count", 0) - n.get("skycards_count", 0)
        delta = new_net - old_net
        if delta:
            results.append((iso, delta))
    return results


def _overall(new_diffs):
    """(to_be_added, to_be_removed, countries_with_worklist) from the new file."""
    countries = (new_diffs or {}).get("countries", {})
    to_add = sum(len(c.get("added_airports", [])) for c in countries.values())
    to_remove = sum(len(c.get("removed_airports", [])) for c in countries.values())
    n = sum(1 for c in countries.values()
            if c.get("added_airports") or c.get("removed_airports"))
    return to_add, to_remove, n


def _comparison_tldr(n_add, n_rem, n_count, resolved, to_add):
    clauses = []
    if n_add:
        clauses.append(f"{n_add} to add")
    if n_rem:
        clauses.append(f"{n_rem} to remove")
    if n_count:
        clauses.append(f"{n_count} count")
    if resolved:
        clauses.append(f"{resolved} resolved")
    if not clauses:
        return ""
    return f"Airport comparison: {' · '.join(clauses)} ({to_add:,} to add)"


def format_comparison(old_diffs, new_diffs, old_iatas, new_iatas, link):
    to_add, to_remove, n_countries = _overall(new_diffs)
    overall = (f"**OVERALL**\nTo be added: {to_add:,} · "
               f"To be removed: {to_remove:,} · {n_countries} countries")

    if old_diffs is None:
        head = f"## {HEADER_EMOJI} Airpedia airport comparison baseline"
        msg = "\n".join([head, "", overall, "", f"For all changes see [commit](<{link}>)"])
        tldr = f"Airport comparison baseline: {to_add:,} to add, {to_remove:,} to remove"
        return msg, tldr

    new_add, res_add, sky_add = _classify_side(
        _cmp_index(old_diffs, "added_airports"),
        _cmp_index(new_diffs, "added_airports"), old_iatas, new_iatas)
    new_rem, res_rem, sky_rem = _classify_side(
        _cmp_index(old_diffs, "removed_airports"),
        _cmp_index(new_diffs, "removed_airports"), old_iatas, new_iatas)
    resolved = res_add + res_rem
    skycards_driven = sky_add + sky_rem
    count_changes = _count_only(old_diffs, new_diffs)

    if not new_add and not new_rem and not resolved and not count_changes:
        return "", ""

    place = lambda r: r.get("placeCode")
    name_key = lambda r: (r.get("name") or "")

    parts = [f"## {HEADER_EMOJI} Airpedia airport comparison update", ""]
    if new_add:
        parts += ["**To be added** (new)",
                  render_geo(new_add, place, name_key,
                             lambda r: [_comparison_line(r, "+")], with_region=False), ""]
    if new_rem:
        parts += ["**To be removed** (new)",
                  render_geo(new_rem, place, name_key,
                             lambda r: [_comparison_line(r, "\\-")], with_region=False), ""]
    if resolved:
        parts += [f"✓ {resolved} resolved this update (see the airports update)", ""]
    if count_changes:
        lines = ["**Count changes** (not yet detailed)"]
        for iso, delta in count_changes:
            lines.append(f"{cd.flag(iso)} {cd.country_name(iso)} {delta:+d}")
        parts += ["\n".join(lines), ""]
    if skycards_driven:
        all_add = _comparison_records(new_diffs, "added_airports")
        if all_add:
            parts += ["**Still to be added**",
                      render_geo(all_add, place, name_key,
                                 lambda r: [_comparison_line(r, "+")], with_region=False), ""]
    parts += [overall, "", f"For all changes see [commit](<{link}>)"]

    tldr = _comparison_tldr(len(new_add), len(new_rem), len(count_changes),
                            resolved, to_add)
    return "\n".join(parts), tldr


def _fleet_slug(r):
    iata = r.get("iata")
    icao = r.get("icao") or ""
    return f"{iata}-{icao}".lower() if iata else icao.lower()


def _fleet_label(r):
    name = r.get("name") or "Unknown"
    return f"[{name}](<https://www.flightradar24.com/data/airlines/{_fleet_slug(r)}/fleet>)"


def _aircraft_count(r):
    return len(r.get("fleet") or [])


FLEET_CHANGE_FIELDS = [
    ("Name", lambda r: r.get("name") or ""),
    ("IATA", lambda r: r.get("iata") or ""),
    ("ICAO", lambda r: r.get("icao") or ""),
    ("Country", lambda r: cd.country_name(r.get("placeCode"))),
    ("Aircraft", lambda r: str(_aircraft_count(r))),
]


def format_fleets(old_list, new_list, link):
    # A fleet with no aircraft isn't a real (playable) fleet, mirroring how
    # iata-less airports are handled. Drop empty fleets before diffing so a
    # fleet emptying out reads as a removal, and one refilling reads as added.
    old_list = [r for r in old_list if _aircraft_count(r)]
    new_list = [r for r in new_list if _aircraft_count(r)]
    added, updated, removed = diff(old_list, new_list, "id", FLEET_CHANGE_FIELDS)
    if not (added or updated or removed):
        return _misc_message("fleets", link)
    place = lambda r: r.get("placeCode")
    name_key = lambda r: (r.get("name") or "")

    def added_entry(r):
        codes = _codes_span(r.get("iata"), r.get("icao"))
        return [f"+ {_fleet_label(r)} ({codes})", f"  \\- Aircraft: {_aircraft_count(r)}"]

    def removed_entry(r):
        codes = _codes_span(r.get("iata"), r.get("icao"))
        return [f"\\- {_fleet_label(r)} ({codes})"]

    def updated_entry(pair):
        o, n = pair
        codes = _codes_span(n.get("iata"), n.get("icao"))
        out = [f"~ {_fleet_label(n)} ({codes})"]
        for label, fn in FLEET_CHANGE_FIELDS:
            if fn(o) != fn(n):
                out.append(f"  \\- {label}: {fn(o)} {ARROW} {fn(n)}")
        return out

    added_md = render_geo(added, place, name_key, added_entry, with_region=False)
    removed_md = render_geo(removed, place, name_key, removed_entry, with_region=False)
    updated_md = render_geo(updated, lambda t: t[1].get("placeCode"),
                            lambda t: (t[1].get("name") or ""),
                            updated_entry, with_region=False)

    def icaos(records):
        return sorted(r["icao"] for r in records if r.get("icao"))

    sections = [
        (f"Added ({len(added)})", added_md),
        (f"Updated ({len(updated)})", updated_md),
        (f"Removed ({len(removed)})", removed_md),
    ]
    total = _total_block(icaos(added), icaos([n for _, n in updated]), icaos(removed))
    msg = _assemble("fleets", sections, total, link,
                    footer=f"Total fleets: {len(new_list):,}")
    return msg, _tldr("Fleets", added, updated, removed)


def _load(path):
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            txt = fh.read().strip()
    except FileNotFoundError:
        return None
    return json.loads(txt) if txt else None


def _rows(data):
    if data is None:
        return None
    if isinstance(data, dict):
        return data.get("rows", [])
    return data


FORMATTERS = {
    "models": format_models,
    "airports": format_airports,
    "airlines": format_fleets,
}
FIRST_RUN_LABEL = {"models": "Aircraft", "airports": "Airports", "airlines": "Fleets"}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Format Skycards data changes.")
    parser.add_argument("--type", required=True,
                        choices=["models", "airports", "airlines", "comparison"])
    parser.add_argument("--old")
    parser.add_argument("--new")
    parser.add_argument("--old-airports", dest="old_airports")
    parser.add_argument("--airports")
    parser.add_argument("--link", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--meta-out", dest="meta_out",
                        help="Write 'true'/'false' indicating a misc (non-gameplay) notice")
    parser.add_argument("--caption-out", dest="caption_out",
                        help="Write the Discord file-attachment caption (per-category "
                             "code breakdown for airports; falls back to the tldr)")
    args = parser.parse_args(argv)

    if args.type == "comparison":
        old_diffs = _load(args.old)
        new_diffs = _load(args.new) or {"countries": {}}
        old_iatas = _airport_idents(_load(args.old_airports))
        new_iatas = _airport_idents(_load(args.airports))
        msg, tldr = format_comparison(old_diffs, new_diffs, old_iatas, new_iatas, args.link)
    else:
        old_data = _load(args.old)
        new_rows = _rows(_load(args.new)) or []
        if old_data is None:
            label = FIRST_RUN_LABEL[args.type]
            msg = (f"## {HEADER_EMOJI} Airpedia {label.lower()} data published\n\n"
                   f"For all changes see [commit](<{args.link}>)")
            tldr = f"{label} data published"
        else:
            msg, tldr = FORMATTERS[args.type](_rows(old_data) or [], new_rows, args.link)

    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(msg)
    if args.meta_out:
        with open(args.meta_out, "w", encoding="utf-8") as fh:
            fh.write("true" if is_misc_tldr(tldr) else "false")
    if args.caption_out:
        # Airports get a per-category code breakdown; everything else reuses the
        # one-line tldr. Misc/first-run airport notices have no diff to break out.
        if args.type == "airports" and old_data is not None and not is_misc_tldr(tldr):
            caption = airports_caption(_rows(old_data) or [], new_rows)
        else:
            caption = tldr
        with open(args.caption_out, "w", encoding="utf-8") as fh:
            fh.write(caption + "\n")
    print(tldr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

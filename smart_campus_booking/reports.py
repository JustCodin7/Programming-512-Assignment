"""
reports.py
Cross-campus comparison reports for the System Operator (brief section 7.2):
  - "Resource usage across campuses"
  - "Booking trends and differences resulting from campus-specific rules"

The data comes out of SQLite, but the comparing itself is done here with
Python's own collections, on purpose:
  - dict  -> {campus name: {resource type: number of bookings}}
  - set   -> which resource types each campus offers, so set maths
             (intersection / difference) can show what every campus has in
             common and what only one campus has
  - list  -> one entry per campus, in a consistent order
"""

from database import get_connection
from policies import BookingPolicy


def get_campus_comparison():
    """One dict per campus: its booking policy sitting right next to its
    booking stats, so the numbers can be read against the rules that
    produced them. Includes campuses with zero bookings."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT campuses.*,
                  COUNT(bookings.booking_id) AS total_bookings,
                  COALESCE(SUM(CASE WHEN bookings.status = 'active' THEN 1 ELSE 0 END), 0) AS active_bookings,
                  COALESCE(SUM(CASE WHEN bookings.status = 'cancelled' THEN 1 ELSE 0 END), 0) AS cancelled_bookings,
                  AVG(bookings.duration_minutes) AS avg_duration,
                  MAX(bookings.duration_minutes) AS longest_booking
           FROM campuses
           LEFT JOIN bookings ON campuses.campus_id = bookings.campus_id
           GROUP BY campuses.campus_id
           ORDER BY campuses.campus_id"""
    )
    rows = cursor.fetchall()
    conn.close()

    comparison = []
    for row in rows:
        policy = BookingPolicy.from_campus(row)
        entry = {
            "name": row["name"],
            "policy": policy.short_summary(),
            "max_duration_minutes": row["max_duration_minutes"],
            "priority_override": bool(row["priority_override"]),
            "total_bookings": row["total_bookings"],
            "active_bookings": row["active_bookings"],
            "cancelled_bookings": row["cancelled_bookings"],
            "avg_duration": row["avg_duration"],          # None if no bookings yet
            "longest_booking": row["longest_booking"],    # None if no bookings yet
            "cap_usage_percent": None,
        }
        # only a campus WITH a duration cap can have "how much of the cap is used"
        if row["max_duration_minutes"] > 0 and row["avg_duration"] is not None:
            entry["cap_usage_percent"] = round(row["avg_duration"] / row["max_duration_minutes"] * 100)
        comparison.append(entry)
    return comparison


def get_resource_usage_by_campus():
    """Bookings per resource TYPE, per campus, as a nested dict:
        {"Cape Town": {"Lab": 4, "Projector": 2}, "Durban": {...}, ...}
    A resource type with no bookings still appears (with 0), and a campus
    with no resources still appears (with an empty dict)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT campuses.name AS campus_name, resources.resource_type,
                  COUNT(bookings.booking_id) AS booking_count
           FROM campuses
           LEFT JOIN resources ON resources.campus_id = campuses.campus_id
           LEFT JOIN bookings ON bookings.resource_id = resources.resource_id
           GROUP BY campuses.campus_id, resources.resource_type
           ORDER BY campuses.campus_id"""
    )
    rows = cursor.fetchall()
    conn.close()

    usage = {}
    for row in rows:
        by_type = usage.setdefault(row["campus_name"], {})   # make sure every campus has an entry
        if row["resource_type"] is None:
            continue                                         # campus with no resources at all
        # .title() so "lab" and "Lab" count as the same type
        resource_type = row["resource_type"].strip().title()
        by_type[resource_type] = by_type.get(resource_type, 0) + row["booking_count"]
    return usage


def compare_resource_types(usage):
    """Use set maths on the resource types each campus offers.
    Returns (shared, unique):
        shared -> a set of types that EVERY campus offers
        unique -> {campus name: set of types only that campus offers}"""
    types_by_campus = {campus: set(by_type) for campus, by_type in usage.items()}   # dict of sets
    if not types_by_campus:
        return set(), {}

    shared = set.intersection(*types_by_campus.values())

    unique = {}
    for campus, types in types_by_campus.items():
        offered_elsewhere = set()
        for other_campus, other_types in types_by_campus.items():
            if other_campus != campus:
                offered_elsewhere |= other_types             # set union
        unique[campus] = types - offered_elsewhere           # set difference
    return shared, unique


def summarise_rule_impact(comparison):
    """Plain-English sentences linking the numbers to the campus rules that
    produced them - the "differences resulting from campus-specific rules"
    part of section 7.2. Returns a list of strings."""
    with_bookings = [c for c in comparison if c["total_bookings"] > 0]
    if not with_bookings:
        return ["No bookings yet - rule differences will show up here once bookings are made."]

    insights = []

    busiest = max(with_bookings, key=lambda c: c["total_bookings"])
    insights.append(f"Busiest campus: {busiest['name']} ({busiest['total_bookings']} bookings, {busiest['policy']}).")

    longest_avg = max(with_bookings, key=lambda c: c["avg_duration"])
    cap_note = "no duration cap" if longest_avg["max_duration_minutes"] == 0 else f"{longest_avg['max_duration_minutes']} min cap"
    insights.append(
        f"Longest average booking: {longest_avg['name']} ({round(longest_avg['avg_duration'])} min, {cap_note})."
    )

    for c in with_bookings:
        if c["cap_usage_percent"] is not None and c["cap_usage_percent"] >= 75:
            insights.append(
                f"{c['name']}'s bookings average {c['cap_usage_percent']}% of its "
                f"{c['max_duration_minutes']}-minute cap - the cap is shaping how long people book for."
            )

    most_cancelled = max(with_bookings, key=lambda c: c["cancelled_bookings"])
    if most_cancelled["cancelled_bookings"] > 0:
        note = " (priority access is on here, so overrides add to this)" if most_cancelled["priority_override"] else ""
        insights.append(f"Most cancellations: {most_cancelled['name']} ({most_cancelled['cancelled_bookings']}){note}.")

    return insights
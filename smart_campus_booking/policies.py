"""
policies.py
Campus booking rules, kept completely separate from the core booking logic
(Programming 512, section 5.2 - "booking rules are separated from core
system logic using functions or classes").

How it's put together:
  - Each individual rule is its own small function (max_duration_rule,
    operating_hours_rule). It takes a policy + a requested booking and
    returns an error message if the rule is broken, or None if it's fine.
  - BOOKING_RULES is just a list of those functions. create_booking() in
    database.py loops over it without knowing or caring what's in it.
  - BookingPolicy is an object that holds ONE campus's rule values.

So adding things later needs minimal changes:
  - A new campus       -> insert a row in the campuses table. No code changes.
  - A new kind of rule -> write one function below and add it to BOOKING_RULES.
    create_booking() itself doesn't change at all.
"""

# How much warning a lecturer must get before an admin's priority booking
# is allowed to bump their booking (only applies at campuses with the
# priority-access rule switched on).
OVERRIDE_NOTICE_HOURS = 24

# How far ahead a booking can be made (stops nonsense like a booking in year 9999).
MAX_ADVANCE_DAYS = 365


# ---------------------------------------------------------------------------
# INDIVIDUAL RULES - one function per rule
# ---------------------------------------------------------------------------

def max_duration_rule(policy, start_minutes, duration_minutes):
    """Rule: a single booking can't be longer than the campus's cap.
    A cap of 0 means this campus has no limit."""
    if policy.max_duration_minutes > 0 and duration_minutes > policy.max_duration_minutes:
        return f"This campus's max booking duration is {policy.max_duration_minutes} minutes."
    return None


def operating_hours_rule(policy, start_minutes, duration_minutes):
    """Rule: the whole booking (start AND end) must fall inside the
    campus's opening hours."""
    end_minutes = start_minutes + duration_minutes
    if start_minutes < policy.open_hour * 60 or end_minutes > policy.close_hour * 60:
        return f"Bookings must fall within {policy.open_hour}:00 - {policy.close_hour}:00."
    return None


# The rules that get checked, in this order, for every booking.
# To add a new rule: write a function like the two above and add it here.
BOOKING_RULES = [max_duration_rule, operating_hours_rule]


# ---------------------------------------------------------------------------
# THE POLICY OBJECT
# ---------------------------------------------------------------------------

class BookingPolicy:
    """Holds one campus's booking rules. The values are private (single
    underscore) and only readable through the properties below - nothing
    outside this class can accidentally change a campus's rules halfway
    through a booking check (encapsulation)."""

    def __init__(self, campus_name, max_duration_minutes, open_hour, close_hour, priority_override):
        self._campus_name = campus_name
        self._max_duration_minutes = max_duration_minutes
        self._open_hour = open_hour
        self._close_hour = close_hour
        self._priority_override = bool(priority_override)

    @classmethod
    def from_campus(cls, campus_row):
        """Build a policy straight from a row of the campuses table."""
        return cls(
            campus_row["name"],
            campus_row["max_duration_minutes"],
            campus_row["open_hour"],
            campus_row["close_hour"],
            campus_row["priority_override"],
        )

    # read-only access to the private values
    @property
    def campus_name(self):
        return self._campus_name

    @property
    def max_duration_minutes(self):
        return self._max_duration_minutes

    @property
    def open_hour(self):
        return self._open_hour

    @property
    def close_hour(self):
        return self._close_hour

    @property
    def priority_override(self):
        return self._priority_override

    def check_booking(self, start_minutes, duration_minutes):
        """Run the requested booking past every rule in BOOKING_RULES.
        Returns the first error message it finds, or None if the booking
        is allowed under this campus's policy."""
        for rule in BOOKING_RULES:
            problem = rule(self, start_minutes, duration_minutes)
            if problem:
                return problem
        return None

    def allows_override(self, requesting_role):
        """Can this role bump an existing booking at this campus? Only
        admins/operators, and only where the campus has priority access."""
        return self._priority_override and requesting_role in ("admin", "operator")

    def short_summary(self):
        """One-line version of the policy, e.g. for the operator's report."""
        cap = f"max {self._max_duration_minutes} min" if self._max_duration_minutes > 0 else "no duration cap"
        text = f"{cap}, {self._open_hour}:00-{self._close_hour}:00"
        if self._priority_override:
            text += ", priority access"
        return text

    def describe(self):
        """Full multi-line description, shown to lecturers so they can see
        exactly which rules are in effect for the campus they've selected
        (brief section 5.1 - the active policy must be clearly indicated)."""
        if self._max_duration_minutes > 0:
            duration_line = f"Maximum {self._max_duration_minutes} minutes per booking"
        else:
            duration_line = "No maximum booking duration"
        lines = [
            f"Booking policy in effect - {self._campus_name}",
            f"  - {duration_line}",
            f"  - Bookings only between {self._open_hour}:00 and {self._close_hour}:00",
        ]
        if self._priority_override:
            lines.append(
                f"  - Priority access: an admin booking can override yours with "
                f"{OVERRIDE_NOTICE_HOURS}+ hours' notice"
            )
        return "\n".join(lines)
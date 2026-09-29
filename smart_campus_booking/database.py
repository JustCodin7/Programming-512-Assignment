"""
database.py
Handles all SQLite setup, queries, and business rules for the
Smart Campus Resource Booking System (Programming 512).

Every function opens its own connection and closes it before returning,
and every query uses '?' placeholders instead of building SQL strings
manually - this is what protects the app against SQL injection.
"""

import sqlite3
import datetime
import os
import re

from policies import BookingPolicy, OVERRIDE_NOTICE_HOURS, MAX_ADVANCE_DAYS

# Store the database file next to this script, not wherever the terminal
# happens to be pointed - avoids ever accidentally creating/reading a
# second, empty database file in the wrong folder.
DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "campus_booking.db")


def get_connection():
    """Open a connection with foreign keys enforced and named-column access."""
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row  # lets us do row["username"] instead of row[1]
    return conn


def initialize_database():
    """Create all tables if they don't exist yet, and seed the three campuses."""
    conn = get_connection()
    cursor = conn.cursor()

    # USERS - one table for all three roles; 'role' decides which class
    # (Lecturer / CampusAdministrator / SystemOperator) wraps it in Python.
    # Passwords are never stored in plain text - only a salted hash.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('lecturer', 'admin', 'operator')),
            full_name TEXT NOT NULL,
            campus_id INTEGER,
            FOREIGN KEY (campus_id) REFERENCES campuses (campus_id)
        )
    """)

    # CAMPUSES - each row carries its own booking policy values, so adding
    # a new campus with different rules never requires changing any code,
    # just inserting a new row (see _seed_campuses below). The rules
    # themselves (max duration, operating hours, priority access) are
    # enforced by the BookingPolicy class and rule functions in policies.py,
    # kept separate from this file's booking logic (brief section 5.2).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS campuses (
            campus_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            max_duration_minutes INTEGER NOT NULL,   -- 0 means "no cap"
            open_hour INTEGER NOT NULL,
            close_hour INTEGER NOT NULL,
            priority_override INTEGER NOT NULL DEFAULT 0
        )
    """)

    # RESOURCES - unique resource_code stops duplicate registration at the
    # database level, not just in the GUI.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resources (
            resource_id INTEGER PRIMARY KEY AUTOINCREMENT,
            campus_id INTEGER NOT NULL,
            resource_code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'available' CHECK (status IN ('available', 'unavailable')),
            FOREIGN KEY (campus_id) REFERENCES campuses (campus_id)
        )
    """)

    # BOOKINGS - links a lecturer + resource + campus to a date/time/duration.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_id INTEGER NOT NULL,
            lecturer_id INTEGER NOT NULL,
            campus_id INTEGER NOT NULL,
            booking_date TEXT NOT NULL,        -- 'YYYY-MM-DD'
            start_time TEXT NOT NULL,          -- 'HH:MM' (24hr)
            duration_minutes INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'cancelled')),
            FOREIGN KEY (resource_id) REFERENCES resources (resource_id),
            FOREIGN KEY (lecturer_id) REFERENCES users (user_id),
            FOREIGN KEY (campus_id) REFERENCES campuses (campus_id)
        )
    """)

    conn.commit()
    _seed_campuses(cursor, conn)
    first_run = _seed_demo_users(cursor, conn)
    conn.close()

    # Sample resources + bookings are only added on the very first run (when
    # the demo accounts were just created), so nothing is ever duplicated and
    # nothing an admin later deletes comes back.
    if first_run:
        _seed_sample_data()


def _seed_demo_users(cursor, conn):
    """Create one demo account per role (only once) so the app is fully
    testable the moment it's unzipped, without needing to manually poke
    the database. The GUI's own registration form only ever creates
    lecturer accounts on purpose (see open_register_window in gui.py) -
    admin/operator accounts aren't meant to be something anyone can just
    sign up for, so these demo accounts (one lecturer, one administrator
    per campus, one operator) are the only way to reach those roles from
    a fresh database."""
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] > 0:
        return False  # already seeded - don't duplicate on every run

    from auth import hash_password

    # campus_id 1 = Cape Town, 2 = Durban, 3 = Johannesburg (see _seed_campuses)
    demo_accounts = [
        ("lecturer1", "Password123", "lecturer", "Demo Lecturer", 1),
        # one administrator per campus (brief 3.2: an admin manages ONE
        # specific campus) - admin3 is the only one who sees the priority
        # booking tool, because only Johannesburg has that rule switched on
        ("admin1",    "Password123", "admin",    "Demo Administrator (Cape Town)", 1),
        ("admin2",    "Password123", "admin",    "Demo Administrator (Durban)", 2),
        ("admin3",    "Password123", "admin",    "Demo Administrator (Johannesburg)", 3),
        ("operator1", "Password123", "operator", "Demo System Operator", None),
    ]
    for username, password, role, full_name, campus_id in demo_accounts:
        password_hash, salt = hash_password(password)
        cursor.execute(
            """INSERT INTO users (username, password_hash, salt, role, full_name, campus_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (username, password_hash, salt, role, full_name, campus_id),
        )
    conn.commit()
    return True


def _seed_sample_data():
    """Give a brand-new database some realistic starting data (resources at
    all three campuses, plus a few bookings) so every screen and report has
    something to show straight away.

    Everything goes through add_resource() and create_booking(), i.e. the
    same validation and campus booking rules as real use, so the sample data
    can never break a rule. Booking dates are worked out from today's date,
    so they are always in the future however long after this was written
    the app is first run."""
    # (campus_id, code, name, type) - the types deliberately overlap between
    # campuses (Lab / Projector / Room) but not completely (Equipment only
    # exists in Cape Town + Durban, Auditorium only in Johannesburg), which
    # is what the operator's "offered at every campus / only at ..."
    # comparison shows off.
    resources = [
        (1, "CT-LAB-01",   "Computer Lab A",          "Lab"),
        (1, "CT-PROJ-01",  "Portable Projector 1",    "Projector"),
        (1, "CT-ROOM-01",  "Seminar Room 1A",         "Room"),
        (1, "CT-EQ-01",    "Video Camera Kit",        "Equipment"),
        (2, "DBN-LAB-01",  "Computer Lab B",          "Lab"),
        (2, "DBN-PROJ-01", "Ceiling Projector, Room 4", "Projector"),
        (2, "DBN-ROOM-01", "Seminar Room 2B",         "Room"),
        (2, "DBN-EQ-01",   "Presentation Kit (mic + screen)", "Equipment"),
        (3, "JHB-LAB-01",  "Computer Lab C",          "Lab"),
        (3, "JHB-PROJ-01", "Portable Projector 2",    "Projector"),
        (3, "JHB-ROOM-01", "Boardroom",               "Room"),
        (3, "JHB-AUD-01",  "Main Auditorium",         "Auditorium"),
    ]
    for campus_id, code, name, resource_type in resources:
        add_resource(campus_id, code, name, resource_type)

    conn = get_connection()
    ids = {r["username"]: r["user_id"] for r in conn.execute("SELECT user_id, username FROM users")}
    codes = {r["resource_code"]: r["resource_id"] for r in conn.execute("SELECT resource_id, resource_code FROM resources")}
    conn.close()

    today = datetime.date.today()
    day = lambda n: (today + datetime.timedelta(days=n)).isoformat()

    # (resource code, campus_id, days from today, start, minutes, booked by, role)
    bookings = [
        ("CT-LAB-01",   1, 3,  "09:00", 90,  "lecturer1", "lecturer"),
        ("CT-PROJ-01",  1, 3,  "13:00", 60,  "lecturer1", "lecturer"),
        ("CT-LAB-01",   1, 5,  "10:00", 120, "lecturer1", "lecturer"),
        ("DBN-ROOM-01", 2, 4,  "10:00", 150, "lecturer1", "lecturer"),
        ("DBN-LAB-01",  2, 6,  "09:30", 180, "lecturer1", "lecturer"),
        ("JHB-AUD-01",  3, 7,  "08:00", 300, "lecturer1", "lecturer"),
        ("JHB-LAB-01",  3, 9,  "14:00", 240, "lecturer1", "lecturer"),
        ("JHB-ROOM-01", 3, 10, "11:00", 60,  "admin3",     "admin"),
    ]
    for code, campus_id, offset, start, minutes, username, role in bookings:
        create_booking(codes[code], ids[username], campus_id, day(offset), start, minutes, role)

    # A little booking HISTORY, so "past bookings" has something to show on a
    # brand-new database. create_booking() (rightly) refuses dates in the
    # past, so these two are inserted directly - they still respect every
    # campus rule (hours and max duration).
    history = [
        ("CT-LAB-01",   1, -3, "09:00", 60),
        ("DBN-PROJ-01", 2, -1, "11:00", 90),
    ]
    conn = get_connection()
    for code, campus_id, offset, start, minutes in history:
        conn.execute(
            """INSERT INTO bookings (resource_id, lecturer_id, campus_id, booking_date, start_time, duration_minutes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (codes[code], ids["lecturer1"], campus_id, day(offset), start, minutes),
        )
    conn.commit()
    conn.close()

    # one cancelled booking, so the cancellation figures in the reports
    # aren't all zero
    create_booking(codes["CT-EQ-01"], ids["lecturer1"], 1, day(12), "15:00", 45, "lecturer")
    conn = get_connection()
    booking_id = conn.execute(
        "SELECT booking_id FROM bookings WHERE resource_id = ? AND booking_date = ?",
        (codes["CT-EQ-01"], day(12)),
    ).fetchone()["booking_id"]
    conn.close()
    cancel_booking(booking_id, ids["lecturer1"])

    # one resource marked unavailable, so the availability chart and the
    # "hidden from lecturers" behaviour can be seen
    set_resource_status(codes["JHB-PROJ-01"], 3, "unavailable")


def _seed_campuses(cursor, conn):
    """Insert the three campuses with their agreed policies (only once)."""
    cursor.execute("SELECT COUNT(*) FROM campuses")
    if cursor.fetchone()[0] > 0:
        return  # already seeded - don't duplicate on every run

    campuses = [
        ("Cape Town",     120, 8, 18, 0),
        ("Durban",        180, 9, 16, 0),
        ("Johannesburg",    0, 7, 20, 1),  # 0 duration = no cap, priority_override flag set
    ]
    cursor.executemany(
        """INSERT INTO campuses
           (name, max_duration_minutes, open_hour, close_hour, priority_override)
           VALUES (?, ?, ?, ?, ?)""",
        campuses,
    )
    conn.commit()


# ---------------------------------------------------------------------------
# USER ACCOUNTS
# ---------------------------------------------------------------------------

def create_user(username, password, role, full_name, campus_id=None):
    """Create a new user account with a securely hashed+salted password.
    Returns (True, message) on success or (False, message) on failure -
    e.g. if the username is already taken."""
    from auth import hash_password

    # --- validate everything first, so bad input gets a clear message and
    # never reaches the database ---
    username = (username or "").strip()
    full_name = (full_name or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,30}", username):
        return False, "Username must be 3-30 characters: letters, numbers, dots, hyphens or underscores (no spaces)."
    if not password or len(password) < 6:
        return False, "Password must be at least 6 characters long."
    if len(password) > 100:
        return False, "Password can't be longer than 100 characters."
    if not 2 <= len(full_name) <= 80:
        return False, "Full name must be between 2 and 80 characters."
    if role not in ("lecturer", "admin", "operator"):
        return False, "Invalid account role."
    if role != "operator" and get_campus(campus_id) is None:
        return False, "Please choose a valid campus."

    password_hash, salt = hash_password(password)

    conn = get_connection()
    cursor = conn.cursor()
    try:
        # usernames are treated as case-insensitive, so "Bob" and "bob"
        # can't exist as two different accounts
        cursor.execute("SELECT 1 FROM users WHERE LOWER(username) = LOWER(?)", (username,))
        if cursor.fetchone():
            return False, "That username is already taken."
        cursor.execute(
            """INSERT INTO users (username, password_hash, salt, role, full_name, campus_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (username, password_hash, salt, role, full_name, campus_id),
        )
        conn.commit()
        return True, "Account created successfully."
    except sqlite3.IntegrityError:
        return False, "That username is already taken."
    finally:
        conn.close()


def get_all_campuses():
    """Return every campus - used to populate the campus dropdown at registration."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM campuses")
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_campus(campus_id):
    """Fetch one campus row, including its booking policy values."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM campuses WHERE campus_id = ?", (campus_id,))
    row = cursor.fetchone()
    conn.close()
    return row


# ---------------------------------------------------------------------------
# RESOURCES
# ---------------------------------------------------------------------------

def add_resource(campus_id, resource_code, name, resource_type):
    """Add a new resource to a campus. Returns (True, message) or (False, message).
    The code is tidied up to upper-case so "ct-lab-1" and "CT-LAB-1" can't
    both exist as different resources."""
    resource_code = (resource_code or "").strip().upper()
    name = (name or "").strip()
    resource_type = (resource_type or "").strip().title()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{1,19}", resource_code):
        return False, "Resource code must be 2-20 characters: letters, numbers, hyphens or underscores (e.g. CT-LAB-02)."
    if not 1 <= len(name) <= 60:
        return False, "Resource name must be between 1 and 60 characters."
    if not 1 <= len(resource_type) <= 30:
        return False, "Resource type must be between 1 and 30 characters."
    if get_campus(campus_id) is None:
        return False, "Campus not found."

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO resources (campus_id, resource_code, name, resource_type)
               VALUES (?, ?, ?, ?)""",
            (campus_id, resource_code, name, resource_type),
        )
        conn.commit()
        return True, "Resource added successfully."
    except sqlite3.IntegrityError:
        return False, "A resource with that code already exists."
    finally:
        conn.close()


def get_resources_by_campus(campus_id):
    """Return only the AVAILABLE resources at a campus (for the Lecturer's booking list)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM resources WHERE campus_id = ? AND status = 'available'",
        (campus_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_all_resources_by_campus(campus_id):
    """Return every resource at a campus, available or not (for admin management)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM resources WHERE campus_id = ?", (campus_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_resource(resource_id):
    """Fetch one resource row by id (used to double-check its status before booking)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM resources WHERE resource_id = ?", (resource_id,))
    row = cursor.fetchone()
    conn.close()
    return row


def get_all_resources():
    """Every resource, across every campus (for the System Operator)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT resources.*, campuses.name AS campus_name
           FROM resources
           JOIN campuses ON resources.campus_id = campuses.campus_id"""
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def set_resource_status(resource_id, campus_id, status):
    """Mark a resource available/unavailable - only if it belongs to this admin's
    own campus. We never hard-delete a resource, since that would break the
    booking history and reports tied to it; 'removing' a resource means
    hiding it from lecturers, not erasing its records."""
    if status not in ("available", "unavailable"):
        return False, "Status must be 'available' or 'unavailable'."
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE resources SET status = ? WHERE resource_id = ? AND campus_id = ?",
        (status, resource_id, campus_id),
    )
    conn.commit()
    rows_changed = cursor.rowcount
    conn.close()

    if rows_changed == 0:
        return False, "Resource not found at your campus."
    return True, f"Resource marked as {status}."


def delete_resource(resource_id, campus_id):
    """Permanently remove a resource - only if it belongs to this admin's
    own campus AND has no booking history at all (past or present). This
    is a genuine hard delete, unlike set_resource_status() above.

    We refuse to delete a resource that has any bookings, active or
    cancelled, because bookings.resource_id has a FOREIGN KEY pointing at
    it - deleting it anyway would either fail outright or silently break
    every report and booking-history record tied to it. In that case an
    admin should use set_resource_status() to mark it unavailable instead,
    which keeps the history intact but stops it being booked again.

    Returns (True, message) on a successful delete, or (False, message)
    explaining why it couldn't be deleted."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM bookings WHERE resource_id = ?", (resource_id,)
    )
    booking_count = cursor.fetchone()[0]
    if booking_count > 0:
        conn.close()
        return False, (
            f"Can't permanently remove this resource - it has {booking_count} "
            "booking(s) on record. Mark it unavailable instead to hide it "
            "without losing booking history."
        )

    cursor.execute(
        "DELETE FROM resources WHERE resource_id = ? AND campus_id = ?",
        (resource_id, campus_id),
    )
    conn.commit()
    rows_changed = cursor.rowcount
    conn.close()

    if rows_changed == 0:
        return False, "Resource not found at your campus."
    return True, "Resource permanently removed."


def update_resource(resource_id, campus_id, name, resource_type):
    """Update a resource's name and type - only if it belongs to this admin's
    own campus. The resource_code is left alone on purpose: it's the stable
    identifier other records (bookings, reports) implicitly rely on, so it
    shouldn't change after creation - only the descriptive details can."""
    name = (name or "").strip()
    resource_type = (resource_type or "").strip().title()
    if not 1 <= len(name) <= 60:
        return False, "Resource name must be between 1 and 60 characters."
    if not 1 <= len(resource_type) <= 30:
        return False, "Resource type must be between 1 and 30 characters."
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE resources SET name = ?, resource_type = ? WHERE resource_id = ? AND campus_id = ?",
        (name, resource_type, resource_id, campus_id),
    )
    conn.commit()
    rows_changed = cursor.rowcount
    conn.close()

    if rows_changed == 0:
        return False, "Resource not found at your campus."
    return True, "Resource updated successfully."


# ---------------------------------------------------------------------------
# BOOKINGS
# ---------------------------------------------------------------------------

def _time_to_minutes(time_str):
    """Turn '14:30' into 870 (minutes since midnight) so times are easy to compare.
    Raises ValueError for anything that isn't a real time of day (so "9:60"
    or "-1:30" are rejected instead of quietly turning into another time)."""
    hours, minutes = time_str.strip().split(":")
    hours, minutes = int(hours), int(minutes)
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        raise ValueError("time out of range")
    return hours * 60 + minutes


def is_slot_available(resource_id, booking_date, start_time, duration_minutes):
    """Check whether a resource is free for the requested date/time/duration,
    by comparing the new booking's time range against every existing active
    booking for that same resource on that same date."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT * FROM bookings
           WHERE resource_id = ? AND booking_date = ? AND status = 'active'""",
        (resource_id, booking_date),
    )
    existing_bookings = cursor.fetchall()
    conn.close()

    new_start = _time_to_minutes(start_time)
    new_end = new_start + duration_minutes

    for booking in existing_bookings:
        existing_start = _time_to_minutes(booking["start_time"])
        existing_end = existing_start + booking["duration_minutes"]

        # Two time ranges overlap if one starts before the other ends.
        if new_start < existing_end and existing_start < new_end:
            return False

    return True


def create_booking(resource_id, lecturer_id, campus_id, booking_date, start_time, duration_minutes, requesting_role="lecturer"):
    """Create a booking, but only after validating the input and checking
    it against the campus's own booking policy and existing bookings.

    At a campus with priority_override enabled (Johannesburg), an admin or
    operator's booking can bump an existing lecturer booking that overlaps
    it - but only if that existing booking starts more than 24 hours from
    now, so the lecturer isn't bumped with no notice. Regular lecturer
    bookings never get this override; they follow the normal overlap rule.

    Returns (True, message) or (False, message)."""

    if duration_minutes <= 0:
        return False, "Duration must be greater than 0 minutes."

    try:
        parsed_date = datetime.datetime.strptime(booking_date, "%Y-%m-%d")
        # Normalize to zero-padded form (e.g. "2026-8-7" -> "2026-08-07").
        # SQLite has no real date type - it sorts booking_date as plain text,
        # so an unpadded date would sort in the wrong position relative to
        # padded ones (e.g. "2026-08-7" sorts AFTER "2026-08-12" as text).
        booking_date = parsed_date.strftime("%Y-%m-%d")
    except ValueError:
        return False, "Date must be in YYYY-MM-DD format (e.g. 2026-10-01)."

    try:
        start_minutes = _time_to_minutes(start_time)
        # Same normalization for time, for the same text-sorting reason
        # (e.g. "9:00" would otherwise sort AFTER "10:00" as text).
        start_time = f"{start_minutes // 60:02d}:{start_minutes % 60:02d}"
    except (ValueError, AttributeError):
        return False, "Start time must be in HH:MM format (e.g. 14:30)."

    # No bookings in the past (they could never be cancelled either, since
    # only future bookings can be cancelled), and none absurdly far ahead.
    start_datetime = datetime.datetime.strptime(f"{booking_date} {start_time}", "%Y-%m-%d %H:%M")
    now = datetime.datetime.now()
    if start_datetime <= now:
        return False, "Bookings can't be made in the past - please choose a future date and time."
    if start_datetime > now + datetime.timedelta(days=MAX_ADVANCE_DAYS):
        return False, f"Bookings can only be made up to {MAX_ADVANCE_DAYS} days in advance."

    campus = get_campus(campus_id)
    if campus is None:
        return False, "Campus not found."

    # All of this campus's booking rules live in policies.py, not here -
    # this function just asks the policy object and doesn't need to know
    # what any individual rule actually is (brief section 5.2).
    policy = BookingPolicy.from_campus(campus)

    # A resource marked unavailable can't be booked, even if a caller
    # somehow has its resource_id - the Lecturer's list already filters
    # these out, but that's a GUI convenience, not a real guarantee.
    resource = get_resource(resource_id)
    if resource is None or resource["status"] != "available":
        return False, "This resource is not available for booking."

    # A booking is linked to the campus the lecturer selected (brief 4.3),
    # so the resource has to genuinely be at that campus.
    if resource["campus_id"] != campus_id:
        return False, "That resource doesn't belong to the selected campus."

    # Campus-specific rules (max duration, operating hours, and any rule
    # added to BOOKING_RULES in future) are all checked in one call.
    rule_violation = policy.check_booking(start_minutes, duration_minutes)
    if rule_violation:
        return False, rule_violation

    # No double-booking the same resource - unless this is a priority
    # override at a campus that allows it.
    if not is_slot_available(resource_id, booking_date, start_time, duration_minutes):
        if policy.allows_override(requesting_role):
            overridden, override_message = _override_conflicting_bookings(
                resource_id, booking_date, start_time, duration_minutes
            )
            if not overridden:
                return False, override_message
        else:
            return False, "This resource is already booked for an overlapping time."

    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO bookings (resource_id, lecturer_id, campus_id, booking_date, start_time, duration_minutes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (resource_id, lecturer_id, campus_id, booking_date, start_time, duration_minutes),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # e.g. the lecturer account doesn't exist. Without this, the error
        # would escape with the connection still open and the database
        # locked for every save after it.
        return False, "Couldn't save the booking - the lecturer or resource no longer exists."
    finally:
        conn.close()
    return True, "Booking created successfully."


def _override_conflicting_bookings(resource_id, booking_date, start_time, duration_minutes):
    """Cancel every active booking that overlaps the requested slot, but only
    if every single one of them starts more than 24 hours from now. If even
    one is too close, nothing is cancelled and the whole override is refused -
    it's all-or-nothing, so a lecturer is never partially bumped."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT * FROM bookings
           WHERE resource_id = ? AND booking_date = ? AND status = 'active'""",
        (resource_id, booking_date),
    )
    existing_bookings = cursor.fetchall()

    new_start = _time_to_minutes(start_time)
    new_end = new_start + duration_minutes

    overlapping = []
    for booking in existing_bookings:
        existing_start = _time_to_minutes(booking["start_time"])
        existing_end = existing_start + booking["duration_minutes"]
        if new_start < existing_end and existing_start < new_end:
            overlapping.append(booking)

    now = datetime.datetime.now()
    for booking in overlapping:
        booking_start = datetime.datetime.strptime(
            f"{booking['booking_date']} {booking['start_time']}", "%Y-%m-%d %H:%M"
        )
        if booking_start - now < datetime.timedelta(hours=OVERRIDE_NOTICE_HOURS):
            conn.close()
            return False, f"Cannot override: an existing booking starts within the next {OVERRIDE_NOTICE_HOURS} hours."

    for booking in overlapping:
        cursor.execute(
            "UPDATE bookings SET status = 'cancelled' WHERE booking_id = ?",
            (booking["booking_id"],),
        )
    conn.commit()
    conn.close()
    return True, ""


def get_bookings_by_lecturer(lecturer_id):
    """Return all bookings made by this lecturer, with the resource name and
    campus name attached. The campus matters because a lecturer can select
    and book at any campus (brief section 3.1), so their history needs to
    show WHICH campus each booking belongs to."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT bookings.*, resources.name AS resource_name, resources.resource_code,
                  campuses.name AS campus_name
           FROM bookings
           JOIN resources ON bookings.resource_id = resources.resource_id
           JOIN campuses ON bookings.campus_id = campuses.campus_id
           WHERE bookings.lecturer_id = ?
           ORDER BY bookings.booking_date, bookings.start_time""",
        (lecturer_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def cancel_booking(booking_id, lecturer_id):
    """Cancel a booking - only if it actually belongs to this lecturer, it's
    still active, AND it hasn't already happened. Checking lecturer_id in
    the WHERE clause (not just booking_id) stops one lecturer from
    cancelling someone else's booking, even if they guessed a valid
    booking ID. The brief specifically says lecturers can cancel FUTURE
    bookings (section 6.1) - cancelling something whose date/time has
    already passed doesn't really mean anything, so that's blocked here
    rather than left to the GUI to enforce."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """SELECT booking_date, start_time FROM bookings
           WHERE booking_id = ? AND lecturer_id = ? AND status = 'active'""",
        (booking_id, lecturer_id),
    )
    row = cursor.fetchone()
    if row is None:
        conn.close()
        return False, "Booking not found or already cancelled."

    booking_start = datetime.datetime.strptime(
        f"{row['booking_date']} {row['start_time']}", "%Y-%m-%d %H:%M"
    )
    if booking_start <= datetime.datetime.now():
        conn.close()
        return False, "Can't cancel a booking that's already started or passed."

    cursor.execute(
        """UPDATE bookings SET status = 'cancelled'
           WHERE booking_id = ? AND lecturer_id = ? AND status = 'active'""",
        (booking_id, lecturer_id),
    )
    conn.commit()
    rows_changed = cursor.rowcount
    conn.close()

    if rows_changed == 0:
        return False, "Booking not found or already cancelled."
    return True, "Booking cancelled."


def get_bookings_by_campus(campus_id):
    """Return every booking at a campus, with resource and lecturer names attached
    (for the Campus Administrator's view)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT bookings.*, resources.name AS resource_name, users.full_name AS lecturer_name
           FROM bookings
           JOIN resources ON bookings.resource_id = resources.resource_id
           JOIN users ON bookings.lecturer_id = users.user_id
           WHERE bookings.campus_id = ?
           ORDER BY bookings.booking_date, bookings.start_time""",
        (campus_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_all_bookings():
    """Every booking, across every campus (for the System Operator)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT bookings.*, resources.name AS resource_name,
                  users.full_name AS lecturer_name, campuses.name AS campus_name
           FROM bookings
           JOIN resources ON bookings.resource_id = resources.resource_id
           JOIN users ON bookings.lecturer_id = users.user_id
           JOIN campuses ON bookings.campus_id = campuses.campus_id
           ORDER BY campuses.name, bookings.booking_date"""
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# BOOKING STATE + LIVE AVAILABILITY (brief sections 6.1 and 6.2)
# ---------------------------------------------------------------------------

def booking_window(booking):
    """Return (start, end) as real datetime objects for a booking row."""
    start = datetime.datetime.strptime(
        f"{booking['booking_date']} {booking['start_time']}", "%Y-%m-%d %H:%M"
    )
    return start, start + datetime.timedelta(minutes=booking["duration_minutes"])


def booking_state(booking):
    """What a booking actually IS right now, which the raw 'status' column
    can't say on its own (status only knows 'active' or 'cancelled', so a
    booking from last month would still read 'active').

    Returns one of: 'Cancelled', 'Past', 'In progress', 'Upcoming'.
    'Upcoming' + 'In progress' together are the bookings still worth
    showing under "active bookings"; 'Past' is the booking history."""
    if booking["status"] == "cancelled":
        return "Cancelled"
    start, end = booking_window(booking)
    now = datetime.datetime.now()
    if end <= now:
        return "Past"
    if start <= now:
        return "In progress"
    return "Upcoming"


def get_resource_schedule(resource_id):
    """Every active booking for one resource that hasn't finished yet, soonest
    first - i.e. the slots a lecturer can NOT book. Each entry is a small dict
    (date / start / end / minutes / in_progress) ready for the GUI to show."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT * FROM bookings
           WHERE resource_id = ? AND status = 'active' AND booking_date >= ?
           ORDER BY booking_date, start_time""",
        (resource_id, datetime.date.today().isoformat()),
    )
    rows = cursor.fetchall()
    conn.close()

    now = datetime.datetime.now()
    schedule = []
    for booking in rows:
        start, end = booking_window(booking)
        if end <= now:
            continue  # already over - nothing left to block
        schedule.append({
            "date": booking["booking_date"],
            "start": start.strftime("%H:%M"),
            "end": end.strftime("%H:%M"),
            "minutes": booking["duration_minutes"],
            "in_progress": start <= now,
        })
    return schedule


def get_resources_in_use_now(campus_id):
    """Which resources at this campus are being used at this very moment.
    Returns {resource_id: 'HH:MM' time it becomes free} - anything not in the
    dict is free right now. This is the 'real-time availability' the GUI
    shows next to each resource."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT * FROM bookings
           WHERE campus_id = ? AND status = 'active' AND booking_date = ?""",
        (campus_id, datetime.date.today().isoformat()),
    )
    rows = cursor.fetchall()
    conn.close()

    now = datetime.datetime.now()
    in_use = {}
    for booking in rows:
        start, end = booking_window(booking)
        if start <= now < end:
            in_use[booking["resource_id"]] = end.strftime("%H:%M")
    return in_use


# ---------------------------------------------------------------------------
# REPORTS
# ---------------------------------------------------------------------------

def get_campus_report(campus_id):
    """Total bookings, most frequently used resources, and average duration
    for one campus (for the Campus Administrator - brief section 7.1)."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM bookings WHERE campus_id = ?", (campus_id,))
    total_bookings = cursor.fetchone()[0]

    # the brief says "most frequently used resources" (plural), so this
    # returns the top 3 as a list of (name, booking_count) pairs
    cursor.execute(
        """SELECT resources.name, COUNT(*) as booking_count
           FROM bookings
           JOIN resources ON bookings.resource_id = resources.resource_id
           WHERE bookings.campus_id = ?
           GROUP BY bookings.resource_id
           ORDER BY booking_count DESC
           LIMIT 3""",
        (campus_id,),
    )
    top_resources = [(row["name"], row["booking_count"]) for row in cursor.fetchall()]

    cursor.execute("SELECT AVG(duration_minutes) FROM bookings WHERE campus_id = ?", (campus_id,))
    avg_duration = cursor.fetchone()[0]

    # A Python set only keeps each value once, so putting every booking's
    # lecturer_id into one gives the number of DIFFERENT lecturers who have
    # booked here, not just the number of bookings.
    cursor.execute("SELECT lecturer_id FROM bookings WHERE campus_id = ?", (campus_id,))
    unique_lecturers = len({row["lecturer_id"] for row in cursor.fetchall()})

    conn.close()
    return {
        "total_bookings": total_bookings,
        "most_used_resource": top_resources[0][0] if top_resources else "No bookings yet",
        "top_resources": top_resources,
        "avg_duration": round(avg_duration, 1) if avg_duration else 0,
        "unique_lecturers": unique_lecturers,
    }


def get_cross_campus_report():
    """Compare booking activity across every campus, even ones with zero
    bookings (for the System Operator). Uses LEFT JOIN instead of a plain
    JOIN so a campus with no bookings still appears in the results with a
    count of 0, rather than being dropped entirely."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT campuses.name,
                  COUNT(bookings.booking_id) AS total_bookings,
                  AVG(bookings.duration_minutes) AS avg_duration
           FROM campuses
           LEFT JOIN bookings ON campuses.campus_id = bookings.campus_id
           GROUP BY campuses.campus_id"""
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


if __name__ == "__main__":
    # Only runs when this file is executed directly (python database.py),
    # not when another file imports functions from it.
    initialize_database()
    print("Database initialized successfully.")
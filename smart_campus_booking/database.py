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
    # just inserting a new row (see _seed_campuses below).
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
    conn.close()


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
    password_hash, salt = hash_password(password)

    conn = get_connection()
    cursor = conn.cursor()
    try:
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
    """Add a new resource to a campus. Returns (True, message) or (False, message)."""
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


# ---------------------------------------------------------------------------
# BOOKINGS
# ---------------------------------------------------------------------------

def _time_to_minutes(time_str):
    """Turn '14:30' into 870 (minutes since midnight) so times are easy to compare."""
    hours, minutes = time_str.split(":")
    return int(hours) * 60 + int(minutes)


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


def create_booking(resource_id, lecturer_id, campus_id, booking_date, start_time, duration_minutes):
    """Create a booking, but only after validating the input and checking
    it against the campus's own booking policy and existing bookings.
    Returns (True, message) or (False, message)."""

    if duration_minutes <= 0:
        return False, "Duration must be greater than 0 minutes."

    try:
        datetime.datetime.strptime(booking_date, "%Y-%m-%d")
    except ValueError:
        return False, "Date must be in YYYY-MM-DD format (e.g. 2026-10-01)."

    try:
        start_minutes = _time_to_minutes(start_time)
    except (ValueError, AttributeError):
        return False, "Start time must be in HH:MM format (e.g. 14:30)."

    campus = get_campus(campus_id)

    # Campus-specific rule: maximum booking duration (0 = no cap, e.g. Johannesburg).
    if campus["max_duration_minutes"] > 0 and duration_minutes > campus["max_duration_minutes"]:
        return False, f"This campus's max booking duration is {campus['max_duration_minutes']} minutes."

    # Campus-specific rule: booking must fall entirely within operating hours.
    end_minutes = start_minutes + duration_minutes
    open_minutes = campus["open_hour"] * 60
    close_minutes = campus["close_hour"] * 60

    if start_minutes < open_minutes or end_minutes > close_minutes:
        return False, f"Bookings must fall within {campus['open_hour']}:00 - {campus['close_hour']}:00."

    # No double-booking the same resource.
    if not is_slot_available(resource_id, booking_date, start_time, duration_minutes):
        return False, "This resource is already booked for an overlapping time."

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO bookings (resource_id, lecturer_id, campus_id, booking_date, start_time, duration_minutes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (resource_id, lecturer_id, campus_id, booking_date, start_time, duration_minutes),
    )
    conn.commit()
    conn.close()
    return True, "Booking created successfully."


def get_bookings_by_lecturer(lecturer_id):
    """Return all bookings made by this lecturer, with the resource name attached."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT bookings.*, resources.name AS resource_name, resources.resource_code
           FROM bookings
           JOIN resources ON bookings.resource_id = resources.resource_id
           WHERE bookings.lecturer_id = ?
           ORDER BY bookings.booking_date, bookings.start_time""",
        (lecturer_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def cancel_booking(booking_id, lecturer_id):
    """Cancel a booking - only if it actually belongs to this lecturer.
    Checking lecturer_id in the WHERE clause (not just booking_id) stops
    one lecturer from cancelling someone else's booking, even if they
    guessed a valid booking ID."""
    conn = get_connection()
    cursor = conn.cursor()
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
# REPORTS
# ---------------------------------------------------------------------------

def get_campus_report(campus_id):
    """Total bookings, most-used resource, and average duration for one campus
    (for the Campus Administrator)."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM bookings WHERE campus_id = ?", (campus_id,))
    total_bookings = cursor.fetchone()[0]

    cursor.execute(
        """SELECT resources.name, COUNT(*) as booking_count
           FROM bookings
           JOIN resources ON bookings.resource_id = resources.resource_id
           WHERE bookings.campus_id = ?
           GROUP BY bookings.resource_id
           ORDER BY booking_count DESC
           LIMIT 1""",
        (campus_id,),
    )
    most_used = cursor.fetchone()

    cursor.execute("SELECT AVG(duration_minutes) FROM bookings WHERE campus_id = ?", (campus_id,))
    avg_duration = cursor.fetchone()[0]

    conn.close()
    return {
        "total_bookings": total_bookings,
        "most_used_resource": most_used["name"] if most_used else "No bookings yet",
        "avg_duration": round(avg_duration, 1) if avg_duration else 0,
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
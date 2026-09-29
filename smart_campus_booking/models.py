"""
models.py
Defines the different user roles as classes.

OOP ideas used here (brief section 3):
  - Inheritance:   Lecturer / CampusAdministrator / SystemOperator all
                   inherit from the User base class.
  - Encapsulation: a user's campuses are private attributes (leading
                   underscore) that can only be read through properties and
                   only changed through select_campus(), which enforces
                   what each role is actually allowed to do.
  - Polymorphism:  every role answers role_name() and
                   can_select_any_campus() in its own way.
"""


class User:
    """Base class - things every logged-in user has, no matter their role."""
    def __init__(self, user_id, username, full_name, campus_id):
        self.user_id = user_id
        self.username = username
        self.full_name = full_name
        # The campus the account was registered under ("home"), and the
        # campus the user is currently working at ("active"). They start out
        # the same; select_campus() is the only way the active one changes.
        self._home_campus_id = campus_id
        self._active_campus_id = campus_id

    @property
    def campus_id(self):
        """The campus this user is currently working at (read-only)."""
        return self._active_campus_id

    @property
    def home_campus_id(self):
        """The campus this account was registered under (read-only)."""
        return self._home_campus_id

    def role_name(self):
        return "User"

    def can_select_any_campus(self):
        """Whether this role may choose which campus to work at. Off by
        default - roles have to opt in."""
        return False

    def select_campus(self, campus_id):
        """Set the campus this user is working at. Roles that aren't allowed
        to roam between campuses can only 'select' their own one."""
        if not self.can_select_any_campus() and campus_id != self._home_campus_id:
            raise PermissionError(f"A {self.role_name()} can only work at their own campus.")
        self._active_campus_id = campus_id


class Lecturer(User):
    """A Lecturer can book resources and view their own bookings. They can
    also choose which campus to work at (brief section 3.1: "select a
    campus and view available resources") - e.g. to book a projector at a
    different campus for a joint event."""
    def role_name(self):
        return "Lecturer"

    def can_select_any_campus(self):
        return True


class CampusAdministrator(User):
    """A Campus Administrator manages resources at their campus. Tied to
    one specific campus (brief section 3.2), so they can't switch."""
    def role_name(self):
        return "Campus Administrator"


class SystemOperator(User):
    """A System Operator has full access across all campuses, so they have
    no single campus to select (campus_id stays None)."""
    def role_name(self):
        return "System Operator"


def create_user_object(db_row):
    """Take a row from the users table and turn it into the correct
    class, based on the role stored in the database."""
    role_map = {
        "lecturer": Lecturer,
        "admin": CampusAdministrator,
        "operator": SystemOperator,
    }
    user_class = role_map[db_row["role"]]
    return user_class(
        user_id=db_row["user_id"],
        username=db_row["username"],
        full_name=db_row["full_name"],
        campus_id=db_row["campus_id"],
    )
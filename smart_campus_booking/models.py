"""
models.py
Defines the different user roles as classes.
"""

class User:
    """Base class - things every logged-in user has, no matter their role."""
    def __init__(self, user_id, username, full_name, campus_id):
        self.user_id = user_id
        self.username = username
        self.full_name = full_name
        self.campus_id = campus_id

    def role_name(self):
        return "User"


class Lecturer(User):
    """A Lecturer can book resources and view their own bookings."""
    def role_name(self):
        return "Lecturer"


class CampusAdministrator(User):
    """A Campus Administrator manages resources at their campus."""
    def role_name(self):
        return "Campus Administrator"


class SystemOperator(User):
    """A System Operator has full access across all campuses."""
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
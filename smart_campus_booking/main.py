"""
main.py
Entry point for the Smart Campus Resource Booking System (Programming 512).

This is the file to run to start the application:
    python main.py

It doesn't contain any GUI/logic itself - it just makes sure the database
exists (creating and seeding it on the very first run) and then hands off
to gui.py, which builds and runs the actual application window.
"""

from database import initialize_database
from gui import run_app

if __name__ == "__main__":
    initialize_database()
    run_app()
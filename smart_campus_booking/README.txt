SMART CAMPUS RESOURCE BOOKING SYSTEM
Programming 512 Assignment
======================================================================

Name and surname:         Pride Pafoule
Student ITS number:       402603157
Qualification:            BSCIT
Year of study/semester:   1st year/ semester 2


STEP 1 - WHAT YOU NEED
----------------------------------------------------------------------
- Python 3.8 or newer
- Tkinter, which is what the whole interface is built with. It comes
  with the normal Python installer on Windows and macOS. On Linux you
  may need to install it once: sudo apt install python3-tk
- SQLite, which is built into Python
 
That is everything. The program only uses Python's standard library,
so there is nothing to download with pip.
 
The app is designed around the Segoe UI and Cambria fonts, which every
Windows PC has. On other systems Tkinter swaps in a similar font, so
everything still works and only the styling changes a little.
 
 
STEP 2 - HOW TO RUN IT
----------------------------------------------------------------------
Open a terminal in the project folder and type:
 
    python main.py
 
The first time you run it, the program creates a file called
campus_booking.db in the same folder and fills it with starting data:
 
- the three campuses and their booking rules
- five demo accounts (listed below)
- 12 sample resources and a handful of sample bookings (upcoming,
  past and cancelled), so nothing looks empty when you open it
 
Everything is saved in the database, so your data is still there the
next time you open the program. To start again from scratch, close the
program, delete campus_booking.db, and run main.py again.
 
 
LOGGING IN
----------------------------------------------------------------------
    Role                                 Username     Password
    -----------------------------------  -----------  ------------
    Lecturer                             lecturer1    Password123
    Campus Administrator (Cape Town)     admin1       Password123
    Campus Administrator (Durban)        admin2       Password123
    Campus Administrator (Johannesburg)  admin3       Password123
    System Operator                      operator1    Password123
 
Anyone can create a lecturer account with the "Register New Account"
button on the login screen. I deliberately did not allow administrator
or operator accounts to be created that way, because those roles have
more power and should not be something anyone can sign up for. The demo
accounts above are the way in for those two roles.
 
There is one administrator for each campus, because an administrator
only manages their own campus. Only admin3 (Johannesburg) can see the
priority booking tool, since Johannesburg is the only campus with that
rule.
 
 
THE THREE CAMPUSES AND THEIR RULES
----------------------------------------------------------------------
Each campus has its own booking rules, and the system applies them
automatically to whichever campus is selected.
 
    Campus          Longest booking   Opening hours    Priority access
    --------------  ----------------  ---------------  ---------------
    Cape Town       120 minutes       08:00 to 18:00   No
    Durban          180 minutes       09:00 to 16:00   No
    Johannesburg    No limit          07:00 to 20:00   Yes
 
Priority access at Johannesburg means an administrator's booking can
replace a lecturer's booking that overlaps it, but only if the
lecturer's booking starts more than 24 hours from now, so nobody gets
bumped at the last minute.
 
The rules that apply are shown to the lecturer when they pick a campus,
and again under the resource list on their dashboard.
 
 
WHAT EACH ROLE CAN DO
----------------------------------------------------------------------
LECTURER
- Register and log in from the GUI.
- Choose a campus after logging in (and change it later with the
  "Switch Campus" button). The campus's booking rules are shown.
- See the campus's available resources, with a "Right now" column that
  says Free or In use until a time.
- Click a resource to see its Booked Slots (the times it is already
  taken), then book it by choosing a date, start time and duration.
- Look through their own bookings and filter them by All, Active, Past
  or Cancelled. Each booking is labelled Upcoming, In progress, Past or
  Cancelled.
- Cancel a booking that has not started yet. Bookings in the past
  cannot be cancelled.
 
CAMPUS ADMINISTRATOR (tied to one campus)
- Add, update, and remove resources. A resource can also be marked
  unavailable, which hides it from lecturers without deleting it.
- A resource that has any booking history cannot be permanently
  removed, because that would break old bookings and reports. It has
  to be marked unavailable instead.
- See every booking at their campus.
- See a campus report with the total number of bookings, the most used
  resources, the average booking length and how many different
  lecturers have booked, plus a couple of charts.
- At a campus with priority access (Johannesburg), make a priority
  booking that can override a lecturer's booking.
 
SYSTEM OPERATOR (all campuses, view only)
- See every resource and every booking at every campus.
- Generate a comparison report showing resource usage per campus, which
  resource types every campus has and which only one campus has, and
  short sentences explaining how each campus's rules affected its
  bookings.
 
 
WHAT IS IN THE FOLDER
----------------------------------------------------------------------
main.py            starts the program (sets up the database, then
                   opens the GUI)
gui.py             every window: login, register, campus selection and
                   the three dashboards
database.py        the SQLite tables, queries and booking logic
policies.py        the campus booking rules, kept apart from the
                   booking logic
models.py          the user classes for the three roles
auth.py            password hashing and checking
reports.py         the cross-campus comparison reports
README.txt         this file
campus_booking.db  created automatically the first time you run the
                   program
 
 

 
 
A SUGGESTED WAY TO TRY IT OUT
----------------------------------------------------------------------
1. Log in as lecturer1 and pick Cape Town. Read the rules that appear,
   then click "Computer Lab A" and look at its Booked Slots.
2. Try to book it for 150 minutes (refused, because Cape Town's limit
   is 120). Then try a time that overlaps an existing booking
   (refused). Then book a free time (accepted).
3. Set the "Show" filter to Past to see the booking history, then
   cancel the booking you just made.
4. Click "Switch Campus" and choose Johannesburg. The rules and the
   resources change.
5. Log out and log in as admin1. Add a resource, mark it unavailable,
   and look at the campus report. Try adding the same resource code
   twice to see the duplicate being rejected. Notice that admin1 only
   sees Cape Town's resources.
6. Log in as admin3 (Johannesburg). Use the Priority Booking card to
   book the Main Auditorium 7 days from today at 09:00 for 60
   minutes. It overrides the lecturer's booking there, because that
   booking is more than 24 hours away.
7. Log out and log in as operator1 to look at all the campuses and
   generate the comparison report.
 
 
THINGS IT DOES NOT DO
----------------------------------------------------------------------
- There is no screen for creating administrator or operator accounts,
  so those roles only exist as the demo accounts.
- Booking times come from the clock of the computer the program is
  running on.
- There is no way to reset a forgotten password.
- The database is one local file, so the program is meant to run on a
  single computer and not for many people using it over a network.
 



-----------------------
Resources Used
-----------------------

channel = Bro-code - title = python tkinter tutorial for beginners
playlist = https://youtube.com/playlist?list=PLZPZq0r_RZOOeQBaP5SeMjl2nwDcJaV0T&si=zV26nl74txWWi99l
website = geeksforgeeks  - https://www.geeksforgeeks.org/python/python-gui-tkinter/

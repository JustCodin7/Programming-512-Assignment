"""
gui.py
This is the actual GUI for my Smart Campus Resource Booking System -
the login screen, the registration popup, and all three role dashboards
(Lecturer / Campus Administrator / System Operator). To actually start
the app, run main.py, which just calls run_app() from here.

Quick note on how I built the look of this app (design system):
  Ink Navy (#10192B)    - background colour for every window
  Panel (#1B273F)       - the card boxes each section sits inside
  Panel Light (#24314D) - background colour for input boxes
  Brass (#C7A252)       - main accent colour, used for the important buttons
  Brass Hover (#B08F42) - what brass buttons turn when you hover over them
  Brick (#B0524A)       - used for "dangerous" buttons like cancel/remove
  Parchment (#EDE6D6)   - the main text colour
  Muted (#9AA4B8)       - dimmer text, for labels/hints
  Sage (#7FA97A)        - used for "success"/available stuff

  Headings use Cambria (a serif font) so it feels a bit more "official",
  and everything else uses Segoe UI since every Windows PC already has it.

Instead of plain "--- text ---" dividers I used actual bordered card boxes
for each section, so the dashboards don't look like a giant wall of labels.
"""

import tkinter as tk
from tkinter import messagebox, ttk

# Everything in this file is plain Tkinter (tk + ttk) from Python's standard
# library, so there is nothing extra to install. The small widget classes
# further down (Frame, Label, Entry, Button, Dropdown) are my own thin
# wrappers around the normal Tkinter widgets. They exist so the dark colour
# scheme can be applied in one place instead of repeating the same colour
# options on every widget.

from database import (
    get_connection, add_resource, get_resources_by_campus,
    create_booking, get_campus, get_bookings_by_lecturer, cancel_booking,
    get_bookings_by_campus, get_all_resources_by_campus, set_resource_status,
    create_user, get_all_campuses, get_campus_report,
    get_all_resources, get_all_bookings,
    update_resource, delete_resource,
    booking_state, get_resource_schedule, get_resources_in_use_now,
)
from auth import verify_password
from models import create_user_object, CampusAdministrator, Lecturer, SystemOperator
from policies import BookingPolicy
from reports import (
    get_campus_comparison, get_resource_usage_by_campus,
    compare_resource_types, summarise_rule_impact,
)

# ---------------------------------------------------------------------------
# COLOURS + FONTS
# ---------------------------------------------------------------------------
# Keeping all of this up here means if I ever want to change a colour, I only
# change it in one place instead of hunting through the whole file.

INK = "#10192B"
PANEL = "#1B273F"
PANEL_LIGHT = "#24314D"
BORDER = "#2A3A5C"
BRASS = "#C7A252"
BRASS_HOVER = "#B08F42"
BRICK = "#B0524A"
BRICK_HOVER = "#943D36"
PARCHMENT = "#EDE6D6"
MUTED = "#9AA4B8"
SUCCESS = "#73B57B"
WARNING = "#D8A84B"

# one colour per campus, used wherever a chart compares campuses side by side
CAMPUS_COLORS = [BRASS, SUCCESS, "#6FA8DC", "#C97B84", "#9C8FD1", "#5FB3B3"]

HEADING_FONT = ("Cambria", 20, "bold")
CARD_TITLE_FONT = ("Cambria", 15, "bold")
BODY_FONT = ("Segoe UI", 12)
LABEL_FONT = ("Segoe UI", 11)
BUTTON_FONT = ("Segoe UI", 12, "bold")

# ---------------------------------------------------------------------------
# WIDGET HELPERS - plain Tkinter widgets with the app's colours built in
# ---------------------------------------------------------------------------
# Tkinter's own widgets each use slightly different option names for colours
# (bg / fg / highlightbackground ...). These wrappers let the rest of the file
# just say things like fg_color=PANEL or text_color=MUTED, and they translate
# that into the real Tkinter options here, once.

def _background_of(parent, fg_color):
    """"transparent" (or nothing) means: use whatever colour the parent has,
    so the widget blends into the card/window it sits on."""
    if fg_color is None or fg_color == "transparent":
        return parent.cget("bg")
    return fg_color


class Frame(tk.Frame):
    """A tk.Frame with an optional coloured outline - used for the cards,
    the stat boxes and the two-column layouts."""
    def __init__(self, parent, fg_color=None, border_width=0, border_color=None, **kw):
        kw.pop("corner_radius", None)   # Tkinter frames can't have rounded corners
        bg = _background_of(parent, fg_color)
        outline = border_color or bg
        super().__init__(parent, bg=bg, bd=0, highlightthickness=border_width,
                         highlightbackground=outline, highlightcolor=outline, **kw)


class Label(tk.Label):
    """A tk.Label that takes text_color instead of fg, and blends into its
    parent's background. text_color also works in .configure(...) later."""
    def __init__(self, parent, text="", text_color=PARCHMENT, fg_color=None, **kw):
        super().__init__(parent, text=text, fg=text_color,
                         bg=_background_of(parent, fg_color), **kw)

    def configure(self, cnf=None, **kw):
        if "text_color" in kw:
            kw["fg"] = kw.pop("text_color")
        return super().configure(cnf, **kw)

    config = configure


class Entry(tk.Entry):
    """A text box in the app's colours. Gets a little extra inner height so
    it isn't as thin as the default Tkinter one."""
    def __init__(self, parent, fg_color=PANEL_LIGHT, border_color=BORDER,
                 text_color=PARCHMENT, show=None, **kw):
        kw.pop("corner_radius", None)
        if show:
            kw["show"] = show   # e.g. "*" for password boxes
        super().__init__(
            parent, bg=fg_color, fg=text_color, insertbackground=text_color,
            selectbackground=BRASS, selectforeground=INK, relief="flat", bd=0,
            highlightthickness=1, highlightbackground=border_color, highlightcolor=BRASS,
            **kw,
        )

    def pack(self, *args, **kw):
        kw.setdefault("ipady", 6)
        super().pack(*args, **kw)


class Button(tk.Label):
    """A clickable button. It is built from a Label rather than tk.Button on
    purpose: the normal tk.Button ignores background colours on macOS, so this
    keeps the gold/red buttons looking the same on every computer. It changes
    colour when the mouse is over it and only fires if the mouse is released
    while still on the button, like a normal button."""
    def __init__(self, parent, text="", command=None, font=None, fg_color=BRASS,
                 hover_color=BRASS_HOVER, text_color=INK, border_width=0,
                 border_color=None, width=None, **kw):
        kw.pop("corner_radius", None)
        self._command = command
        self._normal = _background_of(parent, fg_color)
        self._hover = hover_color
        if width:
            kw["width"] = max(1, width // 9)   # Tkinter measures label width in characters
        super().__init__(
            parent, text=text, font=font, fg=text_color, bg=self._normal, cursor="hand2",
            highlightthickness=border_width,
            highlightbackground=border_color or self._normal,
            highlightcolor=border_color or self._normal,
            pady=7, padx=10, **kw,
        )
        self.bind("<Enter>", lambda event: self.configure(bg=self._hover))
        self.bind("<Leave>", lambda event: self.configure(bg=self._normal))
        self.bind("<ButtonRelease-1>", self._released)

    def _released(self, event):
        # only count it as a click if the mouse is still over the button
        if 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height():
            self.invoke()

    def invoke(self):
        if self._command:
            self._command()


class Dropdown(tk.OptionMenu):
    """A drop-down list (tk.OptionMenu) in the app's colours. .get() and
    .set() read and change the chosen value. `command` is called with the
    newly chosen value whenever the user picks something."""
    def __init__(self, parent, values, variable=None, command=None,
                 fg_color=PANEL_LIGHT, button_color=BRASS, text_color=PARCHMENT, **kw):
        self._variable = variable or tk.StringVar(parent, value=values[0])
        super().__init__(parent, self._variable, *values, command=command)
        self.configure(
            bg=fg_color, fg=text_color, activebackground=button_color, activeforeground=INK,
            font=BODY_FONT, anchor="w", relief="flat", bd=0, indicatoron=True,
            highlightthickness=1, highlightbackground=BORDER, padx=10, pady=6,
        )
        self["menu"].configure(
            bg=fg_color, fg=text_color, activebackground=button_color, activeforeground=INK,
            font=BODY_FONT, bd=0, relief="flat",
        )

    def get(self):
        return self._variable.get()

    def set(self, value):
        self._variable.set(value)


def make_scrollable(parent, bg=INK):
    """Tkinter has no scrollable frame, so this builds one: a Canvas with a
    scrollbar, and a normal frame placed inside the canvas. The dashboards go
    inside that frame, so a page taller than the screen can be scrolled
    instead of getting cut off. Returns the inner frame to put widgets in."""
    outer = tk.Frame(parent, bg=bg)
    outer.pack(fill="both", expand=True, padx=10, pady=10)
    canvas = tk.Canvas(outer, bg=bg, highlightthickness=0, bd=0)
    scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    inner = tk.Frame(canvas, bg=bg)
    inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")
    # keep the scrollable area sized to the content, and the content as wide as the window
    inner.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda event: canvas.itemconfigure(inner_id, width=event.width))

    def on_mousewheel(event):
        try:
            if isinstance(event.widget, ttk.Treeview):
                return   # a table scrolls itself; don't also scroll the whole page
            if event.num == 4:            # Linux wheel up
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:          # Linux wheel down
                canvas.yview_scroll(1, "units")
            else:                         # Windows / macOS
                canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        except tk.TclError:
            pass   # the window was closed while the event was on its way

    for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        canvas.bind_all(sequence, on_mousewheel)
    return inner


def configure_table_style(root):
    """Tkinter's ttk.Treeview is the table widget I use for the resource and
    booking lists - this makes it match my dark theme instead of looking like
    a default grey Windows table."""
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(
        "Vertical.TScrollbar", background=BORDER, troughcolor=PANEL_LIGHT,
        arrowcolor=PARCHMENT, bordercolor=PANEL_LIGHT, relief="flat",
    )
    style.configure(
        "Campus.Treeview",
        background=PANEL_LIGHT, fieldbackground=PANEL_LIGHT, foreground=PARCHMENT,
        rowheight=31, borderwidth=0, font=("Segoe UI", 10),
    )
    style.configure(
        "Campus.Treeview.Heading",
        background=BORDER, foreground=PARCHMENT, relief="flat",
        font=("Segoe UI", 10, "bold"), padding=(10, 8),
    )
    style.map(
        "Campus.Treeview",
        background=[("selected", BRASS)], foreground=[("selected", INK)],
    )


def make_metric(parent, value, label, accent=BRASS):
    """One of those little stat boxes at the top of each dashboard
    (e.g. "7 Resources available"). Just a number + a caption under it.
    Returns the number label itself (not the whole box) so the caller can
    update it later with .configure(text=...) - e.g. after a new booking
    is made, so the metric doesn't just sit there stale until the whole
    dashboard is reopened."""
    metric = Frame(parent, fg_color=PANEL, corner_radius=12, border_width=1, border_color=BORDER)
    metric.pack(side="left", fill="x", expand=True, padx=5)
    value_label = Label(metric, text=str(value), font=("Cambria", 25, "bold"), text_color=accent)
    value_label.pack(anchor="w", padx=16, pady=(13, 0))
    Label(metric, text=label, font=("Segoe UI", 10), text_color=MUTED).pack(
        anchor="w", padx=16, pady=(0, 13)
    )
    return value_label


def make_card(parent, title):
    """This is basically my replacement for the old "--- Section ---" text
    dividers. Makes a proper bordered box with a title at the top, and I
    reuse this everywhere so every section on every dashboard looks the same."""
    card = Frame(parent, fg_color=PANEL, corner_radius=14, border_width=1, border_color=BORDER)
    card.pack(fill="x", padx=20, pady=(0, 16))
    Label(card, text=title, font=CARD_TITLE_FONT, text_color=BRASS, anchor="w").pack(
        fill="x", padx=18, pady=(16, 8)
    )
    return card


def make_field(card, label_text):
    """A label sitting above an entry box, both styled to match the rest
    of the app. Saves me writing the same 6 lines every time I need a
    text field."""
    Label(card, text=label_text, font=LABEL_FONT, text_color=MUTED, anchor="w").pack(
        fill="x", padx=18, pady=(4, 0)
    )
    entry = Entry(
        card, fg_color=PANEL_LIGHT, border_color=BORDER, text_color=PARCHMENT,
        font=BODY_FONT, corner_radius=8,
    )
    entry.pack(fill="x", padx=18, pady=(2, 10))
    return entry


def make_button(card, text, command, style="primary"):
    """One button helper for the whole app. style="primary" is the normal
    gold button for things like Add/Book/Login. style="danger" is the red
    one for Cancel/Remove type actions, so the colour itself gives people
    a hint about what the button actually does before they even read it."""
    colors = {
        "primary": (BRASS, BRASS_HOVER, INK),
        "danger": (BRICK, BRICK_HOVER, PARCHMENT),
    }
    fg, hover, text_color = colors[style]
    btn = Button(
        card, text=text, command=command, font=BUTTON_FONT,
        fg_color=fg, hover_color=hover, text_color=text_color, corner_radius=8,
    )
    btn.pack(fill="x", padx=18, pady=(4, 16))
    return btn


def make_listbox(parent, width=50, height=6):
    """Not actually used for the main tables anymore (I switched those to
    make_table below), but keeping this in case I need a really simple
    list somewhere - styled the same dark colours as everything else."""
    lb = tk.Listbox(
        parent,
        width=width,
        height=height,
        bg=PANEL_LIGHT,
        fg=PARCHMENT,
        font=("Segoe UI", 10),
        selectbackground=BRASS,
        selectforeground=INK,
        highlightthickness=1,
        highlightbackground=BORDER,
        highlightcolor=BRASS,
        relief="flat",
        borderwidth=0,
    )
    lb.pack(fill="x", padx=18, pady=(2, 12))
    return lb


def make_table(parent, columns, height=7):
    """Builds one of the proper tables with column headings (Code / Name /
    Status etc) that I use for resources and bookings. `columns` is a list
    of (internal_name, heading_text) pairs so I can set both at once.
    Also colours a row green/red depending on its status tag - that's set
    with .tag_configure below and used wherever I do listbox.insert(...,
    tags=(status,))."""
    wrap = Frame(parent, fg_color=PANEL_LIGHT, corner_radius=8)
    wrap.pack(fill="x", padx=18, pady=(2, 12))
    tree = ttk.Treeview(wrap, columns=[key for key, _ in columns], show="headings", height=height,
                        style="Campus.Treeview")
    for key, heading in columns:
        tree.heading(key, text=heading, anchor="w")
        tree.column(key, anchor="w", width=max(85, len(heading) * 12), stretch=True)
    scroll = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    tree.tag_configure("available", foreground=SUCCESS)
    tree.tag_configure("unavailable", foreground="#E87A70")
    tree.tag_configure("cancelled", foreground="#E87A70")
    # booking states (see booking_state() in database.py)
    tree.tag_configure("upcoming", foreground=SUCCESS)
    tree.tag_configure("inprogress", foreground=WARNING)
    tree.tag_configure("past", foreground=MUTED)
    return tree


def state_tag(state):
    """Turn a booking state like 'In progress' into the matching row-colour
    tag name ('inprogress') set up in make_table above."""
    return state.lower().replace(" ", "")


def make_chart_canvas(parent, height=190):
    """Just a blank canvas to draw a chart onto later. Using plain
    tk.Canvas here instead of installing a whole charting library, since
    the charts I need are simple enough to draw by hand with rectangles/arcs."""
    canvas = tk.Canvas(parent, height=height, bg=PANEL, highlightthickness=0, bd=0)
    canvas.pack(fill="x", padx=18, pady=(2, 12))
    return canvas


def draw_bar_chart(canvas, data, title, color=BRASS):
    """Draws a simple bar chart from a list of (label, value) pairs.
    Nothing fancy - just maths to work out bar heights based on whatever
    the biggest value is, then draws rectangles + text for each bar."""
    canvas.delete("all")
    canvas.update_idletasks()
    width = max(canvas.winfo_width(), 360)
    height = int(canvas.cget("height"))
    left, right, top, bottom = 42, 16, 28, 38
    plot_width, plot_height = width - left - right, height - top - bottom
    canvas.create_text(0, 6, text=title.upper(), anchor="nw", fill=MUTED, font=("Segoe UI", 9, "bold"))
    if not data or max(value for _, value in data) == 0:
        # nothing booked yet, so just show a message instead of an empty chart
        canvas.create_text(width / 2, height / 2, text="No report data yet", fill=MUTED, font=BODY_FONT)
        return
    maximum = max(value for _, value in data)
    for step in range(3):
        # drawing 3 faint horizontal guide lines with numbers next to them
        y = top + plot_height * step / 2
        canvas.create_line(left, y, width - right, y, fill=BORDER, width=1)
        canvas.create_text(left - 7, y, text=str(round(maximum * (2 - step) / 2)), anchor="e", fill=MUTED, font=("Segoe UI", 8))
    gap = 12
    bar_width = max(22, (plot_width - gap * (len(data) + 1)) / len(data))
    for index, (label, value) in enumerate(data):
        # working out where each bar goes left-to-right, then how tall it should be
        x1 = left + gap + index * (bar_width + gap)
        x2 = x1 + bar_width
        y2 = top + plot_height
        y1 = y2 - (value / maximum * plot_height)
        canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="")
        canvas.create_text((x1 + x2) / 2, y1 - 8, text=str(value), fill=PARCHMENT, font=("Segoe UI", 9, "bold"))
        short_label = label if len(label) <= 12 else label[:11] + "…"
        canvas.create_text((x1 + x2) / 2, y2 + 15, text=short_label, fill=MUTED, font=("Segoe UI", 8))


def draw_donut_chart(canvas, values, title):
    """Draws the little donut chart (used for available vs unavailable
    resources). `values` is a list of (label, value, colour) tuples - one
    slice per entry, sized by how big its value is compared to the total."""
    canvas.delete("all")
    canvas.update_idletasks()
    width, height = max(canvas.winfo_width(), 360), int(canvas.cget("height"))
    canvas.create_text(0, 6, text=title.upper(), anchor="nw", fill=MUTED, font=("Segoe UI", 9, "bold"))
    total = sum(value for _, value, _ in values)
    if total == 0:
        canvas.create_text(width / 2, height / 2, text="No report data yet", fill=MUTED, font=BODY_FONT)
        return
    x1, y1, x2, y2 = 18, 30, 155, 167
    start = 90
    for label, value, color in values:
        # each slice's angle is just its share of the total, out of 360 degrees
        extent = 360 * value / total
        canvas.create_arc(x1, y1, x2, y2, start=start, extent=-extent, fill=color, outline=PANEL, width=3, style="pieslice")
        start -= extent
    # covering the middle with a plain circle so it looks like a donut, not a pie
    canvas.create_oval(55, 67, 118, 130, fill=PANEL, outline=PANEL)
    canvas.create_text(86, 88, text=str(total), fill=PARCHMENT, font=("Cambria", 18, "bold"))
    canvas.create_text(86, 110, text="TOTAL", fill=MUTED, font=("Segoe UI", 8, "bold"))
    legend_x = 185
    for index, (label, value, color) in enumerate(values):
        # small coloured dot + label + number next to the donut, one per row
        y = 54 + index * 34
        canvas.create_oval(legend_x, y, legend_x + 10, y + 10, fill=color, outline="")
        canvas.create_text(legend_x + 17, y + 5, text=label, anchor="w", fill=PARCHMENT, font=("Segoe UI", 10))
        canvas.create_text(width - 6, y + 5, text=str(value), anchor="e", fill=PARCHMENT, font=("Segoe UI", 10, "bold"))


def draw_stacked_bar_chart(canvas, rows, series_names, title):
    """Horizontal stacked bar chart, used to compare campuses. `rows` is a
    list of (label, {series_name: value}) - one bar per row, and each bar is
    split into coloured segments, one per series (here: one per campus).
    The canvas grows to fit however many rows there are, since the number of
    resource types isn't fixed."""
    canvas.delete("all")
    row_height, top = 26, 52
    canvas.configure(height=top + max(len(rows), 1) * row_height + 10)
    canvas.update_idletasks()
    width = max(canvas.winfo_width(), 360)
    canvas.create_text(0, 6, text=title.upper(), anchor="nw", fill=MUTED, font=("Segoe UI", 9, "bold"))

    # each series (campus) always gets the same colour, in the same order
    colors = {name: CAMPUS_COLORS[i % len(CAMPUS_COLORS)] for i, name in enumerate(series_names)}
    legend_x = 0
    for name in series_names:
        canvas.create_rectangle(legend_x, 28, legend_x + 10, 38, fill=colors[name], outline="")
        canvas.create_text(legend_x + 15, 33, text=name, anchor="w", fill=PARCHMENT, font=("Segoe UI", 9))
        legend_x += 15 + len(name) * 7 + 18

    totals = [sum(values.values()) for _, values in rows]
    if not rows or max(totals) == 0:
        canvas.create_text(width / 2, top + 20, text="No bookings yet", fill=MUTED, font=BODY_FONT)
        return

    label_width, right_padding = 120, 34
    plot_width = width - label_width - right_padding
    maximum = max(totals)   # the longest bar fills the plot; every other bar is scaled against it
    for index, (label, values) in enumerate(rows):
        y = top + index * row_height
        short_label = label if len(label) <= 17 else label[:16] + "…"
        canvas.create_text(label_width - 8, y + 8, text=short_label, anchor="e", fill=MUTED, font=("Segoe UI", 9))
        x = label_width
        for name in series_names:
            value = values.get(name, 0)
            if value:
                segment = value / maximum * plot_width
                canvas.create_rectangle(x, y, x + segment, y + 16, fill=colors[name], outline=PANEL, width=1)
                x += segment
        # total at the end of the bar (a type nobody has booked shows 0)
        canvas.create_text(x + 6, y + 8, text=str(sum(values.values())), anchor="w", fill=PARCHMENT, font=("Segoe UI", 9, "bold"))


# ---------------------------------------------------------------------------
# CAMPUS ADMINISTRATOR DASHBOARD
# ---------------------------------------------------------------------------

def build_admin_resource_form(dashboard, user, resources_metric_label=None, available_metric_label=None, bookings_metric_label=None):
    """Everything a Campus Administrator sees: add resources, see every
    booking at their campus, mark resources available/unavailable, and
    pull up a report. Split into a left column and right column so it's
    not just one long list going down the page."""
    layout = Frame(dashboard, fg_color="transparent")
    layout.pack(fill="both", expand=True, padx=10)
    left = Frame(layout, fg_color="transparent")
    right = Frame(layout, fg_color="transparent")
    left.pack(side="left", fill="both", expand=True, padx=(0, 8))
    right.pack(side="left", fill="both", expand=True, padx=(8, 0))

    # --- Add a New Resource ---
    card = make_card(left, "Add a New Resource")
    code_entry = make_field(card, "Resource Code (e.g. CT-LAB-02)")
    name_entry = make_field(card, "Resource Name")
    type_entry = make_field(card, "Resource Type (Lab / Projector / Room)")

    def submit_resource():
        # cleaning up whatever they typed before it goes anywhere near the database -
        # .strip() removes stray spaces, .upper()/.title() keep codes/types consistent
        code = code_entry.get().strip().upper()
        name = name_entry.get().strip()
        r_type = type_entry.get().strip().title()

        if not code or not name or not r_type:
            messagebox.showerror("Error", "All fields are required.")
            return

        success, message = add_resource(
            campus_id=user.campus_id, resource_code=code, name=name, resource_type=r_type,
        )
        if success:
            messagebox.showinfo("Success", message)
            # clear the form out so it's ready for the next resource
            code_entry.delete(0, tk.END)
            name_entry.delete(0, tk.END)
            type_entry.delete(0, tk.END)
            refresh_resources()
            show_report()
        else:
            messagebox.showerror("Error", message)

    make_button(card, "Add Resource", submit_resource, style="primary")

    # --- Campus Bookings (every booking made at this admin's own campus) ---
    bookings_card = make_card(right, "Campus Bookings")
    campus_bookings_listbox = make_table(bookings_card, [
        ("resource", "Resource"), ("lecturer", "Lecturer"), ("date", "Date"), ("time", "Time"), ("status", "Status"),
    ], height=8)

    def refresh_campus_bookings():
        # wipe the table and rebuild it from scratch - simplest way to keep it
        # showing the current state without trying to patch individual rows
        campus_bookings_listbox.delete(*campus_bookings_listbox.get_children())
        campus_bookings = get_bookings_by_campus(user.campus_id)
        for b in campus_bookings:
            state = booking_state(b)   # Upcoming / In progress / Past / Cancelled
            campus_bookings_listbox.insert("", "end", values=(b['resource_name'], b['lecturer_name'], b['booking_date'], f"{b['start_time']} · {b['duration_minutes']} min", state), tags=(state_tag(state),))
        # keeps the "Campus bookings" number at the top in sync with reality -
        # otherwise it's stuck at whatever it was when the dashboard opened
        if bookings_metric_label is not None:
            bookings_metric_label.configure(text=str(len(campus_bookings)))

    # --- Manage Resources (mark things available/unavailable) ---
    manage_card = make_card(left, "Manage Resources")
    manage_listbox = make_table(manage_card, [("code", "Code"), ("name", "Name"), ("type", "Type"), ("status", "Status")], height=7)

    all_resources = []  # keeping the actual data here so I can match a clicked row back to its real DB record

    def refresh_resources():
        nonlocal all_resources
        manage_listbox.delete(*manage_listbox.get_children())
        all_resources = get_all_resources_by_campus(user.campus_id)
        for r in all_resources:
            manage_listbox.insert("", "end", values=(r['resource_code'], r['name'], r['resource_type'], r['status'].title()), tags=(r['status'].lower(),))
        # same idea as above - keeps "Total resources" and "Available now"
        # accurate after adding, removing, or toggling a resource's status
        if resources_metric_label is not None:
            resources_metric_label.configure(text=str(len(all_resources)))
        if available_metric_label is not None:
            available_metric_label.configure(text=str(sum(r["status"] == "available" for r in all_resources)))

    def toggle_status(new_status):
        selection = manage_listbox.selection()
        if not selection:
            messagebox.showerror("Error", "Please select a resource first.")
            return
        # .index() tells me WHERE in the table they clicked, so I can grab the
        # matching resource out of all_resources (same order as the table rows)
        selected_resource = all_resources[manage_listbox.index(selection[0])]
        success, message = set_resource_status(selected_resource["resource_id"], user.campus_id, new_status)
        if success:
            messagebox.showinfo("Success", message)
            refresh_resources()
            show_report()
        else:
            messagebox.showerror("Error", message)

    make_button(manage_card, "Mark Available", lambda: toggle_status("available"), style="primary")
    make_button(manage_card, "Mark Unavailable", lambda: toggle_status("unavailable"), style="danger")

    def remove_resource():
        selection = manage_listbox.selection()
        if not selection:
            messagebox.showerror("Error", "Please select a resource first.")
            return
        selected_resource = all_resources[manage_listbox.index(selection[0])]

        # this is permanent (unlike Mark Unavailable), so double-check with
        # the admin before it actually happens
        confirmed = messagebox.askyesno(
            "Remove Resource",
            f"Permanently remove '{selected_resource['name']}' "
            f"({selected_resource['resource_code']})?\n\nThis can't be undone.",
        )
        if not confirmed:
            return

        # delete_resource() itself refuses if this resource has any booking
        # history - it isn't a check we need to duplicate here, we just
        # show whatever message it gives back
        success, message = delete_resource(selected_resource["resource_id"], user.campus_id)
        if success:
            messagebox.showinfo("Success", message)
            refresh_resources()
            show_report()
        else:
            messagebox.showerror("Can't Remove Resource", message)

    make_button(manage_card, "Remove Resource Permanently", remove_resource, style="danger")

    # --- updating a resource's name/type (not its code - see update_resource's
    # own docstring in database.py for why the code stays fixed) ---
    Label(manage_card, text="Update Selected Resource", font=LABEL_FONT, text_color=MUTED, anchor="w").pack(
        fill="x", padx=18, pady=(6, 0)
    )

    # shows which resource is currently loaded into the fields below, same
    # idea as the "Selected: ..." label on the Lecturer's booking screen
    editing_label = Label(
        manage_card, text="No resource selected", font=LABEL_FONT, text_color=BRASS, anchor="w"
    )
    editing_label.pack(fill="x", padx=18, pady=(4, 0))

    update_name_entry = make_field(manage_card, "New Name")
    update_type_entry = make_field(manage_card, "New Type")

    def on_manage_select(event=None):
        # fires automatically whenever a different row is clicked in the
        # table - just confirms which resource is currently selected,
        # nothing gets typed into the fields below automatically
        selection = manage_listbox.selection()
        if not selection:
            editing_label.configure(text="No resource selected")
            return
        selected = all_resources[manage_listbox.index(selection[0])]
        editing_label.configure(text=f"{selected['resource_code']} selected")

    manage_listbox.bind("<<TreeviewSelect>>", on_manage_select)

    def submit_update():
        selection = manage_listbox.selection()
        if not selection:
            messagebox.showerror("Error", "Please select a resource first.")
            return
        selected_resource = all_resources[manage_listbox.index(selection[0])]

        new_name = update_name_entry.get().strip()
        new_type = update_type_entry.get().strip().title()
        if not new_name or not new_type:
            messagebox.showerror("Error", "Both new name and new type are required.")
            return

        success, message = update_resource(selected_resource["resource_id"], user.campus_id, new_name, new_type)
        if success:
            messagebox.showinfo("Success", message)
            update_name_entry.delete(0, tk.END)
            update_type_entry.delete(0, tk.END)
            refresh_resources()
        else:
            messagebox.showerror("Error", message)

    make_button(manage_card, "Update Resource", submit_update, style="primary")

    # --- Campus Insights (the report + charts) ---
    report_card = make_card(right, "Campus Insights")
    report_label = Label(report_card, text="Generate a report to see your campus activity.", justify="left", font=BODY_FONT, text_color=MUTED, anchor="w", wraplength=440)
    report_label.pack(fill="x", padx=18, pady=(0, 10))
    usage_chart = make_chart_canvas(report_card)
    availability_chart = make_chart_canvas(report_card, height=170)

    def show_report():
        report = get_campus_report(user.campus_id)
        # top_resources is a list of (name, count) pairs - the brief asks for
        # the most frequently used resources (plural), not just one
        top_text = ", ".join(f"{name} ({count})" for name, count in report["top_resources"]) or "none yet"
        report_text = (
            f"{report['total_bookings']} booking{'' if report['total_bookings'] == 1 else 's'} recorded · "
            f"{report['unique_lecturers']} different lecturer{'' if report['unique_lecturers'] == 1 else 's'} · "
            f"average duration: {report['avg_duration']} min\n"
            f"Most frequently used: {top_text}"
        )
        report_label.configure(text=report_text)
        bookings = get_bookings_by_campus(user.campus_id)
        # counting how many times each resource shows up in the bookings list,
        # so I can chart "most booked resources" without a fancy query
        usage = {}
        for booking in bookings:
            usage[booking["resource_name"]] = usage.get(booking["resource_name"], 0) + 1
        draw_bar_chart(usage_chart, sorted(usage.items(), key=lambda item: item[1], reverse=True)[:5], "Bookings by resource")
        resources = get_all_resources_by_campus(user.campus_id)
        available = sum(resource["status"] == "available" for resource in resources)
        draw_donut_chart(availability_chart, [("Available", available, SUCCESS), ("Unavailable", len(resources) - available, BRICK)], "Resource availability")

    make_button(report_card, "Generate Report", show_report, style="primary")

    def auto_refresh_report():
        """Keeps the report/charts up to date every 15 seconds while the
        dashboard is open, in case something changes (like a lecturer making
        a new booking) while the admin is sitting on this screen. The
        winfo_exists() check stops this from trying to update a window
        that's already been closed."""
        if report_card.winfo_exists():
            show_report()
            report_card.after(15000, auto_refresh_report)

    report_card.after(15000, auto_refresh_report)

    # --- Priority Booking - only shows up for a campus that actually has this rule ---
    # (right now that's just Johannesburg - see the priority_override column
    # in the campuses table). Cape Town/Durban admins won't see this card at all.
    campus = get_campus(user.campus_id)
    if campus["priority_override"]:
        priority_card = make_card(left, "Priority Booking (Override)")
        Label(
            priority_card,
            text="This campus allows an admin booking to override an existing\nlecturer booking, but only with 24+ hours' notice.",
            font=LABEL_FONT, text_color=MUTED, justify="left", anchor="w",
        ).pack(fill="x", padx=18, pady=(0, 10))

        priority_resources = get_resources_by_campus(user.campus_id)
        priority_resource_table = make_table(priority_card, [("code", "Code"), ("name", "Name")], height=4)
        for r in priority_resources:
            priority_resource_table.insert("", "end", values=(r["resource_code"], r["name"]))

        p_date_entry = make_field(priority_card, "Date (YYYY-MM-DD)")
        p_time_entry = make_field(priority_card, "Start Time (HH:MM, 24hr)")
        p_duration_entry = make_field(priority_card, "Duration (minutes)")

        def submit_priority_booking():
            selection = priority_resource_table.selection()
            if not selection:
                messagebox.showerror("Error", "Please select a resource first.")
                return
            selected_resource = priority_resources[priority_resource_table.index(selection[0])]
            try:
                duration = int(p_duration_entry.get())
            except ValueError:
                messagebox.showerror("Error", "Duration must be a whole number of minutes.")
                return

            # the important bit here is requesting_role="admin" - that's what
            # tells create_booking() this request is ALLOWED to bump an
            # existing lecturer booking (with the 24-hour rule still applying).
            # A normal lecturer booking never passes this, so they can never
            # override anyone else.
            success, message = create_booking(
                resource_id=selected_resource["resource_id"],
                lecturer_id=user.user_id,
                campus_id=user.campus_id,
                booking_date=p_date_entry.get().strip(),
                start_time=p_time_entry.get().strip(),
                duration_minutes=duration,
                requesting_role="admin",
            )
            if success:
                messagebox.showinfo("Success", message)
                refresh_campus_bookings()
                show_report()
            else:
                messagebox.showerror("Booking Failed", message)

        make_button(priority_card, "Book / Override", submit_priority_booking, style="danger")

    # filling both tables in as soon as the dashboard opens, not just when a button is clicked
    refresh_campus_bookings()
    refresh_resources()


# ---------------------------------------------------------------------------
# LECTURER DASHBOARD
# ---------------------------------------------------------------------------

def build_lecturer_view(dashboard, user, bookings_metric_label=None):
    """Everything a Lecturer sees: the list of resources they can book,
    the actual booking form, and their own booking history with a cancel
    option."""
    layout = Frame(dashboard, fg_color="transparent")
    layout.pack(fill="both", expand=True, padx=10)
    left = Frame(layout, fg_color="transparent")
    right = Frame(layout, fg_color="transparent")
    left.pack(side="left", fill="both", expand=True, padx=(0, 8))
    right.pack(side="left", fill="both", expand=True, padx=(8, 0))

    # --- Available Resources ---
    # user.campus_id is the campus the lecturer SELECTED after logging in
    # (see show_campus_selection) - not necessarily the one they registered at
    campus = get_campus(user.campus_id)
    resources_card = make_card(left, f"Available Resources · {campus['name']}")
    resource_listbox = make_table(resources_card, [("code", "Code"), ("resource", "Resource"), ("type", "Type"), ("now", "Right now")], height=8)

    # keeping the actual resource records around (not just what's shown in the
    # table) so I can match a clicked row back to a real resource_id later
    resources = get_resources_by_campus(user.campus_id)
    for r in resources:
        resource_listbox.insert("", "end", values=(r['resource_code'], r['name'], r['resource_type'], "Free"))

    def refresh_resource_now():
        """Updates the 'Right now' column: 'Free', or 'In use until HH:MM'
        for a resource someone is using at this moment (brief 6.2 - real-time
        availability). It edits the existing rows in place instead of
        rebuilding the table, so whatever row is selected stays selected."""
        in_use = get_resources_in_use_now(user.campus_id)
        for row_id, r in zip(resource_listbox.get_children(), resources):
            busy = r["resource_id"] in in_use
            resource_listbox.item(
                row_id,
                values=(r['resource_code'], r['name'], r['resource_type'],
                        f"In use until {in_use[r['resource_id']]}" if busy else "Free"),
                tags=("inprogress" if busy else "available",),
            )

    refresh_resource_now()

    # showing this campus's own booking rules right under the table, so the
    # lecturer knows the limits before they even try to book something
    # (brief section 5.1: the policy in effect must be clearly indicated).
    # The wording comes from the BookingPolicy object in policies.py, so the
    # rules shown here can never drift out of step with the rules enforced.
    policy = BookingPolicy.from_campus(campus)
    Label(
        resources_card, text=policy.describe(), font=LABEL_FONT, text_color=MUTED,
        anchor="w", justify="left", wraplength=440,
    ).pack(fill="x", padx=18, pady=(0, 14))

    # --- Book Selected Resource ---
    booking_card = make_card(right, "Book Selected Resource")

    # this label just shows which resource is currently clicked/highlighted -
    # added it because the highlight colour on the table alone was easy to miss
    selected_resource_label = Label(
        booking_card, text="No resource selected", font=LABEL_FONT, text_color=BRASS, anchor="w"
    )
    selected_resource_label.pack(fill="x", padx=18, pady=(0, 10))

    def on_resource_select(event=None):
        # <<TreeviewSelect>> fires automatically whenever someone clicks a
        # different row in the table, so this keeps the label above in sync
        # without needing a button click
        selection = resource_listbox.selection()
        if selection:
            selected = resources[resource_listbox.index(selection[0])]
            selected_resource_label.configure(
                text=f"Selected: {selected['name']} ({selected['resource_code']})"
            )
        else:
            selected_resource_label.configure(text="No resource selected")
        refresh_schedule()   # show when the newly selected resource is already booked

    resource_listbox.bind("<<TreeviewSelect>>", on_resource_select)

    date_entry = make_field(booking_card, "Date (YYYY-MM-DD)")
    time_entry = make_field(booking_card, "Start Time (HH:MM, 24hr)")
    duration_entry = make_field(booking_card, "Duration (minutes)")

    # --- My Bookings ---
    bookings_card = make_card(left, "My Bookings")

    # filter for the table below: "Active" = upcoming + in progress (brief 6.1
    # "view active bookings"), "Past" = booking history, plus cancelled/all
    Label(bookings_card, text="Show", font=LABEL_FONT, text_color=MUTED, anchor="w").pack(
        fill="x", padx=18, pady=(0, 0)
    )
    booking_filter = Dropdown(
        bookings_card, values=["All", "Active", "Past", "Cancelled"],
        command=lambda choice: refresh_bookings(),
        fg_color=PANEL_LIGHT, button_color=BRASS,
        text_color=PARCHMENT,
    )
    booking_filter.set("All")
    booking_filter.pack(fill="x", padx=18, pady=(2, 8))

    bookings_listbox = make_table(bookings_card, [("resource", "Resource"), ("campus", "Campus"), ("date", "Date"), ("time", "Time"), ("status", "Status")], height=7)

    my_bookings = []  # the bookings currently SHOWN (after the filter), same order as the table rows

    def refresh_bookings():
        nonlocal my_bookings
        # remember which booking is selected, so a refresh (or a filter
        # change) doesn't throw the selection away
        selection = bookings_listbox.selection()
        selected_id = my_bookings[bookings_listbox.index(selection[0])]["booking_id"] if selection else None

        bookings_listbox.delete(*bookings_listbox.get_children())
        all_bookings = get_bookings_by_lecturer(user.user_id)
        wanted = booking_filter.get()
        my_bookings = []
        for b in all_bookings:
            state = booking_state(b)   # Upcoming / In progress / Past / Cancelled
            if wanted == "Active" and state not in ("Upcoming", "In progress"):
                continue
            if wanted == "Past" and state != "Past":
                continue
            if wanted == "Cancelled" and state != "Cancelled":
                continue
            my_bookings.append(b)
            row_id = bookings_listbox.insert("", "end", values=(b['resource_name'], b['campus_name'], b['booking_date'], f"{b['start_time']} · {b['duration_minutes']} min", state), tags=(state_tag(state),))
            if b["booking_id"] == selected_id:
                bookings_listbox.selection_set(row_id)

        # "Active bookings" = bookings still to come (or happening now). The
        # raw status column can't tell a past booking from a future one, so
        # this uses booking_state(). Counts ALL of the lecturer's bookings,
        # not just the ones the filter is currently showing.
        if bookings_metric_label is not None:
            active_count = sum(1 for b in all_bookings if booking_state(b) in ("Upcoming", "In progress"))
            bookings_metric_label.configure(text=str(active_count))

    def submit_booking():
        selection = resource_listbox.selection()
        if not selection:
            messagebox.showerror("Error", "Please select a resource from the list first.")
            return
        selected_resource = resources[resource_listbox.index(selection[0])]
        try:
            # entry boxes only ever give back plain text, so this is checking
            # someone actually typed a real number and not letters or nothing
            duration = int(duration_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Duration must be a whole number of minutes.")
            return

        # all the actual rule-checking (overlaps, campus hours, max duration,
        # resource availability) happens inside create_booking() in database.py -
        # this just passes along whatever the lecturer typed and shows the result
        success, message = create_booking(
            resource_id=selected_resource["resource_id"],
            lecturer_id=user.user_id,
            campus_id=user.campus_id,
            booking_date=date_entry.get().strip(),
            start_time=time_entry.get().strip(),
            duration_minutes=duration,
        )
        if success:
            messagebox.showinfo("Success", message)
            refresh_bookings()  # so the new booking shows up straight away, no re-login needed
            refresh_resource_now()
            refresh_schedule()
        else:
            messagebox.showerror("Booking Failed", message)

    make_button(booking_card, "Book Resource", submit_booking, style="primary")

    # --- Booked slots for the selected resource (brief 6.2 - availability) ---
    # Shows when the resource is ALREADY taken, so a lecturer can pick a free
    # time instead of guessing and getting an "overlapping" error.
    schedule_card = make_card(right, "Booked Slots · Selected Resource")
    schedule_status_label = Label(
        schedule_card, text="Select a resource to see when it is booked.",
        font=LABEL_FONT, text_color=MUTED, anchor="w", justify="left", wraplength=440,
    )
    schedule_status_label.pack(fill="x", padx=18, pady=(0, 8))
    schedule_table = make_table(schedule_card, [("date", "Date"), ("time", "Time"), ("length", "Length")], height=5)

    def refresh_schedule():
        schedule_table.delete(*schedule_table.get_children())
        selection = resource_listbox.selection()
        if not selection:
            schedule_status_label.configure(text="Select a resource to see when it is booked.", text_color=MUTED)
            return
        selected = resources[resource_listbox.index(selection[0])]
        slots = get_resource_schedule(selected["resource_id"])

        busy_now = next((slot for slot in slots if slot["in_progress"]), None)
        if busy_now:
            text = f"{selected['name']} is in use right now, until {busy_now['end']}."
        else:
            text = f"{selected['name']} is free right now."
        if slots:
            text += f" {len(slots)} booking{'' if len(slots) == 1 else 's'} still to come or in progress:"
        else:
            text += " No upcoming bookings - any time within campus hours is open."
        schedule_status_label.configure(text=text, text_color=WARNING if busy_now else SUCCESS)

        for slot in slots:
            schedule_table.insert(
                "", "end",
                values=(slot["date"], f"{slot['start']} - {slot['end']}", f"{slot['minutes']} min"),
                tags=("inprogress" if slot["in_progress"] else "upcoming",),
            )

    def submit_cancel():
        selection = bookings_listbox.selection()
        if not selection:
            messagebox.showerror("Error", "Please select a booking to cancel.")
            return
        selected_booking = my_bookings[bookings_listbox.index(selection[0])]
        # cancel_booking() double-checks this booking actually belongs to this
        # lecturer before touching it - so no one can cancel someone else's booking
        # even if they somehow guessed a valid booking id
        success, message = cancel_booking(selected_booking["booking_id"], user.user_id)
        if success:
            messagebox.showinfo("Success", message)
            refresh_bookings()
            refresh_resource_now()   # the slot is free again straight away
            refresh_schedule()
        else:
            messagebox.showerror("Error", message)

    make_button(bookings_card, "Cancel Selected Booking", submit_cancel, style="danger")

    refresh_bookings()  # fill the table in as soon as the dashboard opens

    def auto_refresh_availability():
        """Keeps 'Right now', the booked slots and the booking states current
        while the dashboard sits open (a booking can start or finish, or
        another lecturer can book something). Same 15-second idea as the
        admin/operator dashboards. All three refreshes keep the current
        selection, so this never interrupts someone mid-click."""
        if resources_card.winfo_exists():
            refresh_resource_now()
            refresh_schedule()
            refresh_bookings()
            resources_card.after(15000, auto_refresh_availability)

    resources_card.after(15000, auto_refresh_availability)


# ---------------------------------------------------------------------------
# SYSTEM OPERATOR DASHBOARD
# ---------------------------------------------------------------------------

def build_operator_view(dashboard, user, resources_metric_label=None, bookings_metric_label=None):
    """The System Operator sees everything, across every campus - all
    resources, all bookings, and a report comparing the campuses against
    each other. No editing powers here, this role is read-only/reporting."""
    layout = Frame(dashboard, fg_color="transparent")
    layout.pack(fill="both", expand=True, padx=10)
    left = Frame(layout, fg_color="transparent")
    right = Frame(layout, fg_color="transparent")
    left.pack(side="left", fill="both", expand=True, padx=(0, 8))
    right.pack(side="left", fill="both", expand=True, padx=(8, 0))

    resources_card = make_card(left, "All Resources")
    resources_listbox = make_table(resources_card, [("campus", "Campus"), ("code", "Code"), ("resource", "Resource"), ("status", "Status")], height=10)

    bookings_card = make_card(right, "All Bookings")
    bookings_listbox = make_table(bookings_card, [("campus", "Campus"), ("resource", "Resource"), ("lecturer", "Lecturer"), ("when", "When"), ("status", "Status")], height=10)

    def refresh_tables_and_metrics():
        # the operator never adds/edits anything themselves, but lecturers
        # and admins at any campus can be changing things in the background
        # while this dashboard sits open, so these tables (and the "Total
        # resources" / "Total bookings" numbers up top) need to be able to
        # move on their own too, not just stay frozen at whatever they were
        # when the dashboard first opened
        resources_listbox.delete(*resources_listbox.get_children())
        all_resources = get_all_resources()
        for r in all_resources:
            resources_listbox.insert("", "end", values=(r['campus_name'], r['resource_code'], r['name'], r['status'].title()), tags=(r['status'].lower(),))
        if resources_metric_label is not None:
            resources_metric_label.configure(text=str(len(all_resources)))

        bookings_listbox.delete(*bookings_listbox.get_children())
        all_bookings = get_all_bookings()
        for b in all_bookings:
            state = booking_state(b)
            bookings_listbox.insert("", "end", values=(b['campus_name'], b['resource_name'], b['lecturer_name'], f"{b['booking_date']} · {b['start_time']}", state), tags=(state_tag(state),))
        if bookings_metric_label is not None:
            bookings_metric_label.configure(text=str(len(all_bookings)))

    # --- Resource usage across campuses (brief 7.2) ---
    usage_card = make_card(left, "Resource Usage Across Campuses")
    usage_chart = make_chart_canvas(usage_card, height=260)
    usage_label = Label(usage_card, text="", justify="left", font=LABEL_FONT, text_color=PARCHMENT, anchor="w", wraplength=440)
    usage_label.pack(fill="x", padx=18, pady=(0, 16))

    def show_resource_usage():
        usage = get_resource_usage_by_campus()            # dict: {campus: {resource type: bookings}}
        shared, unique = compare_resource_types(usage)    # set maths on the types each campus offers
        campus_names = list(usage)

        # the chart: one row per resource type, split into one segment per campus.
        # A set collects every type any campus has, busiest types first.
        all_types = set()
        for by_type in usage.values():
            all_types |= set(by_type)
        rows = [(t, {campus: usage[campus].get(t, 0) for campus in campus_names}) for t in all_types]
        rows.sort(key=lambda row: (-sum(row[1].values()), row[0]))
        draw_stacked_bar_chart(usage_chart, rows, campus_names, "Bookings by resource type")

        # the yes/no facts (which types exist where) read better as text than as a chart
        lines = ["Offered at every campus: " + (", ".join(sorted(shared)) or "none")]
        for campus_name, only_here in unique.items():
            if only_here:
                lines.append(f"Only at {campus_name}: " + ", ".join(sorted(only_here)))
        usage_label.configure(text="\n".join(lines))

    # --- Cross-campus insights: numbers next to the rules that shaped them ---
    report_card = make_card(right, "Cross-Campus Insights")
    report_label = Label(report_card, text="Generate a report to compare campus activity.", justify="left", font=BODY_FONT, text_color=MUTED, anchor="w", wraplength=440)
    report_label.pack(fill="x", padx=18, pady=(0, 10))
    comparison_chart = make_chart_canvas(report_card, height=205)

    def show_cross_report():
        comparison = get_campus_comparison()              # list of dicts, one per campus
        lines = []
        for c in comparison:
            # a campus with zero bookings has avg_duration = None, not 0 -
            # can't round(None), so check for that first
            avg = f"{round(c['avg_duration'])} min" if c["avg_duration"] is not None else "N/A"
            line = f"{c['name']}  ({c['policy']})\n    {c['total_bookings']} booking{'' if c['total_bookings'] == 1 else 's'} · avg {avg} · {c['cancelled_bookings']} cancelled"
            if c["cap_usage_percent"] is not None:
                line += f" · avg uses {c['cap_usage_percent']}% of cap"
            lines.append(line)
        lines.append("")
        lines.append("What the campus rules changed:")
        lines.extend(f"  - {sentence}" for sentence in summarise_rule_impact(comparison))
        report_label.configure(text="\n".join(lines))
        draw_bar_chart(comparison_chart, [(c["name"], c["total_bookings"]) for c in comparison], "Bookings by campus", SUCCESS)
        show_resource_usage()

    make_button(report_card, "Generate Comparison Report", show_cross_report, style="primary")

    def auto_refresh_cross_report():
        # same idea as the admin dashboard's auto-refresh - keeps this screen
        # accurate every 15 seconds without the operator having to click Generate
        if report_card.winfo_exists():
            refresh_tables_and_metrics()
            show_cross_report()
            report_card.after(15000, auto_refresh_cross_report)

    refresh_tables_and_metrics()  # fill both tables in as soon as the dashboard opens
    show_resource_usage()         # ...and the resource usage summary too
    # the canvas has no real width until the window is actually on screen, so
    # draw the chart a second time just after it appears
    usage_card.after(300, show_resource_usage)
    report_card.after(15000, auto_refresh_cross_report)


# ---------------------------------------------------------------------------
# DASHBOARD ROUTER - decides which dashboard to build based on the role
# ---------------------------------------------------------------------------

def open_dashboard(user):
    """Runs right after a successful login. Closes the login window,
    opens a fresh dashboard window, and builds whichever screen matches
    this user's role (Admin / Lecturer / Operator all look completely
    different). Whoever calls this closes the previous window first."""
    dashboard = tk.Tk()
    dashboard.title(f"{user.role_name()} Dashboard")
    dashboard.geometry("1120x720")
    dashboard.minsize(900, 620)
    dashboard.configure(bg=INK)
    configure_table_style(dashboard)

    # everything goes inside this scrollable frame instead of directly on the
    # window, so the page can be taller than the screen without cutting content off
    content = make_scrollable(dashboard)

    # top header: name + role on the left, a Logout button on the right
    header = Frame(content, fg_color="transparent")
    header.pack(fill="x", padx=15, pady=(12, 12))
    greeting = Frame(header, fg_color="transparent")
    greeting.pack(side="left", fill="x", expand=True)
    Label(greeting, text=f"Welcome back, {user.full_name.split()[0]}", font=HEADING_FONT, text_color=PARCHMENT, anchor="w").pack(fill="x")
    # showing which campus this account belongs to - Lecturers and Admins are
    # tied to one campus each, but a System Operator isn't (they see all of
    # them), so this falls back to "ALL CAMPUSES" for that role
    if user.campus_id:
        active_campus_name = f"ACTIVE CAMPUS: {get_campus(user.campus_id)['name'].upper()}"
    else:
        active_campus_name = "ALL CAMPUSES"
    Label(greeting, text=f"SMART CAMPUS  /  {user.role_name().upper()}  ·  {active_campus_name}", font=("Segoe UI", 10, "bold"), text_color=BRASS, anchor="w").pack(fill="x", pady=(2, 0))
    Label(header, text="Resource Booking", font=("Cambria", 16, "bold"), text_color=MUTED).pack(side="right", padx=8)
    Button(
        header, text="Logout", command=lambda: logout(dashboard),
        fg_color="transparent", hover_color=PANEL_LIGHT, border_width=1, border_color=BRICK,
        text_color=BRICK, font=LABEL_FONT, corner_radius=8, width=80,
    ).pack(side="right", padx=8)
    # only roles allowed to roam between campuses (Lecturers) get this -
    # it goes back to the campus selection step without logging out
    if user.can_select_any_campus():
        Button(
            header, text="Switch Campus", command=lambda: switch_campus(dashboard, user),
            fg_color="transparent", hover_color=PANEL_LIGHT, border_width=1, border_color=BRASS,
            text_color=BRASS, font=LABEL_FONT, corner_radius=8, width=110,
        ).pack(side="right", padx=8)

    # the 3 stat boxes at the top - different numbers depending on the role,
    # since an admin cares about their campus, a lecturer cares about their
    # own bookings, and an operator cares about everything institution-wide.
    # make_metric() hands back the number label itself so we can update it
    # later - these start as None for metrics no view ever needs to refresh
    # (e.g. "Maximum minutes" never changes while the dashboard is open).
    metrics = Frame(content, fg_color="transparent")
    metrics.pack(fill="x", padx=15, pady=(0, 18))
    resources_metric_label = available_metric_label = bookings_metric_label = None
    if isinstance(user, CampusAdministrator):
        resources = get_all_resources_by_campus(user.campus_id)
        bookings = get_bookings_by_campus(user.campus_id)
        resources_metric_label = make_metric(metrics, len(resources), "Total resources")
        available_metric_label = make_metric(metrics, sum(r["status"] == "available" for r in resources), "Available now", SUCCESS)
        bookings_metric_label = make_metric(metrics, len(bookings), "Campus bookings")
    elif isinstance(user, Lecturer):
        resources = get_resources_by_campus(user.campus_id)
        bookings = get_bookings_by_lecturer(user.user_id)
        make_metric(metrics, len(resources), "Resources available", SUCCESS)
        # same "currently held, not ever made" logic as refresh_bookings()
        # in build_lecturer_view - see the comment there for why
        active_booking_count = sum(1 for b in bookings if booking_state(b) in ("Upcoming", "In progress"))
        bookings_metric_label = make_metric(metrics, active_booking_count, "Active bookings")
        make_metric(metrics, get_campus(user.campus_id)["max_duration_minutes"] or "∞", "Maximum minutes", WARNING)
    else:
        resources = get_all_resources()
        bookings = get_all_bookings()
        make_metric(metrics, len(get_all_campuses()), "Campuses")
        resources_metric_label = make_metric(metrics, len(resources), "Total resources")
        bookings_metric_label = make_metric(metrics, len(bookings), "Total bookings", SUCCESS)

    # this is the actual "which role am I" check that decides the rest of the
    # screen - isinstance() works here because of the class inheritance set up
    # in models.py (Lecturer/CampusAdministrator/SystemOperator all inherit
    # from the same base User class, but each one is still its own type)
    if isinstance(user, CampusAdministrator):
        build_admin_resource_form(content, user, resources_metric_label, available_metric_label, bookings_metric_label)
    elif isinstance(user, Lecturer):
        build_lecturer_view(content, user, bookings_metric_label)
    elif isinstance(user, SystemOperator):
        build_operator_view(content, user, resources_metric_label, bookings_metric_label)

    dashboard.mainloop()


# ---------------------------------------------------------------------------
# REGISTRATION - only lecturers can self-register, per the assignment brief
# ---------------------------------------------------------------------------

def open_register_window():
    """Opens the registration popup on top of the login window. Only ever
    creates a lecturer account - admin/operator accounts get set up
    separately, they're not meant to be something anyone can sign up for."""
    register_win = tk.Toplevel(window)
    register_win.title("Register New Lecturer Account")
    register_win.geometry("380x580")
    register_win.configure(bg=INK)

    # A popup window doesn't always come to the front on its own (it can open
    # BEHIND the login window depending on the OS/window manager) - these
    # three calls force it to the front, give it keyboard focus, and stop
    # clicks from reaching the login window underneath until this popup is
    # closed.
    register_win.transient(window)
    register_win.lift()
    register_win.focus_force()
    register_win.grab_set()

    card = Frame(register_win, fg_color=PANEL, corner_radius=16, border_width=1, border_color=BORDER)
    card.pack(expand=True, fill="both", padx=20, pady=20)

    Label(card, text="Register", font=HEADING_FONT, text_color=BRASS).pack(pady=(20, 15))

    reg_name_entry = make_field(card, "Full Name")
    reg_username_entry = make_field(card, "Choose a Username (3+ characters, no spaces)")
    reg_password_entry_label = Label(card, text="Choose a Password (6+ characters)", font=LABEL_FONT, text_color=MUTED, anchor="w")
    reg_password_entry_label.pack(fill="x", padx=18, pady=(4, 0))
    reg_password_entry = Entry(
        card, show="*", fg_color=PANEL_LIGHT, border_color=BORDER, text_color=PARCHMENT,
        font=BODY_FONT, corner_radius=8,
    )
    reg_password_entry.pack(fill="x", padx=18, pady=(2, 10))

    # asked twice because the box hides what you type - a typo here would
    # otherwise lock the new user out of their own account
    Label(card, text="Confirm Password", font=LABEL_FONT, text_color=MUTED, anchor="w").pack(
        fill="x", padx=18, pady=(4, 0)
    )
    reg_confirm_entry = Entry(
        card, show="*", fg_color=PANEL_LIGHT, border_color=BORDER, text_color=PARCHMENT,
        font=BODY_FONT, corner_radius=8,
    )
    reg_confirm_entry.pack(fill="x", padx=18, pady=(2, 10))

    Label(card, text="Select Your Campus", font=LABEL_FONT, text_color=MUTED, anchor="w").pack(
        fill="x", padx=18, pady=(4, 0)
    )
    # pulling the real campus list from the database instead of hardcoding
    # names here, so if a campus gets added later this dropdown just works
    campuses = get_all_campuses()
    campus_names = [c["name"] for c in campuses]
    selected_campus = tk.StringVar(register_win)
    selected_campus.set(campus_names[0])
    Dropdown(
        card, variable=selected_campus, values=campus_names,
        fg_color=PANEL_LIGHT, button_color=BRASS,
        text_color=PARCHMENT,
    ).pack(fill="x", padx=18, pady=(2, 14))

    def submit_registration():
        full_name = reg_name_entry.get().strip()
        username = reg_username_entry.get().strip()
        password = reg_password_entry.get()

        if not full_name or not username or not password:
            messagebox.showerror("Error", "All fields are required.")
            return
        if password != reg_confirm_entry.get():
            messagebox.showerror("Error", "The two passwords don't match.")
            return

        # the dropdown only gives me back a campus NAME as text, so this
        # looks back through the campuses list to find the matching campus_id
        campus_id = next(c["campus_id"] for c in campuses if c["name"] == selected_campus.get())

        success, message = create_user(username, password, "lecturer", full_name, campus_id)
        if success:
            messagebox.showinfo("Success", message)
            register_win.destroy()
        else:
            messagebox.showerror("Registration Failed", message)

    make_button(card, "Register", submit_registration, style="primary")


# ---------------------------------------------------------------------------
# CAMPUS SELECTION - the step after login (brief sections 3.1 and 4.1)
# ---------------------------------------------------------------------------

def show_campus_selection(user):
    """Shown to a Lecturer right after they log in: pick which campus to work
    at. The dropdown starts on their home campus, and choosing a different
    one immediately shows THAT campus's booking policy, so they can see the
    rules before committing. Whatever they pick becomes user.campus_id, which
    is what the rest of the app (resources list, bookings, policy rules) uses."""
    global window
    window = tk.Tk()
    window.title("Select Campus")
    window.geometry("460x540")
    window.configure(bg=INK)
    configure_table_style(window)

    card = Frame(window, fg_color=PANEL, corner_radius=16, border_width=1, border_color=BORDER)
    card.pack(expand=True, fill="both", padx=30, pady=30)

    Label(card, text="Select a Campus", font=HEADING_FONT, text_color=BRASS).pack(pady=(26, 4))
    Label(
        card,
        text=f"Welcome, {user.full_name.split()[0]}. Choose the campus you want to work with - "
             "its own booking rules will apply automatically.",
        font=LABEL_FONT, text_color=MUTED, wraplength=340, justify="center",
    ).pack(padx=20, pady=(0, 18))

    campuses = get_all_campuses()
    campus_by_name = {c["name"]: c for c in campuses}   # dict: campus name -> its row
    selected_name = tk.StringVar(window)
    home = get_campus(user.home_campus_id) if user.home_campus_id else None
    selected_name.set(home["name"] if home else campuses[0]["name"])

    Label(card, text="Campus", font=LABEL_FONT, text_color=MUTED, anchor="w").pack(fill="x", padx=18)
    policy_label = Label(
        card, text="", font=LABEL_FONT, text_color=PARCHMENT, anchor="w", justify="left", wraplength=340,
    )

    def show_policy(choice=None):
        # runs whenever the dropdown changes (and once at the start) so the
        # policy shown always matches the campus currently selected
        policy = BookingPolicy.from_campus(campus_by_name[selected_name.get()])
        policy_label.configure(text=policy.describe())

    Dropdown(
        card, variable=selected_name, values=list(campus_by_name), command=show_policy,
        fg_color=PANEL_LIGHT, button_color=BRASS,
        text_color=PARCHMENT,
    ).pack(fill="x", padx=18, pady=(2, 14))
    policy_label.pack(fill="x", padx=18, pady=(0, 16))
    show_policy()

    def confirm_campus():
        user.select_campus(campus_by_name[selected_name.get()]["campus_id"])
        window.destroy()
        open_dashboard(user)

    make_button(card, "Continue", confirm_campus, style="primary")
    window.mainloop()


def switch_campus(dashboard, user):
    """The Switch Campus button on the Lecturer dashboard: closes the
    dashboard and goes back to the campus selection step (no re-login needed)."""
    dashboard.destroy()
    show_campus_selection(user)


# ---------------------------------------------------------------------------
# LOGIN
# ---------------------------------------------------------------------------

def check_login():
    """Runs when the Login button is clicked. Looks the username up first -
    if it doesn't exist, stop there. Only if the account exists do I bother
    checking the password against its stored hash."""
    # .strip() so an accidental trailing space doesn't lock someone out, and
    # the lookup ignores capitals (usernames are case-insensitive, matching
    # how create_user() refuses "Bob" when "bob" already exists)
    username = username_entry.get().strip()
    password = password_entry.get()

    if not username or not password:
        messagebox.showerror("Login Failed", "Please enter both your username and password.")
        return

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (username,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        messagebox.showerror("Login Failed", "No account with that username.")
        return

    if not verify_password(password, row["password_hash"], row["salt"]):
        messagebox.showerror("Login Failed", "Incorrect password.")
        return

    # create_user_object() looks at the role stored in the database row and
    # wraps it in the right class (Lecturer/CampusAdministrator/SystemOperator) -
    # that class is what decides which dashboard shows up next
    user = create_user_object(row)
    window.destroy()  # close the login window
    # Brief section 4.1: after a successful login the user selects a campus.
    # Lecturers can work at any campus, so they get the selection screen.
    # Admins are tied to the one campus they manage and Operators work across
    # all campuses, so for them there's nothing to choose - their campus (or
    # "ALL CAMPUSES") is shown clearly in the dashboard header instead.
    if user.can_select_any_campus():
        show_campus_selection(user)
    else:
        open_dashboard(user)


def build_login_window():
    """Builds the login screen. This is its own function (not just code
    sitting at the bottom of the file) because I need to be able to call it
    again after someone logs out - not just once when the app starts."""
    global window, username_entry, password_entry

    window = tk.Tk()
    window.title("Smart Campus Resource Booking System")
    window.geometry("420x480")
    window.configure(bg=INK)
    configure_table_style(window)

    login_card = Frame(window, fg_color=PANEL, corner_radius=16, border_width=1, border_color=BORDER)
    login_card.pack(expand=True, padx=30, pady=40, fill="both")

    Label(login_card, text="Smart Campus", font=HEADING_FONT, text_color=BRASS).pack(pady=(30, 0))
    Label(login_card, text="Resource Booking System", font=LABEL_FONT, text_color=MUTED).pack(pady=(0, 25))

    username_entry = make_field(login_card, "Username")
    password_entry_label = Label(login_card, text="Password", font=LABEL_FONT, text_color=MUTED, anchor="w")
    password_entry_label.pack(fill="x", padx=18, pady=(4, 0))
    password_entry = Entry(
        login_card, show="*", fg_color=PANEL_LIGHT, border_color=BORDER, text_color=PARCHMENT,
        font=BODY_FONT, corner_radius=8,
    )
    password_entry.pack(fill="x", padx=18, pady=(2, 20))

    make_button(login_card, "Login", check_login, style="primary")
    Button(
        login_card, text="Register New Account", command=open_register_window,
        fg_color="transparent", hover_color=PANEL_LIGHT, border_width=1, border_color=BRASS,
        text_color=BRASS, font=BODY_FONT, corner_radius=8,
    ).pack(fill="x", padx=18, pady=(0, 20))

    window.mainloop()


def logout(dashboard):
    """Closes whichever dashboard is open and takes the user back to a
    fresh login screen, instead of having to close and reopen the whole
    program to switch accounts."""
    dashboard.destroy()
    build_login_window()


def run_app():
    """Starts the application by opening the login window. Called from
    main.py - kept as its own function (instead of a bare call sitting at
    the bottom of the file) so gui.py can be imported elsewhere, e.g. by
    tests, without a Tkinter window popping up as a side effect."""
    build_login_window()


if __name__ == "__main__":
    # lets this file still be run directly during development
    # (python gui.py) as well as via main.py
    run_app()
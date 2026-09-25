"""
main.py
Smart Campus Resource Booking System - GUI entry point.

Design system:
  Ink Navy (#10192B)    - window / app background
  Panel (#1B273F)       - card backgrounds
  Panel Light (#24314D) - input field backgrounds
  Brass (#C7A252)       - primary accent, primary action buttons
  Brass Hover (#B08F42) - primary button hover state
  Brick (#B0524A)       - destructive/negative action buttons (cancel, remove)
  Parchment (#EDE6D6)   - primary text
  Muted (#9AA4B8)       - secondary/helper text
  Sage (#7FA97A)        - success/available accents

  Headings : Cambria (serif)   - gives an institutional, "printed" feel
  Body     : Segoe UI (sans)   - clean, always available on Windows

Layout: each dashboard section is its own bordered card, left-aligned,
rather than plain centered text with "--- divider ---" labels.
"""

import tkinter as tk
from tkinter import messagebox, ttk
import customtkinter as ctk

from database import (
    get_connection, add_resource, get_resources_by_campus,
    create_booking, get_campus, get_bookings_by_lecturer, cancel_booking,
    get_bookings_by_campus, get_all_resources_by_campus, set_resource_status,
    create_user, get_all_campuses, get_campus_report,
    get_cross_campus_report, get_all_resources, get_all_bookings,
)
from auth import verify_password
from models import create_user_object, CampusAdministrator, Lecturer, SystemOperator

# ---------------------------------------------------------------------------
# DESIGN TOKENS
# ---------------------------------------------------------------------------

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

HEADING_FONT = ("Cambria", 20, "bold")
CARD_TITLE_FONT = ("Cambria", 15, "bold")
BODY_FONT = ("Segoe UI", 12)
LABEL_FONT = ("Segoe UI", 11)
BUTTON_FONT = ("Segoe UI", 12, "bold")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def configure_table_style(root):
    """Give ttk.Treeview the same visual language as the CTk screens."""
    style = ttk.Style(root)
    style.theme_use("clam")
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
    metric = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=12, border_width=1, border_color=BORDER)
    metric.pack(side="left", fill="x", expand=True, padx=5)
    ctk.CTkLabel(metric, text=str(value), font=("Cambria", 25, "bold"), text_color=accent).pack(
        anchor="w", padx=16, pady=(13, 0)
    )
    ctk.CTkLabel(metric, text=label, font=("Segoe UI", 10), text_color=MUTED).pack(
        anchor="w", padx=16, pady=(0, 13)
    )


def make_card(parent, title):
    """A bordered, titled section card - replaces plain '--- text ---' dividers
    with an actual visual grouping."""
    card = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=14, border_width=1, border_color=BORDER)
    card.pack(fill="x", padx=20, pady=(0, 16))
    ctk.CTkLabel(card, text=title, font=CARD_TITLE_FONT, text_color=BRASS, anchor="w").pack(
        fill="x", padx=18, pady=(16, 8)
    )
    return card


def make_field(card, label_text):
    """A left-aligned label + entry pair, styled to match the theme."""
    ctk.CTkLabel(card, text=label_text, font=LABEL_FONT, text_color=MUTED, anchor="w").pack(
        fill="x", padx=18, pady=(4, 0)
    )
    entry = ctk.CTkEntry(
        card, fg_color=PANEL_LIGHT, border_color=BORDER, text_color=PARCHMENT,
        font=BODY_FONT, corner_radius=8,
    )
    entry.pack(fill="x", padx=18, pady=(2, 10))
    return entry


def make_button(card, text, command, style="primary"):
    """A themed button. style='primary' (brass, for confirm/create actions)
    or style='danger' (brick, for cancel/remove actions)."""
    colors = {
        "primary": (BRASS, BRASS_HOVER, INK),
        "danger": (BRICK, BRICK_HOVER, PARCHMENT),
    }
    fg, hover, text_color = colors[style]
    btn = ctk.CTkButton(
        card, text=text, command=command, font=BUTTON_FONT,
        fg_color=fg, hover_color=hover, text_color=text_color, corner_radius=8,
    )
    btn.pack(fill="x", padx=18, pady=(4, 16))
    return btn


def make_listbox(parent, width=50, height=6):
    """A tk.Listbox styled to match the theme, since CustomTkinter has no
    built-in list widget of its own."""
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
    """A readable, headed table for resource and booking records."""
    wrap = ctk.CTkFrame(parent, fg_color=PANEL_LIGHT, corner_radius=8)
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
    return tree


def make_chart_canvas(parent, height=190):
    """A lightweight canvas chart: no extra plotting package is required."""
    canvas = tk.Canvas(parent, height=height, bg=PANEL, highlightthickness=0, bd=0)
    canvas.pack(fill="x", padx=18, pady=(2, 12))
    return canvas


def draw_bar_chart(canvas, data, title, color=BRASS):
    """Draw a small responsive bar chart from [(label, value), ...]."""
    canvas.delete("all")
    canvas.update_idletasks()
    width = max(canvas.winfo_width(), 360)
    height = int(canvas.cget("height"))
    left, right, top, bottom = 42, 16, 28, 38
    plot_width, plot_height = width - left - right, height - top - bottom
    canvas.create_text(0, 6, text=title.upper(), anchor="nw", fill=MUTED, font=("Segoe UI", 9, "bold"))
    if not data or max(value for _, value in data) == 0:
        canvas.create_text(width / 2, height / 2, text="No report data yet", fill=MUTED, font=BODY_FONT)
        return
    maximum = max(value for _, value in data)
    for step in range(3):
        y = top + plot_height * step / 2
        canvas.create_line(left, y, width - right, y, fill=BORDER, width=1)
        canvas.create_text(left - 7, y, text=str(round(maximum * (2 - step) / 2)), anchor="e", fill=MUTED, font=("Segoe UI", 8))
    gap = 12
    bar_width = max(22, (plot_width - gap * (len(data) + 1)) / len(data))
    for index, (label, value) in enumerate(data):
        x1 = left + gap + index * (bar_width + gap)
        x2 = x1 + bar_width
        y2 = top + plot_height
        y1 = y2 - (value / maximum * plot_height)
        canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="")
        canvas.create_text((x1 + x2) / 2, y1 - 8, text=str(value), fill=PARCHMENT, font=("Segoe UI", 9, "bold"))
        short_label = label if len(label) <= 12 else label[:11] + "…"
        canvas.create_text((x1 + x2) / 2, y2 + 15, text=short_label, fill=MUTED, font=("Segoe UI", 8))


def draw_donut_chart(canvas, values, title):
    """Draw a compact availability/status donut with a legend."""
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
        extent = 360 * value / total
        canvas.create_arc(x1, y1, x2, y2, start=start, extent=-extent, fill=color, outline=PANEL, width=3, style="pieslice")
        start -= extent
    canvas.create_oval(55, 67, 118, 130, fill=PANEL, outline=PANEL)
    canvas.create_text(86, 88, text=str(total), fill=PARCHMENT, font=("Cambria", 18, "bold"))
    canvas.create_text(86, 110, text="TOTAL", fill=MUTED, font=("Segoe UI", 8, "bold"))
    legend_x = 185
    for index, (label, value, color) in enumerate(values):
        y = 54 + index * 34
        canvas.create_oval(legend_x, y, legend_x + 10, y + 10, fill=color, outline="")
        canvas.create_text(legend_x + 17, y + 5, text=label, anchor="w", fill=PARCHMENT, font=("Segoe UI", 10))
        canvas.create_text(width - 6, y + 5, text=str(value), anchor="e", fill=PARCHMENT, font=("Segoe UI", 10, "bold"))




# ---------------------------------------------------------------------------
# CAMPUS ADMINISTRATOR DASHBOARD
# ---------------------------------------------------------------------------

def build_admin_resource_form(dashboard, user):
    layout = ctk.CTkFrame(dashboard, fg_color="transparent")
    layout.pack(fill="both", expand=True, padx=10)
    left = ctk.CTkFrame(layout, fg_color="transparent")
    right = ctk.CTkFrame(layout, fg_color="transparent")
    left.pack(side="left", fill="both", expand=True, padx=(0, 8))
    right.pack(side="left", fill="both", expand=True, padx=(8, 0))

    card = make_card(left, "Add a New Resource")
    code_entry = make_field(card, "Resource Code (e.g. CT-LAB-02)")
    name_entry = make_field(card, "Resource Name")
    type_entry = make_field(card, "Resource Type (Lab / Projector / Room)")

    def submit_resource():
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
            code_entry.delete(0, tk.END)
            name_entry.delete(0, tk.END)
            type_entry.delete(0, tk.END)
            refresh_resources()
            show_report()
        else:
            messagebox.showerror("Error", message)

    make_button(card, "Add Resource", submit_resource, style="primary")

    bookings_card = make_card(right, "Campus Bookings")
    campus_bookings_listbox = make_table(bookings_card, [
        ("resource", "Resource"), ("lecturer", "Lecturer"), ("date", "Date"), ("time", "Time"), ("status", "Status"),
    ], height=8)

    def refresh_campus_bookings():
        campus_bookings_listbox.delete(*campus_bookings_listbox.get_children())
        for b in get_bookings_by_campus(user.campus_id):
            campus_bookings_listbox.insert("", "end", values=(b['resource_name'], b['lecturer_name'], b['booking_date'], f"{b['start_time']} · {b['duration_minutes']} min", b['status'].title()), tags=(b['status'].lower(),))

    manage_card = make_card(left, "Manage Resources")
    manage_listbox = make_table(manage_card, [("code", "Code"), ("name", "Name"), ("type", "Type"), ("status", "Status")], height=7)

    all_resources = []

    def refresh_resources():
        nonlocal all_resources
        manage_listbox.delete(*manage_listbox.get_children())
        all_resources = get_all_resources_by_campus(user.campus_id)
        for r in all_resources:
            manage_listbox.insert("", "end", values=(r['resource_code'], r['name'], r['resource_type'], r['status'].title()), tags=(r['status'].lower(),))

    def toggle_status(new_status):
        selection = manage_listbox.selection()
        if not selection:
            messagebox.showerror("Error", "Please select a resource first.")
            return
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

    report_card = make_card(right, "Campus Insights")
    report_label = ctk.CTkLabel(report_card, text="Generate a report to see your campus activity.", justify="left", font=BODY_FONT, text_color=MUTED, anchor="w")
    report_label.pack(fill="x", padx=18, pady=(0, 10))
    usage_chart = make_chart_canvas(report_card)
    availability_chart = make_chart_canvas(report_card, height=170)

    def show_report():
        report = get_campus_report(user.campus_id)
        report_text = (
            f"{report['total_bookings']} bookings recorded · most used: {report['most_used_resource']} · "
            f"average duration: {report['avg_duration']} min"
        )
        report_label.configure(text=report_text)
        bookings = get_bookings_by_campus(user.campus_id)
        usage = {}
        for booking in bookings:
            usage[booking["resource_name"]] = usage.get(booking["resource_name"], 0) + 1
        draw_bar_chart(usage_chart, sorted(usage.items(), key=lambda item: item[1], reverse=True)[:5], "Bookings by resource")
        resources = get_all_resources_by_campus(user.campus_id)
        available = sum(resource["status"] == "available" for resource in resources)
        draw_donut_chart(availability_chart, [("Available", available, SUCCESS), ("Unavailable", len(resources) - available, BRICK)], "Resource availability")

    make_button(report_card, "Generate Report", show_report, style="primary")

    def auto_refresh_report():
        """Keep an open dashboard accurate when data changes in the database."""
        if report_card.winfo_exists():
            show_report()
            report_card.after(15000, auto_refresh_report)

    report_card.after(15000, auto_refresh_report)

    campus = get_campus(user.campus_id)
    if campus["priority_override"]:
        priority_card = make_card(left, "Priority Booking (Override)")
        ctk.CTkLabel(
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

    refresh_campus_bookings()
    refresh_resources()


# ---------------------------------------------------------------------------
# LECTURER DASHBOARD
# ---------------------------------------------------------------------------

def build_lecturer_view(dashboard, user):
    layout = ctk.CTkFrame(dashboard, fg_color="transparent")
    layout.pack(fill="both", expand=True, padx=10)
    left = ctk.CTkFrame(layout, fg_color="transparent")
    right = ctk.CTkFrame(layout, fg_color="transparent")
    left.pack(side="left", fill="both", expand=True, padx=(0, 8))
    right.pack(side="left", fill="both", expand=True, padx=(8, 0))

    resources_card = make_card(left, "Available Resources")
    resource_listbox = make_table(resources_card, [("code", "Code"), ("resource", "Resource"), ("type", "Type")], height=8)

    resources = get_resources_by_campus(user.campus_id)
    for r in resources:
        resource_listbox.insert("", "end", values=(r['resource_code'], r['name'], r['resource_type']))

    campus = get_campus(user.campus_id)
    policy_text = f"Policy: max {campus['max_duration_minutes']} min, hours {campus['open_hour']}:00-{campus['close_hour']}:00"
    if campus["max_duration_minutes"] == 0:
        policy_text = f"Policy: no duration cap, hours {campus['open_hour']}:00-{campus['close_hour']}:00"
    ctk.CTkLabel(resources_card, text=policy_text, font=LABEL_FONT, text_color=MUTED, anchor="w").pack(
        fill="x", padx=18, pady=(0, 14)
    )

    booking_card = make_card(right, "Book Selected Resource")
    date_entry = make_field(booking_card, "Date (YYYY-MM-DD)")
    time_entry = make_field(booking_card, "Start Time (HH:MM, 24hr)")
    duration_entry = make_field(booking_card, "Duration (minutes)")

    bookings_card = make_card(left, "My Bookings")
    bookings_listbox = make_table(bookings_card, [("resource", "Resource"), ("date", "Date"), ("time", "Time"), ("status", "Status")], height=7)

    my_bookings = []

    def refresh_bookings():
        nonlocal my_bookings
        bookings_listbox.delete(*bookings_listbox.get_children())
        my_bookings = get_bookings_by_lecturer(user.user_id)
        for b in my_bookings:
            line = f"#{b['booking_id']} | {b['resource_name']} | {b['booking_date']} {b['start_time']} ({b['duration_minutes']}min) | {b['status']}"
            bookings_listbox.insert("", "end", values=(b['resource_name'], b['booking_date'], f"{b['start_time']} · {b['duration_minutes']} min", b['status'].title()), tags=(b['status'].lower(),))

    def submit_booking():
        selection = resource_listbox.selection()
        if not selection:
            messagebox.showerror("Error", "Please select a resource from the list first.")
            return
        selected_resource = resources[resource_listbox.index(selection[0])]
        try:
            duration = int(duration_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Duration must be a whole number of minutes.")
            return

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
            refresh_bookings()
        else:
            messagebox.showerror("Booking Failed", message)

    make_button(booking_card, "Book Resource", submit_booking, style="primary")

    def submit_cancel():
        selection = bookings_listbox.selection()
        if not selection:
            messagebox.showerror("Error", "Please select a booking to cancel.")
            return
        selected_booking = my_bookings[bookings_listbox.index(selection[0])]
        success, message = cancel_booking(selected_booking["booking_id"], user.user_id)
        if success:
            messagebox.showinfo("Success", message)
            refresh_bookings()
        else:
            messagebox.showerror("Error", message)

    make_button(bookings_card, "Cancel Selected Booking", submit_cancel, style="danger")

    refresh_bookings()


# ---------------------------------------------------------------------------
# SYSTEM OPERATOR DASHBOARD
# ---------------------------------------------------------------------------

def build_operator_view(dashboard, user):
    layout = ctk.CTkFrame(dashboard, fg_color="transparent")
    layout.pack(fill="both", expand=True, padx=10)
    left = ctk.CTkFrame(layout, fg_color="transparent")
    right = ctk.CTkFrame(layout, fg_color="transparent")
    left.pack(side="left", fill="both", expand=True, padx=(0, 8))
    right.pack(side="left", fill="both", expand=True, padx=(8, 0))
    resources_card = make_card(left, "All Resources")
    resources_listbox = make_table(resources_card, [("campus", "Campus"), ("code", "Code"), ("resource", "Resource"), ("status", "Status")], height=10)
    for r in get_all_resources():
        resources_listbox.insert("", "end", values=(r['campus_name'], r['resource_code'], r['name'], r['status'].title()), tags=(r['status'].lower(),))

    bookings_card = make_card(right, "All Bookings")
    bookings_listbox = make_table(bookings_card, [("campus", "Campus"), ("resource", "Resource"), ("lecturer", "Lecturer"), ("when", "When"), ("status", "Status")], height=10)
    for b in get_all_bookings():
        bookings_listbox.insert("", "end", values=(b['campus_name'], b['resource_name'], b['lecturer_name'], f"{b['booking_date']} · {b['start_time']}", b['status'].title()), tags=(b['status'].lower(),))

    report_card = make_card(right, "Cross-Campus Insights")
    report_label = ctk.CTkLabel(report_card, text="Generate a report to compare campus activity.", justify="left", font=BODY_FONT, text_color=MUTED, anchor="w")
    report_label.pack(fill="x", padx=18, pady=(0, 10))
    comparison_chart = make_chart_canvas(report_card, height=205)

    def show_cross_report():
        lines = []
        for row in get_cross_campus_report():
            avg = round(row["avg_duration"], 1) if row["avg_duration"] is not None else "N/A"
            lines.append(f"{row['name']}: {row['total_bookings']} bookings, avg duration {avg} min")
        report_label.configure(text="\n".join(lines))
        draw_bar_chart(comparison_chart, [(row["name"], row["total_bookings"]) for row in get_cross_campus_report()], "Bookings by campus", SUCCESS)

    make_button(report_card, "Generate Comparison Report", show_cross_report, style="primary")

    def auto_refresh_cross_report():
        if report_card.winfo_exists():
            show_cross_report()
            report_card.after(15000, auto_refresh_cross_report)

    report_card.after(15000, auto_refresh_cross_report)


# ---------------------------------------------------------------------------
# DASHBOARD ROUTER
# ---------------------------------------------------------------------------

def open_dashboard(user):
    window.destroy()

    dashboard = ctk.CTk()
    dashboard.title(f"{user.role_name()} Dashboard")
    dashboard.geometry("1120x720")
    dashboard.minsize(900, 620)
    dashboard.configure(fg_color=INK)
    configure_table_style(dashboard)

    content = ctk.CTkScrollableFrame(dashboard, fg_color=INK)
    content.pack(fill="both", expand=True, padx=10, pady=10)

    header = ctk.CTkFrame(content, fg_color="transparent")
    header.pack(fill="x", padx=15, pady=(12, 12))
    greeting = ctk.CTkFrame(header, fg_color="transparent")
    greeting.pack(side="left", fill="x", expand=True)
    ctk.CTkLabel(greeting, text=f"Welcome back, {user.full_name.split()[0]}", font=HEADING_FONT, text_color=PARCHMENT, anchor="w").pack(fill="x")
    ctk.CTkLabel(greeting, text=f"SMART CAMPUS  /  {user.role_name().upper()}", font=("Segoe UI", 10, "bold"), text_color=BRASS, anchor="w").pack(fill="x", pady=(2, 0))
    ctk.CTkLabel(header, text="Resource Booking", font=("Cambria", 16, "bold"), text_color=MUTED).pack(side="right", padx=8)
    ctk.CTkButton(
        header, text="Logout", command=lambda: logout(dashboard),
        fg_color="transparent", hover_color=PANEL_LIGHT, border_width=1, border_color=BRICK,
        text_color=BRICK, font=LABEL_FONT, corner_radius=8, width=80,
    ).pack(side="right", padx=8)

    metrics = ctk.CTkFrame(content, fg_color="transparent")
    metrics.pack(fill="x", padx=15, pady=(0, 18))
    if isinstance(user, CampusAdministrator):
        resources = get_all_resources_by_campus(user.campus_id)
        bookings = get_bookings_by_campus(user.campus_id)
        make_metric(metrics, len(resources), "Total resources")
        make_metric(metrics, sum(r["status"] == "available" for r in resources), "Available now", SUCCESS)
        make_metric(metrics, len(bookings), "Campus bookings")
    elif isinstance(user, Lecturer):
        resources = get_resources_by_campus(user.campus_id)
        bookings = get_bookings_by_lecturer(user.user_id)
        make_metric(metrics, len(resources), "Resources available", SUCCESS)
        make_metric(metrics, len(bookings), "My bookings")
        make_metric(metrics, get_campus(user.campus_id)["max_duration_minutes"] or "∞", "Maximum minutes", WARNING)
    else:
        resources = get_all_resources()
        bookings = get_all_bookings()
        make_metric(metrics, len(get_all_campuses()), "Campuses")
        make_metric(metrics, len(resources), "Total resources")
        make_metric(metrics, len(bookings), "Total bookings", SUCCESS)

    if isinstance(user, CampusAdministrator):
        build_admin_resource_form(content, user)
    elif isinstance(user, Lecturer):
        build_lecturer_view(content, user)
    elif isinstance(user, SystemOperator):
        build_operator_view(content, user)

    dashboard.mainloop()


# ---------------------------------------------------------------------------
# REGISTRATION
# ---------------------------------------------------------------------------

def open_register_window():
    register_win = ctk.CTkToplevel(window)
    register_win.title("Register New Lecturer Account")
    register_win.geometry("380x480")
    register_win.configure(fg_color=INK)

    card = ctk.CTkFrame(register_win, fg_color=PANEL, corner_radius=16, border_width=1, border_color=BORDER)
    card.pack(expand=True, fill="both", padx=20, pady=20)

    ctk.CTkLabel(card, text="Register", font=HEADING_FONT, text_color=BRASS).pack(pady=(20, 15))

    reg_name_entry = make_field(card, "Full Name")
    reg_username_entry = make_field(card, "Choose a Username")
    reg_password_entry_label = ctk.CTkLabel(card, text="Choose a Password", font=LABEL_FONT, text_color=MUTED, anchor="w")
    reg_password_entry_label.pack(fill="x", padx=18, pady=(4, 0))
    reg_password_entry = ctk.CTkEntry(
        card, show="*", fg_color=PANEL_LIGHT, border_color=BORDER, text_color=PARCHMENT,
        font=BODY_FONT, corner_radius=8,
    )
    reg_password_entry.pack(fill="x", padx=18, pady=(2, 10))

    ctk.CTkLabel(card, text="Select Your Campus", font=LABEL_FONT, text_color=MUTED, anchor="w").pack(
        fill="x", padx=18, pady=(4, 0)
    )
    campuses = get_all_campuses()
    campus_names = [c["name"] for c in campuses]
    selected_campus = tk.StringVar(register_win)
    selected_campus.set(campus_names[0])
    ctk.CTkOptionMenu(
        card, variable=selected_campus, values=campus_names,
        fg_color=PANEL_LIGHT, button_color=BRASS, button_hover_color=BRASS_HOVER,
        text_color=PARCHMENT, dropdown_fg_color=PANEL_LIGHT,
    ).pack(fill="x", padx=18, pady=(2, 14))

    def submit_registration():
        full_name = reg_name_entry.get().strip()
        username = reg_username_entry.get().strip()
        password = reg_password_entry.get()

        if not full_name or not username or not password:
            messagebox.showerror("Error", "All fields are required.")
            return

        campus_id = next(c["campus_id"] for c in campuses if c["name"] == selected_campus.get())

        success, message = create_user(username, password, "lecturer", full_name, campus_id)
        if success:
            messagebox.showinfo("Success", message)
            register_win.destroy()
        else:
            messagebox.showerror("Registration Failed", message)

    make_button(card, "Register", submit_registration, style="primary")


# ---------------------------------------------------------------------------
# LOGIN
# ---------------------------------------------------------------------------

def check_login():
    username = username_entry.get()
    password = password_entry.get()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        messagebox.showerror("Login Failed", "No account with that username.")
        return

    if not verify_password(password, row["password_hash"], row["salt"]):
        messagebox.showerror("Login Failed", "Incorrect password.")
        return

    user = create_user_object(row)
    open_dashboard(user)


def build_login_window():
    """Builds (or rebuilds, after logout) the login screen."""
    global window, username_entry, password_entry

    window = ctk.CTk()
    window.title("Smart Campus Resource Booking System")
    window.geometry("420x480")
    window.configure(fg_color=INK)
    configure_table_style(window)

    login_card = ctk.CTkFrame(window, fg_color=PANEL, corner_radius=16, border_width=1, border_color=BORDER)
    login_card.pack(expand=True, padx=30, pady=40, fill="both")

    ctk.CTkLabel(login_card, text="Smart Campus", font=HEADING_FONT, text_color=BRASS).pack(pady=(30, 0))
    ctk.CTkLabel(login_card, text="Resource Booking System", font=LABEL_FONT, text_color=MUTED).pack(pady=(0, 25))

    username_entry = make_field(login_card, "Username")
    password_entry_label = ctk.CTkLabel(login_card, text="Password", font=LABEL_FONT, text_color=MUTED, anchor="w")
    password_entry_label.pack(fill="x", padx=18, pady=(4, 0))
    password_entry = ctk.CTkEntry(
        login_card, show="*", fg_color=PANEL_LIGHT, border_color=BORDER, text_color=PARCHMENT,
        font=BODY_FONT, corner_radius=8,
    )
    password_entry.pack(fill="x", padx=18, pady=(2, 20))

    make_button(login_card, "Login", check_login, style="primary")
    ctk.CTkButton(
        login_card, text="Register New Account", command=open_register_window,
        fg_color="transparent", hover_color=PANEL_LIGHT, border_width=1, border_color=BRASS,
        text_color=BRASS, font=BODY_FONT, corner_radius=8,
    ).pack(fill="x", padx=18, pady=(0, 20))

    window.mainloop()


def logout(dashboard):
    dashboard.destroy()
    build_login_window()


build_login_window()
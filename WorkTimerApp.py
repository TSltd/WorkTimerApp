import traceback
import os
import sys
import time
import datetime
import re
import tkinter as tk
from tkinter import filedialog, simpledialog
import pystray
from pystray import MenuItem as item, Icon
from PIL import Image
import threading
import base64
import io

# Base64 encoded icon data (PNG format)
CHILL_ICON = "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAX0lEQVR4nGPU0FD9z0ABYMEmeP36LayKNTXV8BtwHaoRm0Jc8owwL4AkcWnEZhBMLRMDhYCJVNtBAKQW5h0mqriAEsA0TAzQRApVuqcDRuTMRFFSxqYQHWAzGKsBpAAA13krZK9ro5MAAAAASUVORK5CYII="

WORK_ICON = "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAhElEQVR4nM2S0Q3AIAhElbiKDew/DE07TBsTaZCgtfGn71OOO1EiYr7CAsk7ZD5cMdE2NuDa6Al79SgjlKIu7Hw2zUi5MRJtsim20Z5rowJ46W8UrYwDM+kjDYRF4F8GaF7Yw/0FUq86w3APsCaMFknzbKI4y416ybbeGFihxTN2Db5wA1dOPWheOcEiAAAAAElFTkSuQmCC"

# Log everything from the start
with open("error_log.txt", "w") as f:
    f.write("Debugging started:\n")


# Function to log to the error log file
def log_to_file(message):
    with open("error_log.txt", "a") as f:
        f.write(f"{message}\n")


try:

    class WorkTimerApp:
        def __init__(self, root):
            self.root = root
            self.root.title("Work Timer")

            # Get screen dimensions
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()

            # Get the window dimensions
            window_width = 175  # Adjust as necessary
            window_height = 85  # Adjust as necessary

            # Calculate the x and y position to place the window at the bottom right
            x_position = (
                screen_width - window_width - 10
            )  # 10 pixels margin from the right
            y_position = (
                screen_height - window_height - 60
            )  # 60 pixels margin from the bottom

            # Set the window's position and size
            self.root.geometry(
                f"{window_width}x{window_height}+{x_position}+{y_position}"
            )

            self.root.overrideredirect(True)  # Remove window frame
            self.root.configure(bg="#2E2E2E")  # Dark background
            self.root.attributes("-topmost", True)  # Keep window on top

            # Make window draggable
            self.root.bind("<ButtonPress-1>", self.start_move)
            self.root.bind("<B1-Motion>", self.do_move)

            self.logged_sessions_today = set()
            config_file = os.path.expanduser("~/.work_timer_config")
            self.log_directory = None

            if os.path.exists(config_file):
                with open(config_file, "r") as f:
                    saved_directory = f.read().strip()
                    if os.path.exists(saved_directory):
                        self.log_directory = saved_directory
                    else:
                        self.select_save_location()
            else:
                self.select_save_location()

            if not self.log_directory:
                print("No save location selected. Exiting...")
                root.quit()
                return

            with open(config_file, "w") as f:
                f.write(self.log_directory)

            os.makedirs(self.log_directory, exist_ok=True)
            self.project_name = tk.StringVar()
            self.project_name.set("Default Project")
            self.load_last_project()

            self.timer_running = False
            self.start_time = None
            self.elapsed_time = tk.StringVar()
            self.elapsed_time.set("00:00:00")
            self.daily_totals = {}
            self.log_file = self.get_current_week_log_filename()
            self.load_existing_logs()  # Recalculate totals from the log file

            self.weekly_total = datetime.timedelta(0)

            self.sessions_today = set()

            self.session_logged = False

            self.create_widgets()
            self.create_tray_icon()

            # Schedule periodic log updates every minute (60000ms)
            self.update_log_periodically()

        def create_widgets(self):
            # Frame for organizing widgets
            frame = tk.Frame(self.root, bg="#2E2E2E", bd=2, relief="ridge")
            frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            # "Project:" label and text entry in the same row (row 0)
            tk.Label(frame, text="Project:", fg="white", bg="#2E2E2E").grid(
                row=0, column=0, padx=5, pady=5, sticky="e"
            )
            self.project_entry = tk.Entry(
                frame,
                textvariable=self.project_name,
                width=15,
                bg="#3C3C3C",
                fg="white",
                insertbackground="white",
            )
            self.project_entry.grid(row=0, column=1, padx=5, pady=5)

            # Start/Stop button and timer display in the same row (row 1)
            self.start_stop_button = tk.Button(
                frame,
                text="Start",
                command=self.toggle_timer,
                bg="#444",
                fg="white",
                relief="raised",
            )
            self.start_stop_button.grid(row=1, column=0, padx=5, pady=5)

            # Timer label in the same row (row 1), aligned to the right side of the cell (column 1)
            tk.Label(
                frame,
                textvariable=self.elapsed_time,
                font=("Arial", 14),
                fg="white",
                bg="#2E2E2E",
            ).grid(
                row=1, column=1, padx=5, pady=5, sticky="w"
            )  # Align to the left of the cell

            # Set column weights for better resizing and preventing overflow
            frame.grid_columnconfigure(0, weight=1, minsize=50)
            frame.grid_columnconfigure(1, weight=3, minsize=50)

        def start_move(self, event):
            if event.widget not in [self.project_entry, self.start_stop_button]:
                self.x = event.x_root - self.root.winfo_x()
                self.y = event.y_root - self.root.winfo_y()

        def do_move(self, event):
            if event.widget not in [self.project_entry, self.start_stop_button]:
                self.root.geometry(f"+{event.x_root - self.x}+{event.y_root - self.y}")

        def stop_move(self, event):
            pass  # Prevent moving while interacting with widgets

        def toggle_timer(self):
            if self.timer_running:
                self.stop_timer()
                self.tray_icon.icon = self.not_working_icon
            else:
                self.start_timer()
                self.tray_icon.icon = self.working_icon

        def create_log_file(self):
            """Ensures that the log file for the current week exists and is initialized."""
            # Get the current date and week start
            now = datetime.datetime.now()
            week_start = now - datetime.timedelta(days=now.weekday())

            # Define the log file path
            log_file = os.path.join(
                self.log_directory, f"work_hours_{week_start.strftime('%d-%m-%Y')}.txt"
            )

            # Check if the log file already exists
            if not os.path.exists(log_file):
                # If the file doesn't exist, create a new one
                try:
                    with open(log_file, "w") as f:
                        # Write a header or initialization message
                        f.write(
                            "Work Hours Log - Week Starting: "
                            + week_start.strftime("%d-%m-%Y")
                            + "\n"
                        )
                        f.write("---------------------------------------------------\n")

                    print(f"New log file created: {log_file}")
                except Exception as e:
                    print(f"Error creating log file: {e}")
            else:
                print(f"Log file already exists: {log_file}")

            # After creating or finding the log file, call write_day_log to ensure today's log entry is there
            today_date = now.strftime("%d/%m/%Y")  # Format today’s date
            self.write_day_log(log_file, today_date)  # Call write_day_log here

            return log_file  # Return the log file path

        def update_log_periodically(self):
            """Update the log file every minute to preserve the current session in case of a crash."""
            print(
                f"Checking timer state: Running: {self.timer_running}, Start Time: {self.start_time}"
            )  # Debug
            if not self.timer_running or not self.start_time:
                print(
                    "Skipping log update, either timer is not running or no start time."
                )  # Debug
                return

            # Update the log file with the current session
            # The update_log_file method already checks for duplicates
            print("Updating log file with current session...")
            self.update_log_file()

            # Schedule the next update after 60 seconds, but only if the timer is still running
            if self.timer_running:
                self.root.after(60000, self.update_log_periodically)

        def update_log_file(self):
            """Update the log file with the current session, updating an existing entry if possible."""
            if not self.timer_running or not self.start_time:
                return

            current_time = time.time()
            start_time_dt = datetime.datetime.fromtimestamp(self.start_time).replace(
                second=0, microsecond=0
            )
            end_time_dt = datetime.datetime.fromtimestamp(current_time).replace(
                second=0, microsecond=0
            )

            session_start_time = start_time_dt.strftime("%H:%M")
            session_end_time = end_time_dt.strftime("%H:%M")
            session_duration = self.format_time(end_time_dt - start_time_dt)
            project_name = self.project_name.get()

            # New log entry
            log_entry = f"- {session_start_time} - {session_end_time} (Project: {project_name}) ({session_duration})"

            log_file = self.get_current_week_log_filename()

            try:
                if not os.path.exists(log_file):
                    self.create_log_file()

                # Read the current log file
                with open(log_file, "r") as f:
                    lines = f.readlines()

                # Find today's date in the log file
                today_date = datetime.datetime.now().strftime("%d/%m/%Y")
                date_index = -1
                next_date_index = len(lines)

                # Find today's date and the next date (if any)
                for i, line in enumerate(lines):
                    if line.strip() == today_date:
                        date_index = i
                        # Now find the next date or end of file
                        for j in range(i + 1, len(lines)):
                            if re.match(r"\d{2}/\d{2}/\d{4}", lines[j].strip()):
                                next_date_index = j
                                break
                        break

                # If we didn't find today's date, add it to the end
                if date_index < 0:
                    lines.append(f"\n{today_date}\n")
                    date_index = len(lines) - 1
                    next_date_index = len(lines)

                # Find all session entries for today
                today_sessions = []
                for i in range(date_index + 1, next_date_index):
                    line = lines[i].strip()
                    if line.startswith("-"):
                        # Check if this is for the current session (same start time)
                        if f"- {session_start_time} -" in line:
                            # Found an existing entry for this session, update it
                            today_sessions.append((i, log_entry))
                            print(f"Updated existing session entry: {log_entry}")
                        else:
                            # Keep the existing session
                            today_sessions.append((i, line))

                # If we didn't find an existing entry for this session, add it
                if not any(
                    f"- {session_start_time} -" in entry for _, entry in today_sessions
                ):
                    today_sessions.append((-1, log_entry))
                    print(f"Added new session entry: {log_entry}")

                # Sort sessions by start time (oldest first)
                today_sessions.sort(
                    key=lambda x: (
                        re.search(r"- (\d{2}:\d{2}) -", x[1]).group(1)
                        if re.search(r"- (\d{2}:\d{2}) -", x[1])
                        else ""
                    )
                )

                # Rebuild the file with sorted sessions
                new_lines = lines[
                    : date_index + 1
                ]  # Everything up to and including today's date

                # Add all sessions in order
                for _, session in today_sessions:
                    new_lines.append(session + "\n")

                # Add everything after today's sessions
                if next_date_index < len(lines):
                    new_lines.extend(lines[next_date_index:])

                # Write the updated lines back to the log file
                with open(log_file, "w") as f:
                    f.writelines(new_lines)

                print(f"Log updated: {log_file}")

            except Exception as e:
                print(f"Error updating log file: {e}")
                traceback.print_exc()  # Print the full traceback for debugging

        def stop_timer(self, end_time=None):
            """Stop the timer and log the session."""
            print("Stopping timer...")
            self.timer_running = False
            end_time = end_time if end_time else time.time()
            end_time_dt = datetime.datetime.fromtimestamp(end_time)

            # Round down to the nearest minute
            end_time_dt = end_time_dt.replace(second=0, microsecond=0)
            end_time = end_time_dt.timestamp()  # Convert back to timestamp

            # Calculate session duration and log it
            # Only log the session once when the timer stops
            duration = self.calculate_duration(self.start_time, end_time)
            self.log_time(duration, end_time)

            # Reset the button and elapsed time display
            self.start_stop_button.config(text="Start")
            self.elapsed_time.set("00:00:00")  # Reset display

            # Get the log file for the current week
            now = datetime.datetime.now()
            week_start = now - datetime.timedelta(days=now.weekday())
            log_file = os.path.join(
                self.log_directory,
                f"work_hours_{week_start.strftime('%d-%m-%Y')}.txt",
            )

            # Update daily and weekly totals **only when stopping the session**
            today_date = now.strftime("%d/%m/%Y")
            self.update_daily_total(log_file, today_date, duration)
            self.update_weekly_total(log_file)

            print("Session logged and updated.")

        def start_timer(self, start_time=None):
            self.timer_running = True
            self.start_time = start_time if start_time else time.time()

            log_file = self.get_current_week_log_filename()
            print(f"Timer started. Log file: {log_file}")

            self.start_stop_button.config(text="Stop")
            self.update_elapsed_time()
            self.update_log_periodically()

        def update_elapsed_time(self):
            if self.timer_running:
                now = datetime.datetime.now()

                # Check if it's 23:59:59 (last second of the day)
                if now.hour == 23 and now.minute == 59 and now.second == 59:
                    print("🔔 Split session at 23:59:59!")

                    # Stop the current session at 23:59:59
                    end_of_day = datetime.datetime.combine(
                        now.date(), datetime.time(23, 59, 59)
                    )
                    self.stop_timer(
                        end_time=end_of_day.timestamp()
                    )  # Log the old session

                    # Start a new session at 00:00:00 (midnight of the new day)
                    midnight = datetime.datetime.combine(
                        now.date() + datetime.timedelta(days=1), datetime.time(0, 0, 0)
                    )
                    self.start_timer(
                        start_time=midnight.timestamp()
                    )  # Log the new session

                    # Reset daily total for the new day
                    self.daily_totals = {midnight.date(): datetime.timedelta(0)}

                # Update elapsed time
                elapsed = time.time() - self.start_time
                self.elapsed_time.set(time.strftime("%H:%M:%S", time.gmtime(elapsed)))
                self.root.after(1000, self.update_elapsed_time)

        def calculate_duration(self, start, end):
            # Duration in seconds
            delta = end - start
            return datetime.timedelta(seconds=delta)

        def log_time(self, duration, end_time):
            now = datetime.datetime.now()
            week_start = now - datetime.timedelta(days=now.weekday())
            log_file = os.path.join(
                self.log_directory, f"work_hours_{week_start.strftime('%d-%m-%Y')}.txt"
            )

            # Convert timestamps to datetime objects
            start_time_dt = datetime.datetime.fromtimestamp(self.start_time)
            end_time_dt = datetime.datetime.fromtimestamp(end_time)

            # Round start and end times down to the nearest minute
            start_time_dt = start_time_dt.replace(second=0, microsecond=0)
            end_time_dt = end_time_dt.replace(second=0, microsecond=0)

            # Calculate duration using the rounded times (not the original times)
            rounded_duration = end_time_dt - start_time_dt

            # Format session log entry
            session_start_time = start_time_dt.strftime("%H:%M")
            session_end_time = end_time_dt.strftime("%H:%M")
            session_duration = self.format_time(rounded_duration)
            log_entry = f"- {session_start_time} - {session_end_time} (Project: {self.project_name.get()}) ({session_duration})"

            # Ensure the log file exists
            if not os.path.exists(log_file):
                with open(log_file, "w") as f:
                    f.write(
                        f"Hours Worked\nWeek commencing {week_start.strftime('%d/%m/%Y')}\n"
                    )

            today_date = now.strftime("%d/%m/%Y")
            self.write_day_log(log_file, today_date)

            # Check for duplicates before writing
            try:
                with open(log_file, "r") as f:
                    lines = [line.strip() for line in f.readlines()]

                existing_sessions = {
                    line.strip() for line in lines if line.startswith("-")
                }

                if log_entry in existing_sessions:
                    print(
                        "Duplicate session detected in log_time, skipping log update."
                    )
                    return

                # Append the session log only if it's not a duplicate
                with open(log_file, "a") as f:
                    f.write(f"{log_entry}\n")

                print(f"Session logged: {log_entry}")

            except Exception as e:
                print(f"Error logging time: {e}")

        def update_daily_total(self, log_file, current_date, duration):
            """Updates the daily total time worked by parsing session times for the current day from the log file."""
            try:
                print(f"\n\n==== UPDATING DAILY TOTAL FOR {current_date} ====")

                # Read the current lines in the log file
                with open(log_file, "r") as f:
                    lines = f.readlines()

                # Print all lines for debugging
                print("\nLog file contents:")
                for i, line in enumerate(lines):
                    print(f"{i}: '{line.strip()}'")

                # Initialize the total time for the day
                total_today = datetime.timedelta(0)

                # APPROACH 1: Find all sessions by directly looking for lines that start with "-"
                # and checking if they're between the current date and the next date/summary
                print("\nAPPROACH 1: Finding sessions by section")

                # Find all sessions for today
                today_sessions = []
                in_today_section = False
                date_line_index = -1

                # First, find the line with today's date
                for i, line in enumerate(lines):
                    line = line.strip()
                    if line == current_date:
                        date_line_index = i
                        print(f"Found exact date match at line {i}: '{line}'")
                        break
                    elif current_date in line and not line.startswith("-"):
                        date_line_index = i
                        print(f"Found partial date match at line {i}: '{line}'")
                        break

                # If we found the date, collect all session entries until the next date or summary
                if date_line_index >= 0:
                    print(f"Starting to collect sessions after line {date_line_index}")
                    for i in range(date_line_index + 1, len(lines)):
                        line = lines[i].strip()

                        # Skip empty lines
                        if not line:
                            continue

                        # If we hit another date or summary, stop collecting
                        if (
                            re.match(r"\d{2}/\d{2}/\d{4}", line)
                            or line.startswith("Total today:")
                            or line.startswith("Total hours this week:")
                        ):
                            print(f"Stopping at line {i}: '{line}'")
                            break

                        # If this is a session entry, add it
                        if line.startswith("-"):
                            today_sessions.append(line)
                            print(f"Added session from line {i}: '{line}'")

                # APPROACH 2: Just find all sessions in the file that match today's date pattern
                # This is a backup approach in case the section-based approach misses something
                print("\nAPPROACH 2: Finding all sessions in the file")
                all_sessions = []
                for i, line in enumerate(lines):
                    line = line.strip()
                    if line.startswith("-"):
                        all_sessions.append((i, line))
                        print(f"Found session at line {i}: '{line}'")

                # Calculate total from all of today's sessions
                print(f"\nProcessing {len(today_sessions)} sessions for today")
                for session in today_sessions:
                    time_info = self.extract_session_time(session)
                    if time_info:
                        total_today += time_info
                        print(
                            f"Added session time: {self.format_time(time_info)}, running total: {self.format_time(total_today)}"
                        )
                    else:
                        print(
                            f"WARNING: Could not extract time from session: '{session}'"
                        )

                print(
                    f"Final daily total from section approach: {self.format_time(total_today)}"
                )

                # APPROACH 3: Use the weekly total calculation method but filter for today's sessions
                # This is the most reliable approach since it uses the same method as the weekly total
                print(
                    "\nAPPROACH 3: Using weekly total method but filtering for today's sessions"
                )

                # First, find the date line index again to make sure we have it
                date_line_index = -1
                for i, line in enumerate(lines):
                    line = line.strip()
                    if line == current_date:
                        date_line_index = i
                        print(f"Found exact date match at line {i}: '{line}'")
                        break
                    elif current_date in line and not line.startswith("-"):
                        date_line_index = i
                        print(f"Found partial date match at line {i}: '{line}'")
                        break

                # If we found the date, find the next date or end of file
                next_date_index = len(lines)
                if date_line_index >= 0:
                    for i in range(date_line_index + 1, len(lines)):
                        line = lines[i].strip()
                        if re.match(r"\d{2}/\d{2}/\d{4}", line):
                            next_date_index = i
                            print(f"Found next date at line {i}: '{line}'")
                            break

                # Now calculate the total using the weekly total method but only for lines between
                # the date line and the next date (or end of file)
                approach3_total = datetime.timedelta(0)
                for i in range(date_line_index + 1, next_date_index):
                    line = lines[i].strip()
                    if line.startswith("-"):  # Session entry
                        session_time = self.extract_session_time(line)
                        if session_time:
                            approach3_total += session_time
                            print(
                                f"Line {i}: Added {self.format_time(session_time)} to approach3 total"
                            )

                print(
                    f"Final daily total from approach 3: {self.format_time(approach3_total)}"
                )

                # Use the approach3 total as our final total since it's the most reliable
                total_today = approach3_total

                # Double-check with the weekly total calculation method
                print("\nDouble-checking with weekly total method:")
                weekly_total = datetime.timedelta(0)
                for i, line in enumerate(lines):
                    line = line.strip()
                    if line.startswith("-"):  # Session entry
                        session_time = self.extract_session_time(line)
                        if session_time:
                            weekly_total += session_time
                            print(
                                f"Line {i}: Added {self.format_time(session_time)} to weekly total"
                            )

                print(f"Weekly total calculation: {self.format_time(weekly_total)}")

                # If today's date wasn't found in the log, add it
                if date_line_index < 0:
                    self.write_day_log(log_file, current_date)

                # Remove any previous total for today if it exists
                new_lines = []
                for line in lines:
                    if "Total today:" not in line:
                        new_lines.append(line)

                # Add the total today at the end of the log file
                new_lines.append(f"\nTotal today: {self.format_time(total_today)}\n")

                # Write the updated lines back into the log file
                with open(log_file, "w") as f:
                    f.writelines(new_lines)

                print(
                    f"Total today updated in {log_file}: {self.format_time(total_today)}"
                )
                print("==== DAILY TOTAL UPDATE COMPLETE ====\n\n")

            except Exception as e:
                print(f"Error updating daily total: {e}")
                traceback.print_exc()  # Print the full traceback for debugging

        def extract_session_time(self, line):
            """Extracts the duration of a session from the log line."""
            # Example line: "- 21:46 - 21:48 (Project: Default Project) (0h 2m)"
            try:
                print(f"Extracting time from line: {line}")

                # Look for the last parenthesized expression which should contain the duration
                match = re.search(r"\(([^)]+)\)$", line.strip())

                if match:
                    time_str = match.group(1)
                    print(f"Found time string: {time_str}")

                    # Use regex to extract hours and minutes
                    hours_match = re.search(r"(\d+)h", time_str)
                    minutes_match = re.search(r"(\d+)m", time_str)

                    hours = int(hours_match.group(1)) if hours_match else 0
                    minutes = int(minutes_match.group(1)) if minutes_match else 0

                    duration = datetime.timedelta(hours=hours, minutes=minutes)
                    print(f"Extracted duration: {self.format_time(duration)}")
                    return duration
                else:
                    # If we can't find the duration at the end, try to extract it from the time range
                    time_range_match = re.search(
                        r"- (\d{2}:\d{2}) - (\d{2}:\d{2})", line
                    )
                    if time_range_match:
                        start_time_str = time_range_match.group(1)
                        end_time_str = time_range_match.group(2)

                        # Parse the time strings
                        start_hour, start_minute = map(int, start_time_str.split(":"))
                        end_hour, end_minute = map(int, end_time_str.split(":"))

                        # Calculate duration in minutes
                        start_minutes = start_hour * 60 + start_minute
                        end_minutes = end_hour * 60 + end_minute

                        # Handle cases where the session crosses midnight
                        if end_minutes < start_minutes:
                            end_minutes += 24 * 60  # Add a day's worth of minutes

                        duration_minutes = end_minutes - start_minutes
                        duration = datetime.timedelta(minutes=duration_minutes)

                        print(
                            f"Extracted duration from time range: {self.format_time(duration)}"
                        )
                        return duration

                print(f"No time format found in line: {line}")
                return datetime.timedelta(0)

            except Exception as e:
                print(f"Error extracting session time from '{line}': {e}")
                traceback.print_exc()  # Print the full traceback for debugging
                return datetime.timedelta(0)  # Return zero on error

        def update_weekly_total(self, log_file):
            """Updates the total work time for the current week in the log file by parsing all session entries."""
            try:
                # Read the current lines in the log file
                with open(log_file, "r") as f:
                    lines = f.readlines()

                # Remove any previous weekly total if it exists
                lines = [line for line in lines if "Total hours this week:" not in line]

                # Initialize the weekly total
                weekly_total = datetime.timedelta(0)

                # Calculate directly from all session entries in the file
                print("Calculating weekly total from all session entries...")
                for line in lines:
                    line = line.strip()
                    if line.startswith("-"):  # Session entry
                        session_time = self.extract_session_time(line)
                        if session_time:
                            weekly_total += session_time
                            print(
                                f"Added to weekly total: {self.format_time(session_time)}"
                            )

                print(
                    f"Final weekly total calculation: {self.format_time(weekly_total)}"
                )

                # Add the weekly total at the end of the log file
                lines.append(
                    f"\nTotal hours this week: {self.format_time(weekly_total)}\n"
                )

                # Write the updated lines back into the log file
                with open(log_file, "w") as f:
                    f.writelines(lines)

                print(
                    f"Weekly total updated in {log_file}: {self.format_time(weekly_total)}"
                )
            except Exception as e:
                print(f"Error updating weekly total: {e}")

        def get_current_week_log_filename(self):
            today = datetime.date.today()
            week_start = today - datetime.timedelta(days=today.weekday())
            return os.path.join(
                self.log_directory, f"work_hours_{week_start.strftime('%d-%m-%Y')}.txt"
            )

        def find_log_file(self):
            """Finds the log file based on the most recent 'Week commencing' entry or defaults to the current week."""
            log_dir = self.log_directory  # Use the actual log directory
            today = datetime.date.today()

            if not log_dir:
                print("Log directory not set. Skipping log search.")
                return None

            # Get the start of the current week (Monday)
            week_start = today - datetime.timedelta(days=today.weekday())

            # Expected filename format
            expected_filename = f"work_hours_{week_start.strftime('%d-%m-%Y')}.txt"
            log_path = os.path.join(log_dir, expected_filename)

            # Check if the log file exists
            if os.path.exists(log_path):
                return log_path  # Found log file

            # If log file doesn't exist, call create_log_file to ensure it's created
            print(
                f"Log file not found: {log_path}. Creating a new log file using create_log_file."
            )

            # Call create_log_file to handle log file creation
            return (
                self.create_log_file()
            )  # This will return the log file path after ensuring it's created

        def load_existing_logs(self):
            """Load existing logs if the file exists, otherwise skip."""
            log_file = self.find_log_file()

            if not log_file:
                return  # Skip if no log file

            try:
                with open(log_file, "r") as file:
                    current_day = None
                    current_day_duration = datetime.timedelta(0)

                    for line in file:
                        line = line.strip()
                        if "Week commencing" in line:
                            continue  # Ignore header lines
                        elif "Total today:" in line:
                            continue  # Ignore summary lines
                        elif line.startswith("-"):
                            # Parse time durations from each session entry
                            match = re.search(r"\((\d+h \d+m)\)", line)
                            if match:
                                session_duration = match.group(1)
                                session_td = self.parse_time(session_duration)
                                current_day_duration += session_td

                    # Store the total for today
                    today_date = datetime.datetime.now().strftime("%d/%m/%Y")
                    self.daily_totals[today_date] = current_day_duration
            except Exception as e:
                print(f"Error loading logs: {e}")

        def write_day_log(self, log_file, today_date):
            # Check if today's date already exists in the file, if not add it
            print(f"write_day_log called for {today_date}")  # Add this print statement

            with open(log_file, "r") as f:
                lines = f.readlines()

            if f"{today_date}\n" not in lines:
                with open(log_file, "a") as f:
                    f.write(f"\n{today_date}\n")

        def parse_time(self, line):
            """Parses a time string like 'Total today: 5h 30m' into a timedelta."""
            try:
                # Extract the time part after the colon
                time_part = line.split(":")[-1].strip()

                # Use regex to extract hours and minutes
                hours_match = re.search(r"(\d+)h", time_part)
                minutes_match = re.search(r"(\d+)m", time_part)

                hours = int(hours_match.group(1)) if hours_match else 0
                minutes = int(minutes_match.group(1)) if minutes_match else 0

                return datetime.timedelta(hours=hours, minutes=minutes)
            except Exception as e:
                print(f"Error parsing time '{line}': {e}")
                return datetime.timedelta(0)  # Return zero duration on error

        def format_time(self, td):
            total_minutes = int(td.total_seconds() // 60)
            hours = total_minutes // 60
            minutes = total_minutes % 60
            return f"{hours}h {minutes}m"

        def load_last_project(self):
            config_file = os.path.join(self.log_directory, "last_project.txt")
            if os.path.exists(config_file):
                with open(config_file, "r") as f:
                    self.project_name.set(f.read().strip())

        def select_save_location(self):
            self.log_directory = filedialog.askdirectory()
            if self.log_directory:
                os.makedirs(self.log_directory, exist_ok=True)

        def hide_window(self):
            self.root.withdraw()

        def show_window(self):
            self.root.deiconify()

        def create_tray_icon(self):
            try:
                # Try to use base64 encoded icons first
                log_to_file("Attempting to load icons from base64 data...")
                try:
                    log_to_file(f"CHILL_ICON length: {len(CHILL_ICON)}")
                    log_to_file(f"WORK_ICON length: {len(WORK_ICON)}")

                    # Decode base64 data
                    log_to_file("Decoding base64 data...")
                    chill_icon_data = base64.b64decode(CHILL_ICON)
                    work_icon_data = base64.b64decode(WORK_ICON)
                    log_to_file(
                        f"Decoded chill_icon_data length: {len(chill_icon_data)}"
                    )
                    log_to_file(f"Decoded work_icon_data length: {len(work_icon_data)}")

                    # Create BytesIO objects
                    log_to_file("Creating BytesIO objects...")
                    chill_bytes = io.BytesIO(chill_icon_data)
                    work_bytes = io.BytesIO(work_icon_data)

                    # Open images
                    log_to_file("Opening images from BytesIO...")
                    self.not_working_icon = Image.open(chill_bytes)
                    self.working_icon = Image.open(work_bytes)
                    log_to_file("Successfully loaded icons from base64 data")
                except Exception as e:
                    log_to_file(f"Error loading icons from base64: {e}")
                    log_to_file(traceback.format_exc())

                    # Fall back to loading from files
                    log_to_file("Falling back to loading icons from files...")
                    script_dir = os.path.dirname(os.path.abspath(__file__))
                    chill_path = os.path.join(script_dir, "icons/chill.ico")
                    work_path = os.path.join(script_dir, "icons/work.ico")

                    log_to_file(f"Loading chill icon from: {chill_path}")
                    log_to_file(f"Loading work icon from: {work_path}")

                    self.not_working_icon = Image.open(chill_path)
                    self.working_icon = Image.open(work_path)
                    log_to_file("Successfully loaded icons from files")

                log_to_file("Creating tray icon...")
                self.tray_icon = Icon(
                    "work_timer", self.not_working_icon, menu=self.create_tray_menu()
                )

                log_to_file("Starting tray icon thread...")
                threading.Thread(target=self.tray_icon.run, daemon=True).start()
                log_to_file("Tray icon thread started")
            except Exception as e:
                log_to_file(f"Error in create_tray_icon: {e}")
                log_to_file(traceback.format_exc())

        def create_tray_menu(self):
            menu = (
                item("Start/Stop", self.toggle_timer),
                item("Select File Save Location", self.select_save_location),
                item("Show/Hide", self.toggle_gui),
                item("View Log", self.open_log_file),
                item("Exit", self.exit_app),
            )
            return menu

        def open_log_file(self):
            """Open the current week's log file in the default text editor."""
            try:
                log_file = self.get_current_week_log_filename()
                if os.path.exists(log_file):
                    # Use the appropriate command based on the OS
                    if os.name == "nt":  # Windows
                        os.startfile(log_file)
                    elif os.name == "posix":  # macOS and Linux
                        import subprocess

                        subprocess.call(
                            ("open", log_file)
                            if sys.platform == "darwin"
                            else ("xdg-open", log_file)
                        )
                    log_to_file(f"Opening log file: {log_file}")
                else:
                    log_to_file(f"Log file not found: {log_file}")
            except Exception as e:
                log_to_file(f"Error opening log file: {e}")
                log_to_file(traceback.format_exc())

        def toggle_gui(self):
            if self.root.state() == "withdrawn":
                self.show_window()
            else:
                self.hide_window()

        def exit_app(self):
            try:
                self.tray_icon.stop()  # Stop the tray icon
            except Exception as e:
                print(f"Error stopping tray icon: {e}")
            self.root.quit()  # Close the Tkinter app

    root = tk.Tk()
    app = WorkTimerApp(root)
    root.mainloop()

except Exception as e:
    with open("error_log.txt", "a") as f:
        f.write("Error during execution:\n")
        f.write(traceback.format_exc())

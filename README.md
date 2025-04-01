# WorkTimerApp

 ![gui_image](/gui.jpg)

WorkTimerApp is a simple and efficient timer application designed to track and log your work hours. It allows you to start and stop timers, automatically logging your sessions into a weekly text-based log file. The app prevents duplicate entries and ensures accurate time tracking.

## Features
- **Start & Stop Timer:** Toggle the timer with a single click.
- **Automatic Logging:** Records sessions in a weekly log file.
- **Daily & Weekly Summaries:** Calculates total work hours per day and week.
- **Project Tracking:** Assign sessions to different projects.
- **Session Splitting at Midnight:** Automatically splits work sessions if they cross midnight.

## Usage
1. Start the application.
2. Click the **Start** button to begin tracking time.
3. Click **Stop** to log the session.
4. The log file is automatically created and updated.
5. View your work log in `logs/` directory.

## Log File Format
The app creates a weekly log file (e.g., `work_hours_31-03-2025.txt`) and records sessions in the following format:
```
Work Hours Log - Week Starting: 31-03-2025
---------------------------------------------------
01/04/2025
- 09:00 - 12:00 (Project: Client A) (3h 0m)
- 13:00 - 15:30 (Project: Client B) (2h 30m)

Total today: 5h 30m

02/04/2025
- 09:00 - 11:00 (Project: Client C) (2h 0m)
- 12:00 - 15:30 (Project: Internal) (3h 30m)

Total today: 5h 30m

Total hours this week: 11h 00m
```


## License
This project is licensed under the MIT License. See `LICENSE` for details.

## Contact
For issues or suggestions, open an issue on [GitHub](https://github.com/your-username/work-hours-logger/issues).


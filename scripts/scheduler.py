from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from time import sleep


def send_notifications():
    # Placeholder: integrate Slack/Twilio here
    print(f"[Scheduler] Sending notifications at {datetime.now().isoformat()}")


def main():
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_notifications, "cron", day_of_week="mon-fri", hour=8, minute=0)
    scheduler.start()
    print("Scheduler started. Press Ctrl+C to stop.")
    try:
        while True:
            sleep(1)
    except KeyboardInterrupt:
        scheduler.shutdown()


if __name__ == "__main__":
    main()

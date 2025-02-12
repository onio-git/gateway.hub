import time
import logging
from datetime import datetime, timedelta


def wait_for_time(event_name, metadata):
    """Wait until the specified time to trigger the event."""
    scheduled_time = metadata.get("scheduled_time")  # Định dạng HH:MM (24 giờ)
    if not scheduled_time:
        raise ValueError("Missing 'scheduled_time' in metadata.")

    logging.info(f"Waiting for scheduled time: {scheduled_time}...")

    while True:
        # Lấy thời gian hiện tại
        now = datetime.now()
        today_scheduled_time = datetime.strptime(scheduled_time, "%H:%M").replace(
            year=now.year, month=now.month, day=now.day
        )

        # Nếu thời gian hiện tại đã qua thời gian lên lịch, chờ đến ngày mai
        if now >= today_scheduled_time:
            logging.info(f"Scheduled time {scheduled_time} already passed today. Waiting for tomorrow...")
            today_scheduled_time += timedelta(days=1)

        # Tính thời gian chờ (giây)
        wait_time = (today_scheduled_time - now).total_seconds()
        logging.info(f"Sleeping for {wait_time / 60:.2f} minutes...")
        time.sleep(wait_time)  # Chờ đến thời điểm đã định

        # Khi đến thời gian, kích hoạt sự kiện
        logging.info(f"Scheduled time {scheduled_time} reached. Triggering event.")
        return {"event_name": "time_triggered", "metadata": metadata}

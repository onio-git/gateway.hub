import time
import logging
def repeat_event(event_name, metadata):
    """Trigger an event every N seconds."""
    interval = metadata.get("interval", 5)  # Thời gian lặp (giây), mặc định là 5 giây
    if interval <= 0:
        raise ValueError("Interval must be greater than 0.")

    logging.info(f"Starting repeat_event with interval: {interval} seconds...")
    time.sleep(interval)
    event_data = {"event_name": event_name, "metadata": metadata}

    return event_data

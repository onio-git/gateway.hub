import time


def wait_for_button(event_name, metadata):
    print(f"Waiting for Philips Hue button press: {event_name} with metadata: {metadata}")
    # Mô phỏng chờ nút nhấn
    time.sleep(2)  # Chờ 2 giây
    return {"event_name": "button_pressed", "metadata": metadata}

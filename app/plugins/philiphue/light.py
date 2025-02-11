def turn_on_light(event, metadata):
    # print(f"Turning on Philips Hue light with event: {event} and metadata: {metadata}")
    print(f"Turning on Philips Hue light-Mac address: {metadata['mac_address']}")
    # Mô phỏng bật đèn
    return {"status": "light_on", "metadata": metadata}

import os
import gpiod
import time
import subprocess

# Determine the script's directory
script_dir = os.path.dirname(os.path.abspath(__file__))

# Paths to main.py and portal.py
main_py = os.path.join(script_dir, 'main.py')
portal_py = os.path.join(script_dir, 'portal.py')

START_AP_PIN = 26

chip = gpiod.Chip('gpiochip4')
line = chip.get_line(START_AP_PIN)
line.request(consumer='manager', type=gpiod.LINE_REQ_DIR_OUT, default_vals=[0])

def is_portal_running():
    result = subprocess.run(['pgrep', '-f', 'portal.py'], stdout=subprocess.PIPE)
    return result.stdout != b''

def start_portal():
    subprocess.run(['python3', portal_py])

def stop_portal():
    subprocess.run(['pkill', '-f', 'portal.py'])

def is_hub_running():
    result = subprocess.run(['pgrep', '-f', 'main.py'], stdout=subprocess.PIPE)
    return result.stdout != b''

def start_hub():
    subprocess.run(['python3', main_py])

def stop_hub():
    subprocess.run(['pkill', '-f', 'main.py'])

def ensure_hub_running():
    """Ensure exactly one instance of the hub is running."""
    if not is_hub_running():
        print("Starting hub...")
        start_hub()

def is_wifi_connected():
    result = subprocess.run(['iwgetid', '-r'], stdout=subprocess.PIPE)
    ssid = result.stdout.decode().strip()
    return ssid != ''


if __name__ == '__main__':
    try:
        while True:
            ensure_hub_running()

            if line.get_value() == 1 and not is_portal_running():
                print("Starting portal...")
                start_portal()
            else:
                print("No reset detected")
            time.sleep(2)  

    except Exception as e:
        print("Error in manager: ", e)
        line.release()
        chip.close()

    except KeyboardInterrupt:
        line.release()
        chip.close()

    finally:
        line.release()
        chip.close()
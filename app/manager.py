import gpiod
import time
import subprocess

START_AP_PIN = 26

chip = gpiod.Chip('gpiochip4')
line = chip.get_line(START_AP_PIN)
line.request(consumer='manager', type=gpiod.LINE_REQ_DIR_OUT, default_vals=[0])

def is_portal_running():
    result = subprocess.run(['pgrep', '-f', 'portal.py'], stdout=subprocess.PIPE)
    return result.stdout != b''

def start_portal():
    subprocess.run(['nohup', 'python3', 'portal.py', '&'])

if __name__ == '__main__':
    try:
        while True:
            if line.get_value() == 1 and not is_portal_running():
                print("Starting portal...")
                start_portal()
            else:
                print("No reset detected")
            time.sleep(2)  

    except Exception as e:
        print("Error in pin manager: ", e)
        line.release()
        chip.close()

    except KeyboardInterrupt:
        line.release()
        chip.close()

    finally:
        line.release()
        chip.close()
# Smart Hub CLI
This is a command-line interface (CLI) tool for controlling a Smart Hub using WiFi. It allows you to configure and interact with the hub via various options.

## Installation
Make sure you have Python installed. Clone this repository and install the required dependencies:

```bash
git clone <repository-url>
cd <repository-directory>
pip install -r requirements.txt
```

## Usage
Run the CLI with the following options

```bash
python main.py [OPTIONS]
```

## Options
--ssid: The SSID of the WiFi network to connect to. (default: '')
--password: The password of the WiFi network to connect to. (default: '')
--log-level: Set the log level. Choices are debug, info, warning, error, critical. (default: 'info')
--serial-number: The serial number of the hub. (default: '')
--auto-scan: Automatically scan for devices. (default: False)
--auto-collect: Automatically collect data from the emulator device. (default: False)

## Example

```bash
python main.py --ssid "MyNetwork" --password "MyPassword" --log-level "debug" --auto-scan --auto-collect
```

## Logging
The application supports different log levels to help with debugging and monitoring:

-Debug: Detailed information, typically of interest only when diagnosing problems.
-Info: Confirmation that things are working as expected.
-Warning: An indication that something unexpected happened, or indicative of some problem in the near future.
-Error: Due to a more serious problem, the software has not been able to perform some function.
-Critical: A serious error, indicating that the program itself may be unable to continue running.

## Configuration
Ensure that your configuration settings are correctly set up in the config/config.py file. This includes default values for the hub's serial number and other settings.
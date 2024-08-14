import configparser
import os
import logging

class ConfigSettings:
    def __init__(self, config_file='config/config.ini'):
        self.config_file = config_file
        self.config = configparser.ConfigParser()

        # Check if the config file exists, and create it if not
        if not os.path.exists(self.config_file):
            logging.warning("Config file not found")
        else:
            self.config.read(self.config_file)


    def get(self, section, option):
        return self.config.get(section, option)

    def set(self, section, option, value):
        self.config.set(section, option, value)
        self.save()

    def save(self):
        with open(self.config_file, 'w') as configfile:
            self.config.write(configfile)
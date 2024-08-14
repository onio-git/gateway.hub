import threading
import time
import importlib
import os
import logging


class PluginInterface:
    def execute(self):
        raise NotImplementedError("Plugins must implement the 'execute' method.")
    



        

    
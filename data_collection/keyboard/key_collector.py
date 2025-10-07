import keyboard
from data_collection.keyboard.key_controller import KeyController

def key_main():
    keyboard.hook(KeyController.handle_event)
    keyboard.wait('esc')

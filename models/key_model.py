from dataclasses import dataclass
from typing import Literal

# Typing for key press events.
# Literal restricts the allowed values to only two: "DOWN" or "UP",
# which makes the code safer and helps prevent logical errors.
EventType = Literal["DOWN", "UP"]

@dataclass(frozen=True, slots=True)
class Key:
    """
    Structure for representing a single user keyboard event.

    This class is used to store all essential information about each key press
    captured during a data collection session.

    Parameters:
        session_id (str): A unique identifier of the current session.
            Allows grouping all events that belong to the same typing session.

        key_name (str): The name of the key (e.g., 'a', 'shift', 'space').
            A symbolic representation of the obtained key.

        event (EventType): The type of event — "DOWN" (pressed) or "UP" (released).
            Used to analyze key press duration and transitions between keys.

        timestamp (int): The time of the event in nanoseconds (Unix time).
            Used for calculating temporal features such as hold time, flight time etc.

        scan_code (int): The hardware scan code of the key, identifying the physical key
            regardless of the keyboard layout. Useful for comparing events across different
            input languages.

        keyboard_layout (str): The code of the active keyboard layout
            (e.g., 'uk-UA', 'en-US'). Determines the language in which the user
            was typing at the time of the event.

        active_window (str): The title of the currently active window where the user is typing.
            Can be used for contextual analysis of typing behavior.

    Class attributes:
        frozen=True — makes the object immutable after creation,
            preventing accidental modification of recorded data.
        slots=True — saves memory and speeds up attribute access
            by creating a fixed set of fields instead of a dynamic dictionary.
    """
    session_id: str
    key_name: str
    event: EventType
    timestamp: int
    scan_code: int
    keyboard_layout: str
    active_window: str

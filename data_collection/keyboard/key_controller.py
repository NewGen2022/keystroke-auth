import os
import time
import ctypes
from ctypes import wintypes
import unicodedata

from models.key_model import Key


class KeyController:
    """
    Controller layer for collecting and shaping keyboard events.

    This class provides static helpers to:
      - read the current input language (keyboard layout) of the foreground thread,
      - read the active window title,
      - build a strongly-typed `Key` event object with precise timestamps.

    All methods are OS-facing (WinAPI) and use `ctypes` to call User32/Kernel32.
    """
    def __init__(self):
        pass

    @staticmethod
    def get_language():
        """
        Return the locale name (e.g., 'en-US') of the foreground thread.

        How it works (WinAPI):
          1) GetForegroundWindow() -> HWND of the focused (input) window.
          2) GetWindowThreadProcessId(HWND, *pid) -> thread id (TID) for that window.
             Note: keyboard layout is attached to THREADS, not globally to the system.
          3) GetKeyboardLayout(TID) -> HKL (keyboard layout handle).
             The lower 16 bits of HKL is the LANGID (language identifier).
          4) LCIDToLocaleName(LANGID, buf, n, 0) -> human-readable locale like 'uk-UA'.

        When resolution fails (short cases):
            - No active window: GetForegroundWindow() returns 0 (no foreground HWND yet).
            - Invalid or system-only thread without a layout: TID belongs to a non-interactive/system thread.
            - LCIDToLocaleName() fails to translate LANGID: rare, e.g., custom/nonstandard layout.
              In all cases we return a fallback like "LANGID_0x0000".

        Returns:
            str: Locale name (e.g., 'en-US').
                 If resolution fails, returns a diagnostic literal like 'LANGID_0x0000'.
        """
        # Load Windows dynamic libraries:
        # user32.dll manages windows, keyboard, and mouse input;
        # kernel32.dll provides core system utilities like memory and locale conversions.
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

        # Declare function signatures so ctypes can correctly pass and interpret
        # arguments and return types between Python and C (WinAPI).
        # This ensures the right data sizes (DWORD, HWND, etc.) are used.

        # GetForegroundWindow returns HWND — a window handle (unique numeric ID for the current window).
        # Used to identify which application is currently active.
        user32.GetForegroundWindow.restype = wintypes.HWND

        # GetWindowThreadProcessId(HWND, *LPDWORD) -> DWORD
        # Retrieves the thread ID that owns the window.
        # Required because keyboard layouts are associated with threads, not processes.
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD

        # GetKeyboardLayout(thread_id) -> HKL
        # HKL is a handle to the keyboard layout, which encodes both the layout and language.
        # c_void_p is used because HKL is an opaque pointer-sized handle.
        user32.GetKeyboardLayout.argtypes = [wintypes.DWORD]
        user32.GetKeyboardLayout.restype = ctypes.c_void_p

        # 1) Get handle to the current foreground window
        hwnd = user32.GetForegroundWindow()

        # 2) Retrieve the thread ID that owns this window.
        # PID (process id) is stored indirectly, but not needed here.
        pid = wintypes.DWORD(0)
        tid = user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        # 3) Obtain the HKL (keyboard layout handle) for this thread.
        # Lower 16 bits of HKL represent the language identifier (LANGID).
        hkl = user32.GetKeyboardLayout(tid)
        lang_id = hkl & 0xFFFF

        # 4) Convert numeric LANGID into human-readable locale name (e.g., "uk-UA")
        # The function LCIDToLocaleName writes the locale string into a buffer.
        buf = ctypes.create_unicode_buffer(85)  # 85 WCHARs is enough per Microsoft documentation.

        # LCIDToLocaleName(LCID, *buffer, buffer_size, flags)
        # Converts a numeric locale identifier (LCID) to a string representation.
        LCIDToLocaleName = kernel32.LCIDToLocaleName
        LCIDToLocaleName.argtypes = [wintypes.DWORD, wintypes.LPWSTR, ctypes.c_int, wintypes.DWORD]
        LCIDToLocaleName.restype = ctypes.c_int # Returns number of written characters or 0 on failure.

        ok = LCIDToLocaleName(lang_id, buf, len(buf), 0)

        # If conversion succeeded, read the string from buffer; otherwise, fallback to hex LANGID.
        locale_name = buf.value if ok else f"LANGID_{lang_id:#06x}"

        return locale_name  # e.g. "en-US"

    # FOR NOW IS NOT USED
    @staticmethod
    def get_wnd_title():
        """
        Return the title (caption) of the current foreground window. (e.g. 'DeepL - Google Chrome')

        How it works (WinAPI):
            - GetForegroundWindow() -> HWND of active window.
            - GetWindowTextLengthW(HWND) -> caption length (without NUL terminator).
            - Allocate buffer of length+1 (room for NUL terminator).
            - GetWindowTextW(HWND, buffer, length+1) -> fill buffer with the title.

        Failure cases (short):
            - No active window (HWND == 0) → return 'no title'.
            - Title length is 0 (untitled/system window) → return 'no title'.
            - GetWindowTextW returns 0 (e.g., security boundary/UAC desktop) → return 'no title'.

        Returns:
            str: Window title if available, otherwise 'no title'.
        """
        user32 = ctypes.WinDLL("user32", use_last_error=True)

        # Signatures creation:
        # GetForegroundWindow -> HWND (focused window handle).
        # Why: identify the window whose title we want.
        user32.GetForegroundWindow.restype = wintypes.HWND

        # GetWindowTextLengthW(HWND) -> int (WCHAR count, no NUL).
        # Why: we must allocate an adequately sized buffer.
        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.GetWindowTextLengthW.restype = ctypes.c_int

        # GetWindowTextW(HWND, LPWSTR, int) -> int (chars copied).
        # Why: copy the title into our Unicode buffer.
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.GetWindowTextW.restype = ctypes.c_int

        # Obtaining active window
        hwnd = user32.GetForegroundWindow()
        title = "no title"

        if hwnd:
            title_len = user32.GetWindowTextLengthW(hwnd) # length without NUL
            if title_len > 0:
                title_len = title_len + 1
                buf = ctypes.create_unicode_buffer(title_len) # include NUL terminator
                if user32.GetWindowTextW(hwnd, buf, title_len): # copy title; 0 means failure
                    title = buf.value

        return title

    @staticmethod
    def get_process_name() -> str:
        """
        Return the executable name (e.g., 'chrome.exe') of the currently active process.

        How it works (WinAPI):
            1) GetForegroundWindow() → HWND (handle to the currently focused window).
            2) GetWindowThreadProcessId(HWND, *pid) → retrieves the Process ID (PID)
               that owns this window.
            3) OpenProcess() → opens a handle to that process with limited read access.
            4) QueryFullProcessImageNameW() → retrieves the full file path to the process image.
               The file name part (e.g., 'chrome.exe') is extracted via os.path.basename().

        Failure cases (short explanations):
            - No active window: GetForegroundWindow() returns 0 → desktop or no focus.
            - OpenProcess() fails: process is protected, elevated (admin/system), or
              not accessible due to privilege boundaries.
            - QueryFullProcessImageNameW() fails: handle lacks read permissions or
              process terminates during the query.
            In all such cases, a fallback string 'unknown.exe' is returned.

        Returns:
            str: The executable name of the active process (e.g., 'chrome.exe').
                 Returns 'unknown.exe' if the process cannot be resolved.
        """

        # Load required Windows DLLs.
        # user32.dll — provides window and input functions.
        # kernel32.dll — gives access to system-level operations like processes and memory.
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

        # Configure function signatures so ctypes knows how to call them correctly.
        # GetForegroundWindow → returns HWND (window handle).
        user32.GetForegroundWindow.restype = wintypes.HWND

        # GetWindowThreadProcessId(HWND, *LPDWORD) → DWORD
        # Retrieves the thread ID and, by reference, the process ID (PID).
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD

        # 1) Get the active window handle.
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return "unknown.exe"  # No active window — likely desktop focus or system state.

        # 2) Retrieve the Process ID (PID) that owns this window.
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        # 3) Open a handle to that process.
        # PROCESS_QUERY_LIMITED_INFORMATION (0x1000) — grants enough rights to query the process name.
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE

        hproc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not hproc:
            # Common if the process is protected or belongs to another user session.
            return "unknown.exe"

        try:
            # 4) Query the full image name (e.g., 'C:\\Program Files\\Google\\Chrome\\chrome.exe').
            kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
            kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL

            # Create a buffer to receive the image path.
            # MAX_PATH (260 characters) is typically enough.
            buf = ctypes.create_unicode_buffer(260)
            size = wintypes.DWORD(len(buf))

            ok = kernel32.QueryFullProcessImageNameW(hproc, 0, buf, ctypes.byref(size))

            # Return the executable file name only (not full path).
            # Example: "chrome.exe" instead of "C:\\Program Files\\Google\\Chrome\\chrome.exe".
            return os.path.basename(buf.value) if ok else "unknown.exe"

        finally:
            # Always close the handle to avoid leaking system resources.
            kernel32.CloseHandle(hproc)

    @staticmethod
    def map_scancode_to_char(scan_code: int) -> str:
        """
        Convert a raw hardware scan code into the actual character
        currently produced by this key in the active (foreground) keyboard layout.

        Returns an empty string for control keys or when no printable symbol can be derived.

        Args:
            scan_code (int): The hardware scan code of the pressed key.

        Logic:
            1) Get the HKL (keyboard layout handle) of the foreground thread.
            2) Convert scan code → virtual-key code using MapVirtualKeyExW().
               (Fallback to MapVirtualKeyW() if needed.)
            3) Retrieve the current modifier key state using GetKeyboardState().
            4) Convert (vk, scan, key_state, layout) → Unicode character via ToUnicodeEx().
        """

        if not scan_code:
            raise ValueError("Scan code needed")

        user32 = ctypes.WinDLL("user32", use_last_error=True)

        # Define function signatures for the needed WinAPI functions
        user32.GetForegroundWindow.restype = wintypes.HWND

        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD

        user32.GetKeyboardLayout.argtypes = [wintypes.DWORD]
        user32.GetKeyboardLayout.restype = wintypes.HKL

        user32.MapVirtualKeyExW.argtypes = [wintypes.UINT, wintypes.UINT, wintypes.HKL]
        user32.MapVirtualKeyExW.restype = wintypes.UINT

        user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
        user32.MapVirtualKeyW.restype = wintypes.UINT

        user32.GetKeyboardState.argtypes = [ctypes.c_void_p]
        user32.GetKeyboardState.restype = wintypes.BOOL

        user32.ToUnicodeEx.argtypes = [
            wintypes.UINT, wintypes.UINT, ctypes.c_void_p,
            wintypes.LPWSTR, ctypes.c_int, wintypes.UINT, wintypes.HKL
        ]
        user32.ToUnicodeEx.restype = ctypes.c_int

        # Mapping modes for MapVirtualKey functions
        MAPVK_VSC_TO_VK_EX = 3
        MAPVK_VSC_TO_VK = 1

        # 1) Obtain HKL (keyboard layout handle) for the foreground thread
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            raise ValueError("Unknown or no foreground window")
        tid = user32.GetWindowThreadProcessId(hwnd, None)
        hkl = user32.GetKeyboardLayout(tid)

        # 2) Convert scan code to virtual-key code
        vk = int(user32.MapVirtualKeyExW(scan_code, MAPVK_VSC_TO_VK_EX, hkl) or 0)
        if vk == 0:
            vk = int(user32.MapVirtualKeyW(scan_code, MAPVK_VSC_TO_VK) or 0)
        if not vk:
            return ""

        # 3) Retrieve the current keyboard state (modifiers like Shift, Ctrl, etc.)
        key_state = (ctypes.c_byte * 256)()
        ok = user32.GetKeyboardState(ctypes.byref(key_state))
        if not ok:
            raise ValueError("Unknown keyboard state")

        # 4) Convert key codes into a character using the active layout
        buf = ctypes.create_unicode_buffer(8)
        res = user32.ToUnicodeEx(
            wintypes.UINT(vk),
            wintypes.UINT(scan_code),
            ctypes.byref(key_state),
            buf,
            ctypes.c_int(len(buf)),
            wintypes.UINT(0),
            hkl
        )

        # res > 0 → buffer contains characters
        # res == 0 → control key (no output)
        # res < 0 → dead key (accent waiting for next letter)
        if res > 0:
            return buf.value
        return ""

    @staticmethod
    def build_key(key):
        """
        Capture and convert a low-level keyboard event into a structured `Key` object.

        This method runs every time a key is pressed or released and records
        the key's physical and contextual data for later behavioral analysis.

        What happens:
            1) Generate a unique session_id (UUIDv4 hex) — links all events in the same session.
            2) Extract event metadata from the keyboard hook:
                - key.name → symbolic key name (e.g., 'a', 'shift')
                - key.event_type → "DOWN" or "UP"
                - key.scan_code → physical key code from the keyboard controller
            3) Record high-resolution time using time.time_ns()
                - measures elapsed nanoseconds since the Unix epoch
                - used for precise hold-time and latency calculations
            4) Capture environment context:
                - keyboard_layout → current input language (if available in event)
                - active_window → current window title (for context)

        Potential failure scenarios:
            - `key.keyboard` may be None if the hook library does not populate layout info.
            - `get_wnd_title()` may return 'no title' if there is no active or untitled window.
            - The system may briefly report inconsistent timestamps under heavy CPU load
              (rare; nanosecond clock drift).

        Args:
            key: A keyboard event object from the listener (must expose
                 `.name`, `.event_type`, `.scan_code`).

        Returns:
            Key: Immutable dataclass instance representing a single key event.
        """

        scan_code = key.scan_code  # Hardware scan code (physical key position)

        key_name = KeyController.map_scancode_to_char(scan_code).strip()  # Logical key name (symbolic form)
        if (not key_name) or (len(key_name) == 1 and unicodedata.category(key_name) == "Cc"):
            key_name = key.name

        event = key.event_type  # Type of event: "DOWN" or "UP"
        timestamp = time.time_ns()  # Nanoseconds since Unix epoch (high precision)
        keyboard_layout = KeyController.get_language()
        active_window = KeyController.get_process_name()

        return Key(
            key_name,
            event,
            timestamp,
            scan_code,
            keyboard_layout,
            active_window,
        )

    @staticmethod
    def handle_event(event) -> None:
        key_obj = KeyController.build_key(event)
        print(key_obj)

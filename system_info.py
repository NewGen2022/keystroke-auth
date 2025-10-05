import json
import os, sys, subprocess, uuid
import getpass
import socket


class SystemInfo:
    def __init__(self):
        self.__device_id = self._get_device_id()
        self.__account_id = self._get_account_id()
        self.__device_name = socket.gethostname()
        self.__username = getpass.getuser()
        self.__platform = sys.platform

    @property
    def device_id(self) -> str: return self.__device_id

    @property
    def account_id(self) -> str: return self.__account_id

    @property
    def device_name(self) -> str: return self.__device_name

    @property
    def username(self) -> str: return self.__username

    # MachineGuid/machine-id
    # унікальний ідентифікатор пристрою, який генерується системою під час інсталяції ОС.
    #
    # змінити можна, але звичайний користувач без адмін-прав не зробить цього просто так.
    @staticmethod
    def _get_device_id() -> str:
        if sys.platform.startswith("win"):
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                    v, _ = winreg.QueryValueEx(key, "MachineGuid")
                    return f"win:{v}"
            except Exception:
                pass
        elif sys.platform.startswith("linux"):
            for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
                try:
                    with open(p, "r") as f:
                        return f"linux:{f.read().strip()}"
                except Exception:
                    pass
        elif sys.platform == "darwin":
            try:
                out = subprocess.check_output(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"], text=True)
                for line in out.splitlines():
                    if "IOPlatformUUID" in line:
                        return "mac:" + line.split('"')[-2]
            except Exception:
                pass
        # Якщо нічого не вдалося → fallback: беремо MAC-адресу
        return "fb_mac:" + str(uuid.getnode())

    # Це унікальний ідентифікатор користувача в Windows.
    # SID прикріплюється до кожного облікового запису, використовується у всіх ACL (дозволах, правах доступу).
    #
    # Змінити не можна, звичайне перейменування облікового запису не чіпає SID.
    #
    # Змінити його можна лише через видалення користувача і створення нового.
    @staticmethod
    def _get_account_id() -> str:
            if sys.platform.startswith("win"):
                # Витягуємо SID без залежності від додаткових бібліотек
                out = subprocess.check_output(["whoami", "/user"], text=True, shell=True)
                # шукаємо рядок з SID типу S-1-5-21-...
                for line in out.splitlines():
                    line = line.strip()
                    if line.startswith("S-1-"):
                        return "sid:" + line
                # Інший формат whoami /user: беремо останню «колонку»
                parts = [p for p in out.split() if p.startswith("S-1-")]
                if parts:
                    return "sid:" + parts[-1]
                return "sid:unknown"
            else:
                try:
                    return "uid:" + str(os.getuid())
                except Exception:
                    return "uid:unknown"

    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "account_id": self.account_id,
            "device_name": self.device_name,
            "username": self.username,
            "platform": self.__platform
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=4, ensure_ascii=False)


if __name__ == "__main__":
    info = SystemInfo()

    print(f"\n{'='*20} Checking static methods {'='*20}")
    print(SystemInfo._get_account_id())
    print(SystemInfo._get_device_id())

    print(f"\n{'='*20} Checking properties {'='*20}")
    print(info.device_id)
    print(info.account_id)
    print(info.device_name)
    print(info.username)

    print(f"\n{'='*20} Checking conversion methods {'='*20}")
    print(info.to_json())
    print(info.to_dict())
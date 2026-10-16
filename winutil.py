"""Windows 전용 보조 기능 (ctypes만 사용, 추가 설치 없음)
- 단일 실행: 이미 실행 중이면 기존 창을 앞으로 불러오고 종료
- 시스템 트레이 아이콘 + 우클릭 메뉴 + 풍선 알림
- 창이 있는 모니터의 작업 영역(작업표시줄 제외) 조회
"""
import ctypes
import os
import struct
import tempfile
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
HWND_MESSAGE = ctypes.c_void_p(-3)
CLASS = "DigiPetTrayWnd"
WM_TRAY = 0x8001   # 트레이 아이콘 콜백
WM_SHOW = 0x8002   # 두 번째 실행이 기존 창을 불러올 때


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HANDLE),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HANDLE),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uID", wintypes.UINT),
                ("uFlags", wintypes.UINT), ("uCallbackMessage", wintypes.UINT), ("hIcon", wintypes.HANDLE),
                ("szTip", wintypes.WCHAR * 128), ("dwState", wintypes.DWORD), ("dwStateMask", wintypes.DWORD),
                ("szInfo", wintypes.WCHAR * 256), ("uVersion", wintypes.UINT),
                ("szInfoTitle", wintypes.WCHAR * 64), ("dwInfoFlags", wintypes.DWORD),
                ("guidItem", ctypes.c_byte * 16), ("hBalloonIcon", wintypes.HANDLE)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD)]


def _sig(fn, restype, *argtypes):
    fn.restype = restype
    fn.argtypes = list(argtypes)


_sig(user32.DefWindowProcW, LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
_sig(user32.RegisterClassW, wintypes.ATOM, ctypes.POINTER(WNDCLASSW))
_sig(user32.CreateWindowExW, wintypes.HWND, wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
     ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE,
     wintypes.LPVOID)
_sig(user32.DestroyWindow, wintypes.BOOL, wintypes.HWND)
_sig(user32.PostMessageW, wintypes.BOOL, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
_sig(user32.FindWindowExW, wintypes.HWND, wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR)
_sig(user32.CreatePopupMenu, wintypes.HMENU)
_sig(user32.AppendMenuW, wintypes.BOOL, wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR)
_sig(user32.TrackPopupMenu, ctypes.c_int, wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int,
     wintypes.HWND, ctypes.c_void_p)
_sig(user32.DestroyMenu, wintypes.BOOL, wintypes.HMENU)
_sig(user32.SetForegroundWindow, wintypes.BOOL, wintypes.HWND)
_sig(user32.GetCursorPos, wintypes.BOOL, ctypes.POINTER(wintypes.POINT))
_sig(user32.LoadImageW, wintypes.HANDLE, wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int,
     ctypes.c_int, wintypes.UINT)
_sig(user32.DestroyIcon, wintypes.BOOL, wintypes.HANDLE)
_sig(user32.MonitorFromWindow, wintypes.HANDLE, wintypes.HWND, wintypes.DWORD)
_sig(user32.GetMonitorInfoW, wintypes.BOOL, wintypes.HANDLE, ctypes.POINTER(MONITORINFO))
_sig(user32.RegisterWindowMessageW, wintypes.UINT, wintypes.LPCWSTR)
_sig(shell32.Shell_NotifyIconW, wintypes.BOOL, wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW))
_sig(kernel32.GetModuleHandleW, wintypes.HMODULE, wintypes.LPCWSTR)
_sig(kernel32.CreateMutexW, wintypes.HANDLE, ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)

_mutex = None


def acquire_single_instance():
    """True: 이 프로세스가 유일한 인스턴스. False: 이미 실행 중(기존 창을 앞으로 불러옴)."""
    global _mutex
    ctypes.set_last_error(0)
    _mutex = kernel32.CreateMutexW(None, False, "Local\\DigiPetPokemonSingleton")
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        hwnd = user32.FindWindowExW(HWND_MESSAGE, None, CLASS, None)
        if hwnd:
            user32.PostMessageW(hwnd, WM_SHOW, 0, 0)
        return False
    return True


def work_area(hwnd):
    """창이 있는 모니터의 작업 영역 (left, top, right, bottom). 작업표시줄 제외."""
    hmon = user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    if hmon and user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
        r = mi.rcWork
        return r.left, r.top, r.right, r.bottom
    return None


def ico_bytes(rows):
    """rows[y][x] = (r, g, b, a) → 32bpp ICO 파일 바이트."""
    h, w = len(rows), len(rows[0])
    xor = bytearray()
    for y in range(h - 1, -1, -1):  # DIB는 아래에서 위로
        for r, g, b, a in rows[y]:
            xor += bytes((b, g, r, a))
    mask = bytes(((w + 31) // 32 * 4) * h)
    bih = struct.pack("<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0, len(xor) + len(mask), 0, 0, 0, 0)
    data = bih + bytes(xor) + mask
    return struct.pack("<HHH", 0, 1, 1) + struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(data), 22) + data


class Tray:
    """시스템 트레이 아이콘. menu_items() -> [(id, 글자, 체크여부) | None(구분선)],
    on_command(id)는 메뉴 선택/좌클릭(1)/더블클릭(2)/두 번째 실행(2) 때 호출."""

    CMD_TOGGLE, CMD_FRONT = 1, 2

    def __init__(self, tooltip, menu_items, on_command):
        self.tooltip, self.menu_items, self.on_command = tooltip, menu_items, on_command
        self.hicon = None
        self._proc = WNDPROC(self._wndproc)  # 참조 유지(GC 방지)
        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSW()
        wc.lpfnWndProc = self._proc
        wc.hInstance = hinst
        wc.lpszClassName = CLASS
        user32.RegisterClassW(ctypes.byref(wc))
        self.hwnd = user32.CreateWindowExW(0, CLASS, "DigiPet", 0, 0, 0, 0, 0, HWND_MESSAGE, None, hinst, None)
        self.taskbar_msg = user32.RegisterWindowMessageW("TaskbarCreated")
        self._notify(0, 0x1 | 0x4)  # NIM_ADD

    def _nid(self, flags):
        n = NOTIFYICONDATAW()
        n.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        n.hWnd = self.hwnd
        n.uID = 1
        n.uFlags = flags | (0x2 if self.hicon else 0)
        n.uCallbackMessage = WM_TRAY
        n.hIcon = self.hicon
        n.szTip = self.tooltip[:127]
        return n

    def _notify(self, msg, flags, **extra):
        n = self._nid(flags)
        for k, v in extra.items():
            setattr(n, k, v)
        shell32.Shell_NotifyIconW(msg, ctypes.byref(n))

    def set_icon(self, rows):
        path = os.path.join(tempfile.gettempdir(), "digipet_tray.ico")
        with open(path, "wb") as f:
            f.write(ico_bytes(rows))
        new = user32.LoadImageW(None, path, 1, len(rows[0]), len(rows), 0x10)  # IMAGE_ICON, LR_LOADFROMFILE
        old, self.hicon = self.hicon, new
        self._notify(1, 0x1 | 0x4)  # NIM_MODIFY
        if old:
            user32.DestroyIcon(old)
        try:
            os.remove(path)
        except OSError:
            pass

    def balloon(self, title, msg):
        """트레이 풍선(토스트) 알림."""
        self._notify(1, 0x10, szInfo=msg[:255], szInfoTitle=title[:63], dwInfoFlags=1)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_TRAY:
                ev = lparam & 0xFFFF
                if ev == 0x202:      # WM_LBUTTONUP
                    self.on_command(self.CMD_TOGGLE)
                elif ev == 0x203:    # WM_LBUTTONDBLCLK
                    self.on_command(self.CMD_FRONT)
                elif ev == 0x205:    # WM_RBUTTONUP
                    self._popup()
                return 0
            if msg == WM_SHOW:
                self.on_command(self.CMD_FRONT)
                return 0
            if msg == self.taskbar_msg:  # 탐색기가 재시작되면 아이콘 다시 등록
                self._notify(0, 0x1 | 0x4)
                return 0
        except Exception:
            pass
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _popup(self):
        menu = user32.CreatePopupMenu()
        for item in self.menu_items():
            if item is None:
                user32.AppendMenuW(menu, 0x800, 0, None)  # MF_SEPARATOR
            else:
                cid, text, checked = item
                user32.AppendMenuW(menu, 0x0 | (0x8 if checked else 0), cid, text)  # MF_STRING | MF_CHECKED
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(self.hwnd)
        # TPM_RIGHTBUTTON | TPM_BOTTOMALIGN | TPM_NONOTIFY | TPM_RETURNCMD
        cmd = user32.TrackPopupMenu(menu, 0x2 | 0x20 | 0x80 | 0x100, pt.x, pt.y, 0, self.hwnd, None)
        user32.PostMessageW(self.hwnd, 0, 0, 0)
        user32.DestroyMenu(menu)
        if cmd:
            self.on_command(cmd)

    def remove(self):
        self._notify(2, 0)  # NIM_DELETE
        if self.hicon:
            user32.DestroyIcon(self.hicon)
            self.hicon = None
        user32.DestroyWindow(self.hwnd)

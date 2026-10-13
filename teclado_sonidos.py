"""Teclado de Sonidos: convierte un teclado numerico USB en una botonera de efectos.

Uso:
    teclado_sonidos.py               arranca (si no hay config.json, abre el asistente)
    teclado_sonidos.py --configurar  vuelve a elegir el teclado
    teclado_sonidos.py --detener     cierra la instancia que esta corriendo

Solo Windows. Solo biblioteca estandar (ctypes + Win32).

Como funciona: un hook global de teclado (WH_KEYBOARD_LL) intercepta las teclas del
bloque numerico y reproduce el sonido asignado, mientras el teclado elegido
(identificado por VID/PID via Raw Input) este conectado y Num Lock este encendido
en el momento de la tecla. Los teclados numericos con Num Lock propio (como el Gear
Head) envuelven sus teclas en "Num Lock, tecla, Num Lock" para que el estado de la
PC coincida con su luz, asi que la luz del teclado funciona como interruptor.
Windows no informa desde que teclado viene una tecla antes de poder bloquearla, por
eso el bloque numerico de CUALQUIER teclado hace sonidos con Num Lock encendido.
"""
import ctypes
import ctypes.wintypes as wt
import json
import logging
import re
import sys
import time
from pathlib import Path

# --------------------------------------------------------------------------- rutas

if getattr(sys, "frozen", False):
    BASE = Path(sys.executable).resolve().parent
else:
    BASE = Path(__file__).resolve().parent
CONFIG = BASE / "config.json"
SONIDOS = BASE / "sonidos"
LOG = BASE / "teclado_sonidos.log"
EXTENSIONES = (".mp3", ".wav")

# Mapa por defecto: scan code -> nombre del archivo de sonido.
# "0xE0xx" = tecla extendida. Backspace (0x0E) no se incluye porque es identico al
# Backspace de cualquier teclado; agregar "0x0E": "borrar" en config.json si se quiere.
TECLAS_DEFECTO = {
    "0xE035": "dividir", "0x37": "multiplicar", "0x4A": "menos", "0x4E": "mas",
    "0x47": "7", "0x48": "8", "0x49": "9",
    "0x4B": "4", "0x4C": "5", "0x4D": "6",
    "0x4F": "1", "0x50": "2", "0x51": "3",
    "0x52": "0", "0x53": "punto", "0xE01C": "enter",
}
VK_NUMLOCK = 0x90
VENTANA_000_MS = 60  # la tecla 000 envia tres "0" en ~32 ms

# --------------------------------------------------------------------------- Win32

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
winmm = ctypes.WinDLL("winmm")
hid = ctypes.WinDLL("hid")

LRESULT = ctypes.c_ssize_t
ULONG_PTR = ctypes.c_size_t

WH_KEYBOARD_LL = 13
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_TIMER = 0x0113
WM_INPUT_DEVICE_CHANGE = 0x00FE
WM_INPUT = 0x00FF
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x0100, 0x0101, 0x0104, 0x0105
WM_APP_SONIDO = 0x8001
RIDEV_INPUTSINK = 0x00000100
RIDEV_DEVNOTIFY = 0x00002000
RID_INPUT = 0x10000003
RIDI_DEVICENAME = 0x20000007
RIM_TYPEKEYBOARD = 1
LLKHF_EXTENDED = 0x01
LLKHF_INJECTED = 0x10
HWND_MESSAGE = wt.HWND(-3)
ERROR_ALREADY_EXISTS = 183
TIMER_000 = 1
CLASE_VENTANA = "TecladoSonidosIoT"
NOMBRE_MUTEX = "Local\\TecladoSonidosIoT"


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wt.DWORD), ("scanCode", wt.DWORD), ("flags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [("usUsagePage", wt.USHORT), ("usUsage", wt.USHORT),
                ("dwFlags", wt.DWORD), ("hwndTarget", wt.HWND)]


class RAWINPUTDEVICELIST(ctypes.Structure):
    _fields_ = [("hDevice", wt.HANDLE), ("dwType", wt.DWORD)]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [("dwType", wt.DWORD), ("dwSize", wt.DWORD),
                ("hDevice", wt.HANDLE), ("wParam", wt.WPARAM)]


class RAWKEYBOARD(ctypes.Structure):
    _fields_ = [("MakeCode", wt.USHORT), ("Flags", wt.USHORT), ("Reserved", wt.USHORT),
                ("VKey", wt.USHORT), ("Message", wt.UINT), ("ExtraInformation", wt.ULONG)]


class RAWINPUT(ctypes.Structure):
    _fields_ = [("header", RAWINPUTHEADER), ("keyboard", RAWKEYBOARD)]


HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wt.WPARAM, wt.LPARAM)
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wt.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON),
                ("hCursor", wt.HANDLE), ("hbrBackground", wt.HBRUSH),
                ("lpszMenuName", wt.LPCWSTR), ("lpszClassName", wt.LPCWSTR)]


user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wt.HINSTANCE, wt.DWORD]
user32.SetWindowsHookExW.restype = wt.HHOOK
user32.UnhookWindowsHookEx.argtypes = [wt.HHOOK]
user32.CallNextHookEx.argtypes = [wt.HHOOK, ctypes.c_int, wt.WPARAM, wt.LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.HWND,
                                   wt.HMENU, wt.HINSTANCE, wt.LPVOID]
user32.CreateWindowExW.restype = wt.HWND
user32.FindWindowExW.argtypes = [wt.HWND, wt.HWND, wt.LPCWSTR, wt.LPCWSTR]
user32.FindWindowExW.restype = wt.HWND
user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
user32.GetRawInputData.argtypes = [wt.HANDLE, wt.UINT, wt.LPVOID, ctypes.POINTER(wt.UINT), wt.UINT]
user32.GetRawInputDeviceInfoW.argtypes = [wt.HANDLE, wt.UINT, wt.LPVOID, ctypes.POINTER(wt.UINT)]
user32.GetRawInputDeviceList.argtypes = [ctypes.POINTER(RAWINPUTDEVICELIST),
                                         ctypes.POINTER(wt.UINT), wt.UINT]
user32.RegisterRawInputDevices.argtypes = [ctypes.POINTER(RAWINPUTDEVICE), wt.UINT, wt.UINT]
user32.SetTimer.argtypes = [wt.HWND, ULONG_PTR, wt.UINT, wt.LPVOID]
user32.KillTimer.argtypes = [wt.HWND, ULONG_PTR]
kernel32.GetModuleHandleW.restype = wt.HMODULE
kernel32.CreateMutexW.argtypes = [wt.LPVOID, wt.BOOL, wt.LPCWSTR]
kernel32.CreateMutexW.restype = wt.HANDLE
kernel32.CloseHandle.argtypes = [wt.HANDLE]
kernel32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, wt.LPVOID, wt.DWORD,
                                 wt.DWORD, wt.HANDLE]
kernel32.CreateFileW.restype = wt.HANDLE
hid.HidD_GetProductString.argtypes = [wt.HANDLE, wt.LPVOID, wt.ULONG]
winmm.mciSendStringW.argtypes = [wt.LPCWSTR, wt.LPWSTR, wt.UINT, wt.HANDLE]
winmm.mciSendStringW.restype = wt.DWORD
winmm.mciGetErrorStringW.argtypes = [wt.DWORD, wt.LPWSTR, wt.UINT]

# --------------------------------------------------------------------------- dispositivos

_nombres_dispositivo = {}


def ruta_dispositivo(handle):
    if handle not in _nombres_dispositivo:
        n = wt.UINT(0)
        user32.GetRawInputDeviceInfoW(handle, RIDI_DEVICENAME, None, ctypes.byref(n))
        buf = ctypes.create_unicode_buffer(n.value + 1)
        user32.GetRawInputDeviceInfoW(handle, RIDI_DEVICENAME, buf, ctypes.byref(n))
        _nombres_dispositivo[handle] = buf.value
    return _nombres_dispositivo[handle]


def vid_pid(ruta):
    m = re.search(r"VID_([0-9A-F]{4})&PID_([0-9A-F]{4})", ruta.upper())
    return (m.group(1), m.group(2)) if m else None


def nombre_producto(ruta, vp):
    texto = ""
    h = kernel32.CreateFileW(ruta, 0, 3, None, 3, 0, None)  # sin acceso, solo consulta
    if h and h != wt.HANDLE(-1).value:
        buf = ctypes.create_unicode_buffer(127)
        if hid.HidD_GetProductString(h, buf, ctypes.sizeof(buf)):
            texto = buf.value.strip()
        kernel32.CloseHandle(h)
    return texto or f"Teclado USB VID_{vp[0]} PID_{vp[1]}"


def teclados_conectados():
    """Conjunto de (VID, PID) de los teclados conectados ahora."""
    n = wt.UINT(0)
    tam = ctypes.sizeof(RAWINPUTDEVICELIST)
    user32.GetRawInputDeviceList(None, ctypes.byref(n), tam)
    lista = (RAWINPUTDEVICELIST * n.value)()
    n_real = user32.GetRawInputDeviceList(lista, ctypes.byref(n), tam)
    encontrados = set()
    for d in lista[:max(0, n_real)]:
        if d.dwType == RIM_TYPEKEYBOARD:
            vp = vid_pid(ruta_dispositivo(d.hDevice))
            if vp:
                encontrados.add(vp)
    return encontrados


def leer_raw_teclado(lparam):
    n = wt.UINT(0)
    hdr = ctypes.sizeof(RAWINPUTHEADER)
    user32.GetRawInputData(lparam, RID_INPUT, None, ctypes.byref(n), hdr)
    buf = ctypes.create_string_buffer(n.value)
    user32.GetRawInputData(lparam, RID_INPUT, buf, ctypes.byref(n), hdr)
    ri = ctypes.cast(buf, ctypes.POINTER(RAWINPUT)).contents
    if ri.header.dwType != RIM_TYPEKEYBOARD:
        return None
    return ri.header.hDevice, ri.keyboard

# --------------------------------------------------------------------------- audio


def mci(comando):
    buf = ctypes.create_unicode_buffer(256)
    err = winmm.mciSendStringW(comando, buf, 256, None)
    if err:
        msg = ctypes.create_unicode_buffer(256)
        winmm.mciGetErrorStringW(err, msg, 256)
        raise OSError(msg.value)
    return buf.value


def buscar_sonido(nombre):
    for ext in EXTENSIONES:
        ruta = SONIDOS / f"{nombre}{ext}"
        if ruta.is_file():
            return ruta
    return None


def sonando():
    try:
        return mci("status snd mode") == "playing"
    except OSError:
        return False


def reproducir(nombre, forzar=False):
    """Reproduce sonidos/<nombre>.mp3|.wav. Si ya hay uno sonando, lo ignora (salvo forzar)."""
    if not forzar and sonando():
        logging.info("Ignorado (hay otro sonando): %s", nombre)
        return
    ruta = buscar_sonido(nombre)
    if not ruta:
        logging.warning("No hay archivo para la tecla '%s' en %s", nombre, SONIDOS)
        return
    try:
        try:
            mci("close snd")
        except OSError:
            pass
        mci(f'open "{ruta}" type mpegvideo alias snd')
        mci("play snd")
        logging.info("Sonido: %s", ruta.name)
    except OSError as e:
        logging.error("No se pudo reproducir %s: %s", ruta.name, e)

# --------------------------------------------------------------------------- config


def parsear_tecla(texto):
    v = int(texto, 16)
    return (v & 0xFF, bool(v & 0xE000))


def cargar_config():
    datos = json.loads(CONFIG.read_text(encoding="utf-8"))
    disp = datos["dispositivo"]
    teclas = {parsear_tecla(k): v for k, v in datos.get("teclas", TECLAS_DEFECTO).items()}
    return (disp["vid"].upper(), disp["pid"].upper()), disp.get("nombre", ""), teclas


def guardar_config(vp, nombre):
    datos = {
        "_ayuda": "Generado por el asistente. Para elegir otro teclado use configurar.bat. "
                  "'teclas' asigna scan code -> nombre del archivo en sonidos/ (0xE0xx = tecla "
                  "extendida).",
        "dispositivo": {"vid": vp[0], "pid": vp[1], "nombre": nombre},
        "teclas": TECLAS_DEFECTO,
    }
    CONFIG.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")

# --------------------------------------------------------------------------- consola


class Consola:
    """Consola para el asistente; la crea si el proceso no tiene (pyw / .exe)."""

    def __init__(self):
        self.creada = False

    def abrir(self):
        if sys.stdout is None or not kernel32.GetConsoleWindow():
            kernel32.AllocConsole()
            self.creada = True
            sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1)
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleTitleW("Teclado de Sonidos - Configuracion")

    def cerrar(self):
        if self.creada:
            sys.stdout.close()
            sys.stdout = None
            kernel32.FreeConsole()


def tecla_consola():
    import msvcrt
    while msvcrt.kbhit():  # descarta lo que se tecleo mientras se detectaba
        msvcrt.getwch()
    return msvcrt.getwch()

# --------------------------------------------------------------------------- app


class App:
    def __init__(self):
        self.modo = None  # "asistente" | "botonera"
        self.hook = None
        self.hwnd = None
        self.detectado = None  # (vp, ruta) en el asistente
        self.vp = None
        self.teclas = {}
        self.conectado = False
        self.bloqueadas = set()
        self.ceros = 0
        self._wndproc = WNDPROC(self.wndproc)
        self._hookproc = HOOKPROC(self.hookproc)
        self._nombres = []  # indice -> nombre para WM_APP_SONIDO

    # ---- ventana oculta + Raw Input
    def crear_ventana(self):
        hinst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSW()
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hinst
        wc.lpszClassName = CLASE_VENTANA
        user32.RegisterClassW(ctypes.byref(wc))
        self.hwnd = user32.CreateWindowExW(0, CLASE_VENTANA, CLASE_VENTANA, 0, 0, 0, 0, 0,
                                           HWND_MESSAGE, None, hinst, None)
        rid = RAWINPUTDEVICE(1, 6, RIDEV_INPUTSINK | RIDEV_DEVNOTIFY, self.hwnd)
        if not user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(rid)):
            raise OSError(f"RegisterRawInputDevices fallo ({ctypes.get_last_error()})")

    @staticmethod
    def bucle():
        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def wndproc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_INPUT and self.modo == "asistente":
                self.raw_asistente(lparam)
            elif msg == WM_INPUT_DEVICE_CHANGE and self.modo == "botonera":
                self.actualizar_conexion()
            elif msg == WM_APP_SONIDO:
                nombre = self._nombres[wparam]
                if nombre == "0":
                    self.tecla_cero()
                else:
                    reproducir(nombre, forzar=nombre in ("on", "off"))
                return 0
            elif msg == WM_TIMER and wparam == TIMER_000:
                user32.KillTimer(hwnd, TIMER_000)
                reproducir("000" if self.ceros >= 3 else "0")
                self.ceros = 0
                return 0
            elif msg == WM_DESTROY:
                user32.PostQuitMessage(0)
                return 0
        except Exception:
            logging.exception("Error en la ventana")
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def avisar(self, nombre):
        if nombre not in self._nombres:
            self._nombres.append(nombre)
        user32.PostMessageW(self.hwnd, WM_APP_SONIDO, self._nombres.index(nombre), 0)

    # ---- asistente
    def raw_asistente(self, lparam):
        r = leer_raw_teclado(lparam)
        if not r or r[1].Message not in (WM_KEYDOWN, WM_SYSKEYDOWN) or self.detectado:
            return
        ruta = ruta_dispositivo(r[0]) if r[0] else ""
        vp = vid_pid(ruta)
        if not vp:
            print("  Ese teclado no es USB (probablemente el integrado de la laptop).")
            print("  Presiona una tecla del teclado USB que quieres usar...")
            return
        self.detectado = (vp, ruta)
        user32.PostQuitMessage(0)

    def asistente(self):
        consola = Consola()
        consola.abrir()
        print("=" * 60)
        print("  TECLADO DE SONIDOS - Elegir teclado")
        print("=" * 60)
        while True:
            print("\nPresiona cualquier tecla del teclado que quieres convertir en botonera...")
            self.detectado = None
            self.modo = "asistente"
            self.bucle()
            vp, ruta = self.detectado
            nombre = nombre_producto(ruta, vp)
            print(f"\n  Detectado: {nombre}  (VID {vp[0]} / PID {vp[1]})")
            print("  Usar este teclado? [S/N] ", end="", flush=True)
            r = tecla_consola().lower()
            print(r)
            if r == "s":
                break
        guardar_config(vp, nombre)
        logging.info("Configurado teclado %s (VID %s PID %s)", nombre, *vp)
        print(f"\n  Guardado en {CONFIG.name}.")
        print("  Con la luz de Num Lock encendida suena; apagada, funciona normal.")
        print("  La botonera queda funcionando en segundo plano.")
        if consola.creada:
            print("  Esta ventana se cerrara en 5 segundos...")
            time.sleep(5)
        consola.cerrar()

    # ---- botonera
    def actualizar_conexion(self, inicio=False):
        antes = self.conectado
        self.conectado = self.vp in teclados_conectados()
        if inicio or antes != self.conectado:
            estado = "conectado" if self.conectado else "NO conectado (esperando)"
            logging.info("Teclado VID %s PID %s %s", *self.vp, estado)
            if not self.conectado:
                self.bloqueadas.clear()
            self.avisar("on" if self.conectado else "off")

    def tecla_cero(self):
        self.ceros += 1
        if self.ceros == 1:
            user32.SetTimer(self.hwnd, TIMER_000, VENTANA_000_MS, None)

    def hookproc(self, code, wparam, lparam):
        try:
            if code == 0 and self.conectado:
                k = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                if not k.flags & LLKHF_INJECTED and self.decidir(k, wparam):
                    return 1
        except Exception:
            logging.exception("Error en el hook")
        return user32.CallNextHookEx(None, code, wparam, lparam)

    def decidir(self, k, wparam):
        """True = bloquear la tecla."""
        abajo = wparam in (WM_KEYDOWN, WM_SYSKEYDOWN)
        clave = (k.scanCode, bool(k.flags & LLKHF_EXTENDED))
        nombre = self.teclas.get(clave)
        if nombre is None:
            return False
        if not abajo:  # soltar: bloquear solo si bloqueamos al presionar
            if clave in self.bloqueadas:
                self.bloqueadas.discard(clave)
                return True
            return False
        if clave in self.bloqueadas:  # auto-repeticion
            return True
        # Num Lock apagado (o la tecla viene envuelta en Num Lock por un teclado con la
        # luz apagada): funciona como tecla normal.
        if not user32.GetKeyState(VK_NUMLOCK) & 1:
            return False
        self.bloqueadas.add(clave)
        self.avisar(nombre)
        return True

    def botonera(self):
        self.vp, nombre, self.teclas = cargar_config()
        logging.info("Iniciando botonera para %s (VID %s PID %s)", nombre, *self.vp)
        self.modo = "botonera"
        self.actualizar_conexion(inicio=True)
        self.hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._hookproc,
                                             kernel32.GetModuleHandleW(None), 0)
        if not self.hook:
            raise OSError(f"SetWindowsHookExW fallo ({ctypes.get_last_error()})")
        try:
            self.bucle()
        finally:
            user32.UnhookWindowsHookEx(self.hook)
            try:
                mci("close snd")
            except OSError:
                pass
            logging.info("Botonera detenida")

# --------------------------------------------------------------------------- main


def ventana_existente():
    return user32.FindWindowExW(HWND_MESSAGE, None, CLASE_VENTANA, None)


def detener_instancia(esperar_s=0.0):
    hwnd = ventana_existente()
    if hwnd:
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    fin = time.monotonic() + esperar_s
    while ventana_existente() and time.monotonic() < fin:
        time.sleep(0.1)
    return bool(hwnd)


def tomar_mutex(esperar_s=0.0):
    fin = time.monotonic() + esperar_s
    while True:
        h = kernel32.CreateMutexW(None, False, NOMBRE_MUTEX)
        if ctypes.get_last_error() != ERROR_ALREADY_EXISTS:
            return h
        kernel32.CloseHandle(h)
        if time.monotonic() >= fin:
            return None
        time.sleep(0.1)


def main():
    logging.basicConfig(filename=LOG, level=logging.INFO, encoding="utf-8",
                        format="%(asctime)s %(levelname)s %(message)s")
    args = sys.argv[1:]

    if "--detener" in args:
        detener_instancia(esperar_s=3)
        return

    configurar = "--configurar" in args or not CONFIG.exists()
    if "--configurar" in args:
        detener_instancia(esperar_s=3)
    mutex = tomar_mutex(esperar_s=3 if configurar else 0)
    if not mutex:
        logging.info("Ya hay una instancia en ejecucion; se cierra esta.")
        return

    app = App()
    app.crear_ventana()
    if configurar:
        app.asistente()
    app.botonera()
    kernel32.CloseHandle(mutex)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.basicConfig(filename=LOG, level=logging.INFO, encoding="utf-8")
        logging.exception("Error fatal")
        raise

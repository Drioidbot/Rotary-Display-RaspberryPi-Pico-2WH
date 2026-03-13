# ============================================================
#  Pico 2 W · Waveshare LCD-0.96 · Script Menu
#  ─────────────────────────────────────────────
#  Features:
#    • Animated boot sequence on ST7735S 160×80 LCD
#    • Scrollable script menu (joystick UP/DOWN)
#    • KEY_A to select · KEY_B to stop
#    • WiFi Access Point — SSID: PicoMenu / pass: pico1234
#    • Web dashboard at http://192.168.4.1
#    • USB HID keyboard macros (MicroPython native — no extra libs)
#    • Pong game
#
#  One-time install (MicroPython only — no CircuitPython needed):
#    mpremote mip install st7735
#
#  HOW TO USE DASHBOARD:
#    1. Power on — connect to WiFi "PicoMenu" (pass: pico1234)
#    2. Open browser → http://192.168.4.1
# ============================================================

import machine, utime, math, network, socket, json, _thread
from machine import Pin, SPI
import st7735

# ════════════════════════════════════════════════════════════
#  PIN MAP  (Waveshare Pico-LCD-0.96 — hardwired, don't edit)
# ════════════════════════════════════════════════════════════
LCD_DC=8; LCD_CS=9; LCD_SCK=10; LCD_MOSI=11; LCD_RST=12; LCD_BL=13
JOY_UP=2; JOY_DOWN=18; JOY_LEFT=16; JOY_RIGHT=20
KEY_A=15; KEY_B=17

# ════════════════════════════════════════════════════════════
#  DISPLAY INIT
# ════════════════════════════════════════════════════════════
spi = SPI(1, baudrate=62_500_000, polarity=0, phase=0,
          sck=Pin(LCD_SCK), mosi=Pin(LCD_MOSI))
display = st7735.TFT(spi, dc=Pin(LCD_DC),
                     cs=Pin(LCD_CS), rst=Pin(LCD_RST))
display.init()
display.rotation(1)          # landscape → 160×80
_bl_pwm = machine.PWM(Pin(LCD_BL))
_bl_pwm.freq(1000)
_BRIGHTNESS_FILE = "brightness.txt"

def _load_brightness():
    try:
        with open(_BRIGHTNESS_FILE, "r") as f:
            return max(0, min(100, int(f.read().strip())))
    except:
        return 100   # default if file missing

def _save_brightness(pct):
    try:
        with open(_BRIGHTNESS_FILE, "w") as f:
            f.write(str(pct))
    except:
        pass

BRIGHTNESS = _load_brightness()

def set_brightness(pct):
    global BRIGHTNESS
    BRIGHTNESS = max(0, min(100, pct))
    _bl_pwm.duty_u16(int(BRIGHTNESS / 100 * 65535))

set_brightness(BRIGHTNESS)
W, H = 160, 80

# ── Colours ──────────────────────────────────────────────────
BLACK  = st7735.TFT.BLACK
WHITE  = st7735.TFT.WHITE
def rgb(r,g,b): return st7735.color565(r,g,b)
CYAN    = rgb(0,   220, 220)
DKCYAN  = rgb(0,   100, 100)
NAVY    = rgb(0,   0,   80)
DKNAVY  = rgb(0,   0,   40)
ORANGE  = rgb(255, 140, 0)
GREEN   = rgb(0,   210, 80)
DKGREEN = rgb(0,   70,  25)
GREY    = rgb(70,  70,  70)
LTGREY  = rgb(180, 180, 180)
RED     = rgb(200, 0,   0)
YELLOW  = rgb(255, 220, 0)
PINK    = rgb(255, 80,  160)
PURPLE  = rgb(140, 0,   220)

# ════════════════════════════════════════════════════════════
#  WIFI CONFIG — change these if you like
# ════════════════════════════════════════════════════════════
AP_SSID     = "PicoMenu"
AP_PASSWORD = "pico1234"      # must be 8+ chars for WPA2
AP_IP       = "192.168.4.1"
SERVER_PORT = 80

# ── Input pins ───────────────────────────────────────────────
joy_up    = Pin(JOY_UP,    Pin.IN, Pin.PULL_UP)
joy_down  = Pin(JOY_DOWN,  Pin.IN, Pin.PULL_UP)
joy_left  = Pin(JOY_LEFT,  Pin.IN, Pin.PULL_UP)
joy_right = Pin(JOY_RIGHT, Pin.IN, Pin.PULL_UP)
key_a     = Pin(KEY_A,     Pin.IN, Pin.PULL_UP)
key_b     = Pin(KEY_B,     Pin.IN, Pin.PULL_UP)
# joy_left / joy_right not used — only 3 buttons on this build

def pressed(pin):
    if pin.value() == 0:
        utime.sleep_ms(25)
        return pin.value() == 0
    return False

CW = 8   # character width (8×8 font)
def txt(s, x, y, fg=WHITE, bg=BLACK):
    display.text(display.FONT_8x8, s, x, y, fg, bg)
def fill(x, y, w, h, c):
    display.fill_rect(x, y, w, h, c)
def hline(y, c):
    fill(0, y, W, 1, c)

# ════════════════════════════════════════════════════════════
#  BOOT ANIMATION
#  Three phases:
#   1. Starfield — stars streak in from centre
#   2. Logo build — "PICO MENU" sweeps in letter by letter
#   3. Scan line — a bright bar wipes down and fades out
# ════════════════════════════════════════════════════════════

def _lerp_color(c1, c2, t):
    """Linearly interpolate between two RGB565 colours (t = 0.0–1.0)."""
    r1=(c1>>11)&0x1f; g1=(c1>>5)&0x3f;  b1=c1&0x1f
    r2=(c2>>11)&0x1f; g2=(c2>>5)&0x3f;  b2=c2&0x1f
    r=int(r1+(r2-r1)*t)
    g=int(g1+(g2-g1)*t)
    b=int(b1+(b2-b1)*t)
    return (r<<11)|(g<<5)|b

# -- Phase 1: starfield (40 frames) --
def _anim_stars():
    import urandom as rnd
    fill(0, 0, W, H, BLACK)
    # pre-generate star positions
    stars = []
    for _ in range(28):
        angle = rnd.getrandbits(8) / 256 * 6.283
        speed = 0.5 + rnd.getrandbits(3) * 0.25
        stars.append([W//2, H//2, angle, speed, 0])  # x,y,angle,speed,life

    for frame in range(42):
        fill(0, 0, W, H, BLACK)
        for s in stars:
            s[0] += math.cos(s[2]) * s[3] * (frame * 0.06 + 0.3)
            s[1] += math.sin(s[2]) * s[3] * (frame * 0.06 + 0.3)
            s[4] += 1
            # brightness grows with distance from centre
            bright = min(255, s[4] * 7)
            c = rgb(bright, bright, bright)
            px, py = int(s[0]), int(s[1])
            if 0 <= px < W and 0 <= py < H:
                fill(px, py, 2, 1, c)
        utime.sleep_ms(28)

# -- Phase 2: logo letter sweep (uses colour cycling) --
def _anim_logo():
    LOGO    = "PICO  MENU"
    TAGLINE = "Waveshare 0.96 LCD"
    colours = [CYAN, GREEN, YELLOW, ORANGE, PINK, PURPLE, WHITE]

    fill(0, 0, W, H, BLACK)

    # Draw letters one by one with a colour sweep
    total = len(LOGO)
    lx = (W - total * CW) // 2
    for i, ch in enumerate(LOGO):
        col = colours[i % len(colours)]
        txt(ch, lx + i*CW, 24, col, BLACK)
        # Brief scanline flash at current letter position
        fill(lx + i*CW, 22, CW, 2, col)
        utime.sleep_ms(55)
        fill(lx + i*CW, 22, CW, 2, BLACK)

    utime.sleep_ms(80)

    # Tagline fade-in as a solid underline grows
    tag_x = (W - len(TAGLINE)*CW) // 2
    for w in range(0, len(TAGLINE)*CW + 1, 4):
        fill(tag_x, 40, w, 1, DKCYAN)
        utime.sleep_ms(12)
    txt(TAGLINE, tag_x, 44, DKCYAN, BLACK)

    utime.sleep_ms(120)

    # Sub-labels slide up from below
    lines = [
        ("UP/DOWN  navigate", GREY),
        ("KEY_A    select",   GREY),
    ]
    for row, (line, col) in enumerate(lines):
        lx2 = (W - len(line)*CW) // 2
        for dy in range(12, -1, -2):
            fill(0, 58 + row*10 - 2, W, 10, BLACK)
            txt(line, lx2, 58 + row*10 + dy, col, BLACK)
            utime.sleep_ms(18)

    utime.sleep_ms(300)

# -- Phase 3: scan-line wipe --
def _anim_scanline():
    for y in range(0, H, 2):
        # bright leading edge
        fill(0, y, W, 2, CYAN)
        if y > 2:
            # fade trail
            fill(0, y-2, W, 2, _lerp_color(CYAN, BLACK, 0.55))
        if y > 6:
            fill(0, y-6, W, 4, BLACK)
        utime.sleep_ms(14)
    fill(0, 0, W, H, BLACK)
    utime.sleep_ms(60)

def show_boot_animation():
    """Full boot sequence — runs once at startup."""
    _anim_stars()
    _anim_logo()
    utime.sleep_ms(400)
    _anim_scanline()

# ════════════════════════════════════════════════════════════
#  LCD SCREENS
# ════════════════════════════════════════════════════════════
TITLE_H=14; ROW_H=16; VISIBLE=4

def draw_menu(items, idx):
    fill(0, 0, W, H, BLACK)
    fill(0, 0, W, TITLE_H, DKCYAN)
    lbl = "SELECT SCRIPT"
    txt(lbl, (W - len(lbl)*CW)//2, 3, BLACK, DKCYAN)
    start = max(0, min(idx-1, len(items)-VISIBLE))
    for row in range(VISIBLE):
        i = start + row
        if i >= len(items): break
        y = TITLE_H + 1 + row*(ROW_H+1)
        name = items[i]["name"]
        if i == idx:
            fill(0, y, W, ROW_H, DKGREEN); hline(y, GREEN)
            txt(f" >{name[:17]}", 0, y+4, WHITE, DKGREEN)
        else:
            fill(0, y, W, ROW_H, BLACK)
            txt(f"  {name[:17]}", 0, y+4, LTGREY, BLACK)
    if start > 0:              txt("^", W-CW-1, TITLE_H+2, CYAN, BLACK)
    if start+VISIBLE<len(items): txt("v", W-CW-1, H-10,    CYAN, BLACK)

def draw_running(name, detail="", pct=0):
    fill(0, 0, W, H, BLACK)
    fill(0, 0, W, TITLE_H, ORANGE)
    lbl = "RUNNING"
    txt(lbl, (W-len(lbl)*CW)//2, 3, BLACK, ORANGE)
    n = name[:18]; txt(n, (W-len(n)*CW)//2, 20, WHITE, BLACK)
    if detail:
        d = detail[:18]; txt(d, (W-len(d)*CW)//2, 36, CYAN, BLACK)
    fill(0, H-12, W, 4, GREY)
    bw = int(W * max(0, min(pct, 100)) / 100)
    if bw: fill(0, H-12, bw, 4, GREEN)
    hint = "KEY_B=stop"
    txt(hint, (W-len(hint)*CW)//2, H-8, GREY, BLACK)

def draw_error(msg):
    fill(0, 0, W, H, BLACK); fill(0, 0, W, TITLE_H, RED)
    txt("  ERROR", 4, 3, WHITE, RED)
    lines = [msg[i:i+19] for i in range(0, min(len(msg), 57), 19)]
    for n, line in enumerate(lines):
        txt(line, 2, 18+n*12, ORANGE, BLACK)
    utime.sleep_ms(2500)

def draw_wifi_screen(ip, clients=0):
    """Teal info screen — shown by the WiFi Dashboard menu entry."""
    TEAL   = rgb(0, 160, 140)
    DKTEAL = rgb(0,  60,  55)
    fill(0, 0, W, H, BLACK)
    fill(0, 0, W, TITLE_H, DKTEAL)
    lbl = "WIFI DASHBOARD"
    txt(lbl, (W - len(lbl)*CW)//2, 3, WHITE, DKTEAL)
    txt(f"SSID: {AP_SSID}",    2, 18, CYAN,   BLACK)
    txt(f"Pass: {AP_PASSWORD}", 2, 30, LTGREY, BLACK)
    txt(f"http://{ip}",         2, 42, GREEN,  BLACK)
    txt(f"Clients: {clients}",  2, 56, GREY,   BLACK)

# ════════════════════════════════════════════════════════════
#  SHARED STATE  (read/written from both cores)
# ════════════════════════════════════════════════════════════
state = {
    "running":     False,
    "script":      "",
    "detail":      "",
    "pct":         0,
    "stop":        False,
    "web_trigger": -1,    # index set by web server, -1 = none
    "web_macro":   None,  # custom text to type via HID, set by /macro
    "clients":     [],    # open SSE socket objects
    "log":         [],    # rolling log lines
    "wifi_ip":     AP_IP,
}
_lock = _thread.allocate_lock()
_boot_ms = utime.ticks_ms()   # used to calculate uptime

def log_push(line):
    """Append to rolling log and push to all SSE clients."""
    with _lock:
        state["log"].append(line)
        if len(state["log"]) > 100:
            state["log"].pop(0)
        dead = []
        for cl in state["clients"]:
            try:
                cl.send(f"data: {json.dumps(line)}\n\n".encode())
            except:
                dead.append(cl)
        for d in dead:
            state["clients"].remove(d)

def set_state(script="", detail="", pct=0, running=None):
    with _lock:
        if running is not None:
            state["running"] = running
        state["script"] = script
        state["detail"] = detail
        state["pct"]    = pct

# ════════════════════════════════════════════════════════════
#  YOUR SCRIPTS
#  ─────────────────────────────────────────────────────────
#  Each function takes no arguments.
#  • Call draw_running(name, detail, 0–100) to update screen
#  • Check key_b.value() == 0 to allow KEY_B to stop it
#  • The menu redraws automatically when the function returns
# ════════════════════════════════════════════════════════════

def script_wifi_info():
    """Show WiFi credentials + IP on the LCD until KEY_B pressed."""
    with _lock:
        ip      = state["wifi_ip"]
        clients = len(state["clients"])
    while key_b.value() and not state["stop"]:
        with _lock:
            clients = len(state["clients"])
        draw_wifi_screen(ip, clients)
        utime.sleep_ms(400)

# ════════════════════════════════════════════════════════════
#  USB HID KEYBOARD MACROS  (Windows target)
#  ─────────────────────────────────────────────────────────
#  Requires CircuitPython firmware + adafruit_hid library.
#
#  Flash CircuitPython: https://circuitpython.org/board/raspberry_pi_pico2_w
#  Then install lib:    mpremote mip install adafruit-circuitpython-hid
#
#  HOW IT WORKS:
#    • Select a macro from the menu
#    • A 3-second countdown gives you time to click the
#      target window on your PC
#    • The Pico then types keystrokes as a USB keyboard
#    • Press KEY_B at any point to abort
#
#  STEP TYPES:
#    ("key",    Keycode.X)           — tap a single key
#    ("combo",  [Keycode.MOD, ...])  — hold modifiers + tap last key
#    ("string", "text here")         — type a string
#    ("delay",  milliseconds)        — wait
#
#  USEFUL WINDOWS KEYCODES:
#    Keycode.GUI_LEFT  = ⊞ Windows key
#    Keycode.CONTROL   = Ctrl
#    Keycode.SHIFT     = Shift
#    Keycode.ALT       = Alt
#    Keycode.ENTER     = Enter
#    Keycode.TAB       = Tab
#    Keycode.ESCAPE    = Escape
#    Keycode.F5        = F5  (browser refresh)
# ════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════
#  USB HID KEYBOARD MACROS  (MicroPython native — no extra libs)
#  ─────────────────────────────────────────────────────────
#  Uses MicroPython's built-in 'usb.device.hid' module which
#  ships with recent MicroPython builds for Pico 2 W.
#  No CircuitPython or adafruit_hid needed — WiFi + HID both
#  work on the same MicroPython firmware.
#
#  HOW IT WORKS:
#    • Select a macro from the menu
#    • 3-second countdown — click your target window
#    • Pico types as a USB keyboard
#    • KEY_B aborts at any point
#
#  STEP TYPES:
#    ("key",    KC_X)               — tap a single key
#    ("combo",  [KC_MOD, KC_KEY])   — hold mod(s) + tap last key
#    ("string", "text here")        — type a string character by character
#    ("delay",  milliseconds)       — wait
#
#  WINDOWS KEY CODES (add your own from the HID usage table):
#    KC_WIN   = 0xE3   KC_CTRL  = 0xE0   KC_SHIFT = 0xE1
#    KC_ALT   = 0xE2   KC_ENTER = 0x28   KC_ESC   = 0x29
#    KC_TAB   = 0x2B   KC_SPACE = 0x2C   KC_BSPC  = 0x2A
#    KC_F5    = 0x3E   KC_L     = 0x0F   KC_R     = 0x15
# ════════════════════════════════════════════════════════════

# ── MicroPython native HID setup ─────────────────────────────
try:
    import usb.device
    from usb.device.hid import HIDInterface, KeyboardReport

    class _KBD(HIDInterface):
        def __init__(self):
            super().__init__(KeyboardReport(), protocol=1,
                             interface_str="Pico Keyboard")
        def on_open(self): pass

    _kbd_iface = _KBD()
    usb.device.get().init(_kbd_iface, builtin_driver=True)
    HID_OK = True
except Exception:
    HID_OK = False

# ── Key code constants ────────────────────────────────────────
KC_CTRL  = 0xE0; KC_SHIFT = 0xE1; KC_ALT  = 0xE2; KC_WIN  = 0xE3
KC_ENTER = 0x28; KC_ESC   = 0x29; KC_BSPC = 0x2A; KC_TAB  = 0x2B
KC_SPACE = 0x2C; KC_F5    = 0x3E
# Letters a–z = 0x04–0x1D
KC_A=0x04;KC_B=0x05;KC_C=0x06;KC_D=0x07;KC_E=0x08;KC_F=0x09
KC_G=0x0A;KC_H=0x0B;KC_I=0x0C;KC_J=0x0D;KC_K=0x0E;KC_L=0x0F
KC_M=0x10;KC_N=0x11;KC_O=0x12;KC_P=0x13;KC_Q=0x14;KC_R=0x15
KC_S=0x16;KC_T=0x17;KC_U=0x18;KC_V=0x19;KC_W=0x1A;KC_X=0x1B
KC_Y=0x1C;KC_Z=0x1D
# Numbers 1–0 = 0x1E–0x27
KC_1=0x1E;KC_2=0x1F;KC_3=0x20;KC_4=0x21;KC_5=0x22
KC_6=0x23;KC_7=0x24;KC_8=0x25;KC_9=0x26;KC_0=0x27

# ── ASCII → (modifier, keycode) lookup ───────────────────────
# Covers the characters needed for URLs and common commands
_ASCII_MAP = {
    ' ':(0,KC_SPACE),'\t':(0,KC_TAB),'\n':(0,KC_ENTER),
    'a':(0,KC_A),'b':(0,KC_B),'c':(0,KC_C),'d':(0,KC_D),
    'e':(0,KC_E),'f':(0,KC_F),'g':(0,KC_G),'h':(0,KC_H),
    'i':(0,KC_I),'j':(0,KC_J),'k':(0,KC_K),'l':(0,KC_L),
    'm':(0,KC_M),'n':(0,KC_N),'o':(0,KC_O),'p':(0,KC_P),
    'q':(0,KC_Q),'r':(0,KC_R),'s':(0,KC_S),'t':(0,KC_T),
    'u':(0,KC_U),'v':(0,KC_V),'w':(0,KC_W),'x':(0,KC_X),
    'y':(0,KC_Y),'z':(0,KC_Z),
    'A':(KC_SHIFT,KC_A),'B':(KC_SHIFT,KC_B),'C':(KC_SHIFT,KC_C),
    'D':(KC_SHIFT,KC_D),'E':(KC_SHIFT,KC_E),'F':(KC_SHIFT,KC_F),
    'G':(KC_SHIFT,KC_G),'H':(KC_SHIFT,KC_H),'I':(KC_SHIFT,KC_I),
    'J':(KC_SHIFT,KC_J),'K':(KC_SHIFT,KC_K),'L':(KC_SHIFT,KC_L),
    'M':(KC_SHIFT,KC_M),'N':(KC_SHIFT,KC_N),'O':(KC_SHIFT,KC_O),
    'P':(KC_SHIFT,KC_P),'Q':(KC_SHIFT,KC_Q),'R':(KC_SHIFT,KC_R),
    'S':(KC_SHIFT,KC_S),'T':(KC_SHIFT,KC_T),'U':(KC_SHIFT,KC_U),
    'V':(KC_SHIFT,KC_V),'W':(KC_SHIFT,KC_W),'X':(KC_SHIFT,KC_X),
    'Y':(KC_SHIFT,KC_Y),'Z':(KC_SHIFT,KC_Z),
    '1':(0,KC_1),'2':(0,KC_2),'3':(0,KC_3),'4':(0,KC_4),
    '5':(0,KC_5),'6':(0,KC_6),'7':(0,KC_7),'8':(0,KC_8),
    '9':(0,KC_9),'0':(0,KC_0),
    '!':(KC_SHIFT,KC_1),'@':(KC_SHIFT,KC_2),'#':(KC_SHIFT,KC_3),
    '$':(KC_SHIFT,KC_4),'%':(KC_SHIFT,KC_5),'^':(KC_SHIFT,KC_6),
    '&':(KC_SHIFT,KC_7),'*':(KC_SHIFT,KC_8),'(':(KC_SHIFT,KC_9),
    ')':(KC_SHIFT,KC_0),
    # punctuation  (key 0x2D = -, 0x2E = =, 0x2F = [, 0x30 = ]
    #               0x31 = \, 0x33 = ;, 0x34 = ', 0x35 = `,
    #               0x36 = ,, 0x37 = ., 0x38 = /)
    '-':(0,0x2D),'_':(KC_SHIFT,0x2D),'=':(0,0x2E),'+':(KC_SHIFT,0x2E),
    '[':(0,0x2F),']':(0,0x30),'{':(KC_SHIFT,0x2F),'}':(KC_SHIFT,0x30),
    ';':(0,0x33),':':(KC_SHIFT,0x33),"'":(0,0x34),'"':(KC_SHIFT,0x34),
    ',':(0,0x36),'<':(KC_SHIFT,0x36),'.':(0,0x37),'>':(KC_SHIFT,0x37),
    '/':(0,0x38),'?':(KC_SHIFT,0x38),'`':(0,0x35),'~':(KC_SHIFT,0x35),
    '\\':(0,0x31),'|':(KC_SHIFT,0x31),
}

def _hid_tap(mod, key):
    """Press mod+key then release all."""
    if not HID_OK: return
    _kbd_iface.send_report(KeyboardReport(modifier=mod, keys=[key]))
    utime.sleep_ms(50)
    _kbd_iface.send_report(KeyboardReport())   # release
    utime.sleep_ms(30)

def _hid_string(text):
    """Type a string character by character."""
    for ch in text:
        entry = _ASCII_MAP.get(ch)
        if entry:
            _hid_tap(entry[0], entry[1])
        utime.sleep_ms(20)

LIME = rgb(160, 255, 0)

def draw_macro_screen(name, status, pct,
                      countdown=False, done=False, aborted=False):
    """Purple-themed screen shown during macro execution."""
    hdr = PURPLE
    if done:    hdr = DKCYAN
    if aborted: hdr = RED
    fill(0, 0, W, H, BLACK)
    fill(0, 0, W, TITLE_H, hdr)
    lbl = "HID MACRO"
    txt(lbl, (W - len(lbl)*CW)//2, 3, WHITE, hdr)
    n = name[:18]
    txt(n, (W - len(n)*CW)//2, 18, WHITE, BLACK)
    s = status[:18]
    if done:        col = LIME
    elif aborted:   col = RED
    elif countdown: col = ORANGE
    else:           col = CYAN
    txt(s, (W - len(s)*CW)//2, 34, col, BLACK)
    fill(0, H-14, W, 5, GREY)
    bw = int(W * max(0, min(pct, 100)) / 100)
    bar_col = LIME if done else (RED if aborted else PURPLE)
    if bw: fill(0, H-14, bw, 5, bar_col)
    txt(f"{pct:3d}%", W - 4*CW - 2, H-8, GREY, BLACK)
    txt("KEY_B=abort", 2, H-8, GREY, BLACK)


def run_macro(payload):
    """Execute a payload. Aborts on KEY_B or state stop flag."""
    name  = payload["name"]
    steps = payload["steps"]
    total = len(steps)

    # ── 3-second countdown ───────────────────────────────────
    for cd in range(3, 0, -1):
        draw_macro_screen(name, f"Starting in {cd}s...", 0, countdown=True)
        set_state(name, f"Starting in {cd}s...", 0)
        log_push(f"Macro '{name}' starting in {cd}s")
        utime.sleep_ms(1000)
        if key_b.value() == 0 or state["stop"]:
            draw_macro_screen(name, "Cancelled", 0, aborted=True)
            log_push("Macro cancelled")
            utime.sleep_ms(1200)
            return

    if not HID_OK:
        draw_error("USB HID unavailable")
        log_push("ERROR: usb.device not available")
        return

    # ── Execute steps ────────────────────────────────────────
    for i, step in enumerate(steps):
        if key_b.value() == 0 or state["stop"]:
            _kbd_iface.send_report(KeyboardReport())   # safety release
            draw_macro_screen(name, "Aborted!", int(i/total*100), aborted=True)
            log_push("Macro aborted")
            utime.sleep_ms(1500)
            return

        pct = int(i / total * 100)
        draw_macro_screen(name, f"Step {i+1}/{total}", pct)
        set_state(name, f"Step {i+1}/{total}", pct)
        log_push(f"Step {i+1}/{total}")

        kind = step[0]
        if kind == "key":
            _hid_tap(0, step[1])
        elif kind == "combo":
            # last item is the key, everything before is a modifier byte
            keys = step[1]
            mod = 0
            for k in keys[:-1]:
                # modifier keys live at 0xE0–0xE7; map to modifier bitmask
                mod |= (1 << (k - 0xE0))
            _hid_tap(mod, keys[-1])
        elif kind == "string":
            _hid_string(step[1])
        elif kind == "delay":
            utime.sleep_ms(step[1])

    _kbd_iface.send_report(KeyboardReport())   # release all
    draw_macro_screen(name, "Done!", 100, done=True)
    log_push(f"Macro '{name}' complete")
    utime.sleep_ms(1500)


# ════════════════════════════════════════════════════════════
#  PAYLOADS — define your macros here
#  ─────────────────────────────────────────────────────────
#  TO ADD A NEW MACRO:
#    1. Add a dict to PAYLOADS with "name" and "steps"
#    2. Add a one-line wrapper function below
#    3. Add it to MENU
# ════════════════════════════════════════════════════════════

PAYLOADS = [
    # ── Open a URL in the default browser (WIN+R trick) ──────
    {
        "name": "Open GitHub",
        "steps": [
            ("combo",  [KC_WIN, KC_R]),
            ("delay",  700),
            ("string", "https://github.com"),
            ("delay",  200),
            ("key",    KC_ENTER),
        ],
    },
    {
        "name": "Open YouTube",
        "steps": [
            ("combo",  [KC_WIN, KC_R]),
            ("delay",  700),
            ("string", "https://youtube.com"),
            ("delay",  200),
            ("key",    KC_ENTER),
        ],
    },
    # ── Open CMD and run a command ────────────────────────────
    {
        "name": "Open CMD",
        "steps": [
            ("combo",  [KC_WIN, KC_R]),
            ("delay",  700),
            ("string", "cmd"),
            ("key",    KC_ENTER),
            ("delay",  1200),
            ("string", "echo Hello from Pico!"),
            ("key",    KC_ENTER),
        ],
    },
    # ── Lock Windows immediately ──────────────────────────────
    {
        "name": "Lock PC",
        "steps": [
            ("combo",  [KC_WIN, KC_L]),
        ],
    },
    # ── Custom payload — fill in your own steps below ─────────
    # {
    #     "name": "My Macro",
    #     "steps": [
    #         ("combo",  [KC_WIN, KC_R]),
    #         ("delay",  700),
    #         ("string", "notepad"),
    #         ("key",    KC_ENTER),
    #         ("delay",  1000),
    #         ("string", "Hello from Pico!"),
    #     ],
    # },
]

# ── Wrapper functions (one per payload) ──────────────────────
def macro_github():   run_macro(PAYLOADS[0])
def macro_youtube():  run_macro(PAYLOADS[1])
def macro_cmd():      run_macro(PAYLOADS[2])
def macro_lock():     run_macro(PAYLOADS[3])


# ════════════════════════════════════════════════════════════
#  PONG GAME
#  ─────────────────────────────────────────────────────────
#  Controls:
#    JOY_UP   → move your paddle up
#    JOY_DOWN → move your paddle down
#    KEY_B    → quit back to menu
#
#  You (right paddle) vs CPU (left paddle).
#  First to 7 points wins.
#  Ball speeds up every time it's hit.
# ════════════════════════════════════════════════════════════

def script_pong():
    # ── Dimensions ───────────────────────────────────────────
    PW, PH   = 3, 14          # paddle width, height
    BW       = 3              # ball size
    MARGIN   = 4              # paddle distance from edge
    WIN_SCORE= 7

    # ── Colours ──────────────────────────────────────────────
    BG    = BLACK
    FG    = WHITE
    SCORE_COL = CYAN
    NET_COL   = GREY
    WIN_COL   = GREEN
    LOSE_COL  = RED

    # ── Helper draws ─────────────────────────────────────────
    def draw_net():
        for y in range(0, H, 5):
            fill(W//2 - 1, y, 2, 3, NET_COL)

    def draw_paddle(x, y, col=FG):
        fill(x, y, PW, PH, col)

    def draw_ball(x, y, col=FG):
        fill(x, y, BW, BW, col)

    def draw_scores(sl, sr):
        fill(0, 0, W, TITLE_H, BG)       # clear score area
        ls = str(sl); rs = str(sr)
        txt(ls, W//2 - 28, 3, SCORE_COL, BG)
        txt(rs, W//2 + 18, 3, SCORE_COL, BG)

    def flash_message(msg, col):
        fill(0, 0, W, H, BG)
        ml = (W - len(msg)*CW) // 2
        txt(msg, ml, H//2 - 4, col, BG)
        utime.sleep_ms(1200)

    # ── Game state ───────────────────────────────────────────
    import urandom as rnd

    def reset_ball(direction=1):
        bx = W//2 - BW//2
        by = rnd.getrandbits(5) + TITLE_H + 4
        by = min(by, H - BW - 2)
        spd = 2
        # slight random vertical angle
        vy = 1 if rnd.getrandbits(1) else -1
        return [float(bx), float(by), float(direction * spd), float(vy), spd]

    score_l = 0          # CPU score
    score_r = 0          # player score
    py = H // 2 - PH // 2          # player (right) paddle y
    cy = H // 2 - PH // 2          # CPU (left) paddle y
    ball = reset_ball(1)            # [bx, by, vx, vy, speed]

    CPU_SPEED = 1          # pixels CPU paddle moves per frame
    FRAME_MS  = 30

    # ── Initial draw ─────────────────────────────────────────
    fill(0, 0, W, H, BG)
    draw_net()
    draw_scores(score_l, score_r)
    draw_paddle(MARGIN, cy)                    # CPU left
    draw_paddle(W - MARGIN - PW, py)           # player right
    draw_ball(int(ball[0]), int(ball[1]))

    # ── Game loop ────────────────────────────────────────────
    while True:
        t0 = utime.ticks_ms()

        # ── Quit ─────────────────────────────────────────────
        if not key_b.value() or state["stop"]:
            break

        bx, by, vx, vy, spd = ball

        # ── Erase old positions ───────────────────────────────
        fill(MARGIN, int(cy), PW, PH, BG)
        fill(W - MARGIN - PW, int(py), PW, PH, BG)
        fill(int(bx), int(by), BW, BW, BG)

        # ── Player input ──────────────────────────────────────
        if joy_up.value() == 0 and py > TITLE_H + 1:
            py -= 2
        if joy_down.value() == 0 and py < H - PH - 1:
            py += 2

        # ── CPU tracks ball (with speed limit) ───────────────
        cy_centre = cy + PH // 2
        if cy_centre < by + BW // 2 - 1 and cy < H - PH - 1:
            cy += CPU_SPEED
        elif cy_centre > by + BW // 2 + 1 and cy > TITLE_H + 1:
            cy -= CPU_SPEED

        # ── Move ball ─────────────────────────────────────────
        bx += vx
        by += vy

        # ── Top / bottom bounce ───────────────────────────────
        if by <= TITLE_H + 1:
            by = TITLE_H + 1; vy = abs(vy)
        if by >= H - BW - 1:
            by = H - BW - 1; vy = -abs(vy)

        # ── Paddle collisions ─────────────────────────────────
        # Left (CPU) paddle
        if (bx <= MARGIN + PW and
                bx >= MARGIN - 1 and
                by + BW >= cy and by <= cy + PH):
            bx = MARGIN + PW + 1
            vx = abs(vx) + 0.15          # speed up slightly
            # add angle based on hit position
            hit = (by + BW/2) - (cy + PH/2)
            vy = hit * 0.18

        # Right (player) paddle
        px_left = W - MARGIN - PW
        if (bx + BW >= px_left and
                bx + BW <= px_left + PW + 1 and
                by + BW >= py and by <= py + PH):
            bx = px_left - BW - 1
            vx = -(abs(vx) + 0.15)
            hit = (by + BW/2) - (py + PH/2)
            vy = hit * 0.18

        # Clamp vy so it never goes too steep
        if vy > 3:  vy = 3.0
        if vy < -3: vy = -3.0

        # ── Scoring ───────────────────────────────────────────
        scored = False
        if bx < 0:                         # CPU missed → player scores
            score_r += 1
            scored = True
            ball = reset_ball(-1)
        elif bx > W:                       # player missed → CPU scores
            score_l += 1
            scored = True
            ball = reset_ball(1)
        else:
            ball = [bx, by, vx, vy, spd]

        if scored:
            fill(0, 0, W, H, BG)
            draw_net()
            draw_scores(score_l, score_r)
            cy = H // 2 - PH // 2
            py = H // 2 - PH // 2
            utime.sleep_ms(600)
            if score_r >= WIN_SCORE:
                flash_message("YOU WIN!", WIN_COL)
                break
            if score_l >= WIN_SCORE:
                flash_message("CPU WINS", LOSE_COL)
                break
            continue

        # ── Redraw ────────────────────────────────────────────
        draw_net()
        draw_scores(score_l, score_r)
        draw_paddle(MARGIN, int(cy))
        draw_paddle(W - MARGIN - PW, int(py))
        draw_ball(int(ball[0]), int(ball[1]))

        # ── Frame rate cap ────────────────────────────────────
        elapsed = utime.ticks_diff(utime.ticks_ms(), t0)
        if elapsed < FRAME_MS:
            utime.sleep_ms(FRAME_MS - elapsed)




# ════════════════════════════════════════════════════════════
#  SNAKE GAME
#  ─────────────────────────────────────────────────────────
#  Controls:
#    JOY_UP / DOWN / LEFT / RIGHT  — change direction
#    KEY_B                         — quit back to menu
#
#  Eat the green food to grow and score points.
#  Hitting a wall or yourself ends the game.
#  Speed increases every 5 food eaten.
# ════════════════════════════════════════════════════════════

def script_snake():
    import urandom as rnd

    SZ      = 4          # cell size in pixels
    COLS    = W // SZ    # 40 columns
    ROWS    = (H - TITLE_H) // SZ   # rows below header
    OY      = TITLE_H    # y offset for play area

    # colours
    BG       = BLACK
    HEAD_COL = GREEN
    BODY_COL = rgb(0, 120, 40)
    FOOD_COL = RED
    WALL_COL = GREY
    TEXT_COL = WHITE

    def cell_px(cx, cy):
        """Top-left pixel of grid cell."""
        return cx * SZ, OY + cy * SZ

    def draw_cell(cx, cy, col):
        px, py = cell_px(cx, cy)
        fill(px, py, SZ - 1, SZ - 1, col)

    def erase_cell(cx, cy):
        px, py = cell_px(cx, cy)
        fill(px, py, SZ, SZ, BG)

    def place_food(snake_set):
        while True:
            fx = rnd.getrandbits(6) % COLS
            fy = rnd.getrandbits(5) % ROWS
            if (fx, fy) not in snake_set:
                return fx, fy

    def draw_header(score):
        fill(0, 0, W, TITLE_H, rgb(0, 60, 0))
        lbl = f"SNAKE  {score}"
        txt(lbl, (W - len(lbl) * CW) // 2, 3, GREEN, rgb(0, 60, 0))

    def draw_border():
        # top and bottom lines of play area
        hline(OY,          WALL_COL)
        hline(H - 1,       WALL_COL)
        # left and right columns
        fill(0,     OY, 1, H - OY, WALL_COL)
        fill(W - 1, OY, 1, H - OY, WALL_COL)

    # ── Initial state ────────────────────────────────────────
    # Snake starts as 3 cells, heading right, in the middle
    sx, sy   = COLS // 2, ROWS // 2
    snake    = [(sx, sy), (sx - 1, sy), (sx - 2, sy)]
    snake_s  = set(snake)
    dx, dy   = 1, 0       # direction
    ndx, ndy = 1, 0       # buffered next direction

    food     = place_food(snake_s)
    score    = 0
    eaten    = 0           # total food eaten (for speed)
    FRAME_MS = 180         # starting frame time (ms)

    # Draw initial screen
    fill(0, 0, W, H, BG)
    draw_border()
    draw_header(score)
    for seg in snake:
        draw_cell(seg[0], seg[1], BODY_COL)
    draw_cell(snake[0][0], snake[0][1], HEAD_COL)
    draw_cell(food[0], food[1], FOOD_COL)

    # ── Game loop ────────────────────────────────────────────
    while True:
        t0 = utime.ticks_ms()

        if not key_b.value() or state["stop"]:
            break

        # ── Read direction input (buffer to avoid 180° reversal) ──
        if joy_up.value() == 0    and dy == 0:  ndx, ndy =  0, -1
        if joy_down.value() == 0  and dy == 0:  ndx, ndy =  0,  1
        if joy_left.value() == 0  and dx == 0:  ndx, ndy = -1,  0
        if joy_right.value() == 0 and dx == 0:  ndx, ndy =  1,  0

        dx, dy = ndx, ndy

        # ── New head position ─────────────────────────────────
        hx = snake[0][0] + dx
        hy = snake[0][1] + dy

        # ── Wall collision ────────────────────────────────────
        if hx < 0 or hx >= COLS or hy < 0 or hy >= ROWS:
            break

        # ── Self collision ────────────────────────────────────
        if (hx, hy) in snake_s:
            break

        # ── Move: add new head ────────────────────────────────
        snake.insert(0, (hx, hy))
        snake_s.add((hx, hy))

        # ── Food eaten? ───────────────────────────────────────
        if (hx, hy) == food:
            score += 10
            eaten += 1
            # speed up every 5 food, cap at 60 ms
            FRAME_MS = max(60, 180 - eaten * 12)
            draw_header(score)
            food = place_food(snake_s)
            draw_cell(food[0], food[1], FOOD_COL)
            # don't remove tail — snake grows
        else:
            # remove tail
            tail = snake.pop()
            snake_s.discard(tail)
            erase_cell(tail[0], tail[1])

        # ── Redraw head and new neck ──────────────────────────
        if len(snake) > 1:
            draw_cell(snake[1][0], snake[1][1], BODY_COL)   # old head → body
        draw_cell(hx, hy, HEAD_COL)

        draw_border()   # keep border crisp

        # ── Frame rate cap ────────────────────────────────────
        elapsed = utime.ticks_diff(utime.ticks_ms(), t0)
        if elapsed < FRAME_MS:
            utime.sleep_ms(FRAME_MS - elapsed)

    # ── Game over screen ─────────────────────────────────────
    fill(0, 0, W, H, BG)
    msg1 = "GAME OVER"
    msg2 = f"Score: {score}"
    txt(msg1, (W - len(msg1) * CW) // 2, H // 2 - 10, RED,   BG)
    txt(msg2, (W - len(msg2) * CW) // 2, H // 2 + 2,  WHITE, BG)
    utime.sleep_ms(2000)


#  ─────────────────────────────────────────────────────────
#  A nested sub-menu. Add more settings entries by appending
#  to SETTINGS_MENU below.
# ════════════════════════════════════════════════════════════

TEAL   = rgb(0, 160, 140)
DKTEAL = rgb(0,  55,  50)

def draw_settings_menu(items, idx):
    """Same style as main menu but with a teal header."""
    fill(0, 0, W, H, BLACK)
    fill(0, 0, W, TITLE_H, DKTEAL)
    lbl = "SETTINGS"
    txt(lbl, (W - len(lbl)*CW)//2, 3, WHITE, DKTEAL)
    start = max(0, min(idx - 1, len(items) - VISIBLE))
    for row in range(VISIBLE):
        i = start + row
        if i >= len(items): break
        y = TITLE_H + 1 + row * (ROW_H + 1)
        name = items[i]["name"]
        if i == idx:
            fill(0, y, W, ROW_H, DKTEAL); hline(y, TEAL)
            txt(f" >{name[:17]}", 0, y+4, WHITE, DKTEAL)
        else:
            fill(0, y, W, ROW_H, BLACK)
            txt(f"  {name[:17]}", 0, y+4, LTGREY, BLACK)
    if start > 0:                    txt("^", W-CW-1, TITLE_H+2, TEAL, BLACK)
    if start+VISIBLE < len(items):   txt("v", W-CW-1, H-10,      TEAL, BLACK)
    # Back hint
    txt("KEY_B=back", (W-10*CW)//2, H-9, GREY, BLACK)

def open_settings():
    """Enter the settings sub-menu. KEY_B exits back to main menu."""
    sidx = 0
    draw_settings_menu(SETTINGS_MENU, sidx)

    while True:
        if pressed(joy_up):
            sidx = (sidx - 1) % len(SETTINGS_MENU)
            draw_settings_menu(SETTINGS_MENU, sidx)
            utime.sleep_ms(160)

        elif pressed(joy_down):
            sidx = (sidx + 1) % len(SETTINGS_MENU)
            draw_settings_menu(SETTINGS_MENU, sidx)
            utime.sleep_ms(160)

        elif pressed(key_a):
            utime.sleep_ms(60)
            try:
                SETTINGS_MENU[sidx]["fn"]()
            except Exception as e:
                draw_error(str(e))
            utime.sleep_ms(250)
            draw_settings_menu(SETTINGS_MENU, sidx)

        elif pressed(key_b):
            # Exit settings — main loop redraws the main menu
            utime.sleep_ms(80)
            return

        utime.sleep_ms(10)

# ════════════════════════════════════════════════════════════
#  BRIGHTNESS SETTING
#  ─────────────────────────────────────────────────────────
#  JOY_LEFT / JOY_RIGHT adjusts brightness in 10% steps.
#  Current level shown as a live bar on the LCD.
#  KEY_A or KEY_B confirms and returns to settings menu.
# ════════════════════════════════════════════════════════════

def draw_brightness_screen(pct):
    fill(0, 0, W, H, BLACK)
    fill(0, 0, W, TITLE_H, DKTEAL)
    lbl = "BRIGHTNESS"
    txt(lbl, (W - len(lbl)*CW)//2, 3, WHITE, DKTEAL)
    val = f"{pct:3d}%"
    txt(val, (W - len(val)*CW)//2, 22, TEAL, BLACK)
    BAR_X, BAR_Y, BAR_W, BAR_H = 10, 38, W - 20, 10
    fill(BAR_X, BAR_Y, BAR_W, BAR_H, GREY)
    bw = int(BAR_W * pct / 100)
    if bw:
        col = rgb(0, int(160 * pct / 100), int(140 * pct / 100))
        fill(BAR_X, BAR_Y, bw, BAR_H, col)
    for t in (25, 50, 75):
        tx = BAR_X + int(BAR_W * t / 100)
        fill(tx, BAR_Y + BAR_H, 1, 4, LTGREY)
    txt("0",      BAR_X,                 BAR_Y + BAR_H + 5, LTGREY, BLACK)
    txt("100%",   BAR_X + BAR_W - 4*CW, BAR_Y + BAR_H + 5, LTGREY, BLACK)
    txt("JOY </> adjust",  (W - 15*CW)//2, H - 17, GREY, BLACK)
    txt("KEY_A/B = done",  (W - 14*CW)//2, H - 8,  GREY, BLACK)

def setting_brightness():
    pct = BRIGHTNESS
    draw_brightness_screen(pct)
    while True:
        changed = False
        if pressed(joy_right):
            pct = min(100, pct + 10); changed = True
        elif pressed(joy_left):
            pct = max(0,   pct - 10); changed = True
        if changed:
            set_brightness(pct)
            draw_brightness_screen(pct)
            utime.sleep_ms(150)
        if pressed(key_a) or pressed(key_b):
            _save_brightness(pct)   # persist across reboots
            utime.sleep_ms(80)
            return
        utime.sleep_ms(10)

# ── Settings entries — add more here ─────────────────────────
SETTINGS_MENU = [
    {"name": "WiFi Dashboard", "fn": script_wifi_info},
    {"name": "Brightness",     "fn": setting_brightness},
    # {"name": "My Setting",   "fn": my_setting_fn},
]

# ════════════════════════════════════════════════════════════
#  MENU — add your own entries here
# ════════════════════════════════════════════════════════════
MENU = [
    {"name": "Settings",      "fn": open_settings},
    # ── HID Macros ──────────────────────────────────────────
    {"name": "Macro:GitHub",  "fn": macro_github},
    {"name": "Macro:YouTube", "fn": macro_youtube},
    {"name": "Macro:Cmd",     "fn": macro_cmd},
    {"name": "Macro:Lock PC", "fn": macro_lock},
    # ── Games ───────────────────────────────────────────────
    {"name": "Pong",          "fn": script_pong},
    {"name": "Snake",         "fn": script_snake},
]

# ════════════════════════════════════════════════════════════
#  WIFI ACCESS POINT
# ════════════════════════════════════════════════════════════
def start_ap():
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(ssid=AP_SSID, password=AP_PASSWORD,
              security=network.WLAN.SEC_WPA2)
    for _ in range(30):
        if ap.active(): break
        utime.sleep_ms(200)
    ip = ap.ifconfig()[0]
    with _lock:
        state["wifi_ip"] = ip
    return ip

# ════════════════════════════════════════════════════════════
#  WEB DASHBOARD HTML  (served from RAM)
# ════════════════════════════════════════════════════════════
_HTML = """\
<!DOCTYPE html><html lang="en">
<head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pico 2 W Dashboard</title>
<style>
:root{--bg:#0a0f0a;--panel:#111811;--green:#39ff14;--dim:#1a7a09;
      --faint:#0d3d06;--orange:#ffb347;--red:#ff4444;--teal:#00dce0;
      --purple:#bb44ff;--grey:#555;--white:#e8f4ee}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--white);font-family:monospace;
     min-height:100vh;padding:16px}
h1{color:var(--green);font-size:20px;letter-spacing:.2em;
   text-shadow:0 0 14px rgba(57,255,20,.5);margin-bottom:3px}
.sub{color:var(--dim);font-size:10px;letter-spacing:.15em;margin-bottom:18px}
.card{background:var(--panel);border:1px solid #1e3a1e;border-radius:8px;
      padding:14px;margin-bottom:12px}
.card h2{font-size:10px;letter-spacing:.2em;color:var(--teal);margin-bottom:10px}
.row{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.dot{width:10px;height:10px;border-radius:50%;background:var(--grey);
     box-shadow:0 0 5px var(--grey);transition:all .3s}
.dot.on{background:var(--green);box-shadow:0 0 10px var(--green)}
#sname{font-size:13px}
.bw{background:#1a1a1a;border-radius:4px;height:7px;overflow:hidden}
.bar{height:100%;background:var(--green);width:0%;transition:width .4s;border-radius:4px}
#detail{font-size:10px;color:var(--teal);margin-top:5px;min-height:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:7px}
.btn{padding:9px 7px;border-radius:6px;border:1px solid #1e4a1e;
     background:#0a1e0a;color:var(--green);font-family:monospace;
     font-size:10px;cursor:pointer;text-align:left;transition:all .12s}
.btn:hover{background:var(--faint);box-shadow:0 0 8px rgba(57,255,20,.15)}
.btn:active{opacity:.7}
.btn.macro{border-color:#4a0064;color:var(--purple);background:#0e0018}
.btn.wifi{border-color:#005858;color:var(--teal);background:#001818}
.stop{width:100%;padding:10px;border-radius:6px;border:1px solid #500;
      background:#1a0000;color:var(--red);font-family:monospace;
      font-size:12px;cursor:pointer;letter-spacing:.1em;transition:all .12s}
.stop:hover{background:#2a0000}
.stats-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px}
.stat{background:#0a1a0a;border:1px solid #1a3a1a;border-radius:6px;
      padding:8px;text-align:center}
.stat-val{font-size:16px;color:var(--green);letter-spacing:.05em}
.stat-lbl{font-size:9px;color:var(--dim);margin-top:3px;letter-spacing:.1em}
.mem-bar-wrap{margin-top:6px}
.mem-bar-bg{background:#1a1a1a;border-radius:3px;height:4px;overflow:hidden;margin-top:2px}
.mem-bar{height:100%;background:var(--teal);width:0%;border-radius:3px;transition:width .6s}
textarea{width:100%;background:#0a1a0a;border:1px solid #1a4a1a;border-radius:6px;
         color:var(--green);font-family:monospace;font-size:12px;padding:10px;
         resize:vertical;outline:none;min-height:70px}
textarea:focus{border-color:var(--green)}
.send-row{display:flex;gap:8px;margin-top:8px;align-items:center}
.send-btn{padding:9px 18px;border-radius:6px;border:1px solid #1e6a1e;
          background:#0a2e0a;color:var(--green);font-family:monospace;
          font-size:11px;cursor:pointer;letter-spacing:.08em;transition:all .12s}
.send-btn:hover{background:var(--faint)}
.send-btn:active{opacity:.7}
#macro-status{font-size:10px;color:var(--teal);min-height:14px}
#log{height:190px;overflow-y:auto;font-size:10px;line-height:1.7;color:var(--dim)}
#log .l{color:var(--green)}#log .s{color:var(--teal)}#log .e{color:var(--red)}
::-webkit-scrollbar{width:3px}::-webkit-scrollbar-thumb{background:var(--dim)}
</style></head>
<body>
<h1>&#9670; PICO 2 W DASHBOARD</h1>
<p class="sub">AP Mode &middot; 192.168.4.1 &middot; ST7735S 160x80</p>

<div class="card">
  <h2>STATUS</h2>
  <div class="row"><div class="dot" id="dot"></div><span id="sname">Idle</span></div>
  <div class="bw"><div class="bar" id="bar"></div></div>
  <div id="detail"></div>
</div>

<div class="card">
  <h2>SYSTEM STATS</h2>
  <div class="stats-grid">
    <div class="stat">
      <div class="stat-val" id="st-uptime">--</div>
      <div class="stat-lbl">UPTIME</div>
    </div>
    <div class="stat">
      <div class="stat-val" id="st-mem">-- KB</div>
      <div class="stat-lbl">FREE RAM</div>
      <div class="mem-bar-wrap">
        <div class="mem-bar-bg"><div class="mem-bar" id="mem-bar"></div></div>
      </div>
    </div>
    <div class="stat">
      <div class="stat-val" id="st-rssi">-- dBm</div>
      <div class="stat-lbl">WIFI RSSI</div>
    </div>
  </div>
</div>

<div class="card">
  <h2>SCRIPTS &amp; MACROS</h2>
  <div class="grid" id="btns"></div>
</div>

<div class="card">
  <h2>CUSTOM MACRO — TYPE &amp; SEND</h2>
  <textarea id="macro-text" placeholder="Type anything here... the Pico will type it out via USB keyboard"></textarea>
  <div class="send-row">
    <button class="send-btn" onclick="sendMacro()">&#9654; SEND TO PICO</button>
    <span id="macro-status"></span>
  </div>
</div>

<div class="card">
  <h2>STOP</h2>
  <button class="stop" onclick="fetch('/stop')">&#9632; STOP RUNNING SCRIPT</button>
</div>
<div class="card"><h2>LIVE LOG</h2><div id="log"></div></div>

<script>
const MENU=[
  {n:"WiFi Dashboard",t:"w"},
  {n:"Macro:GitHub",t:"m"},{n:"Macro:YouTube",t:"m"},
  {n:"Macro:Cmd",t:"m"},{n:"Macro:Lock PC",t:"m"},
  {n:"Pong",t:"s",hidden:true},
  {n:"Snake",t:"s",hidden:true},
];
const g=document.getElementById('btns');
MENU.forEach((item,i)=>{
  if(item.hidden) return;
  const b=document.createElement('button');
  b.className='btn'+(item.t==='m'?' macro':item.t==='w'?' wifi':'');
  b.textContent=(item.t==='m'?'\u2328 ':'\u25b6 ')+item.n;
  b.onclick=()=>fetch('/run?idx='+i);
  g.appendChild(b);
});
const logEl=document.getElementById('log');
function addLog(msg,cls='l'){
  const d=document.createElement('div');
  d.className=cls;d.textContent='> '+msg;
  logEl.appendChild(d);logEl.scrollTop=logEl.scrollHeight;
  while(logEl.children.length>120)logEl.removeChild(logEl.firstChild);
}
const es=new EventSource('/events');
es.onmessage=e=>{try{addLog(JSON.parse(e.data));}catch{addLog(e.data);}};
es.onerror=()=>addLog('reconnecting...','e');
function poll(){
  fetch('/status').then(r=>r.json()).then(d=>{
    document.getElementById('dot').className='dot'+(d.running?' on':'');
    document.getElementById('sname').textContent=d.running?d.script:'Idle';
    document.getElementById('bar').style.width=d.pct+'%';
    document.getElementById('detail').textContent=d.detail||'';
  }).catch(()=>{}).finally(()=>setTimeout(poll,900));
}
function pollStats(){
  fetch('/stats').then(r=>r.json()).then(d=>{
    const s=d.uptime_s;
    const h=Math.floor(s/3600),m=Math.floor((s%3600)/60),sc=s%60;
    document.getElementById('st-uptime').textContent=
      (h?h+'h ':'')+(m?m+'m ':'')+sc+'s';
    document.getElementById('st-mem').textContent=
      Math.round(d.free_kb)+' KB';
    const used=Math.round((1-d.free_kb/d.total_kb)*100);
    document.getElementById('mem-bar').style.width=used+'%';
    document.getElementById('st-rssi').textContent=d.rssi+' dBm';
  }).catch(()=>{}).finally(()=>setTimeout(pollStats,3000));
}
function sendMacro(){
  const text=document.getElementById('macro-text').value.trim();
  if(!text){document.getElementById('macro-status').textContent='Nothing to send';return;}
  document.getElementById('macro-status').textContent='Sending...';
  fetch('/macro',{method:'POST',headers:{'Content-Type':'text/plain'},body:text})
    .then(r=>r.text()).then(()=>{
      document.getElementById('macro-status').textContent='Sent! Pico is typing...';
      addLog('[WEB] Custom macro: '+text.substring(0,40)+(text.length>40?'...':''),'s');
    }).catch(()=>{
      document.getElementById('macro-status').textContent='Error — is Pico busy?';
    });
}
poll();
pollStats();
addLog('Dashboard connected','s');
</script></body></html>
"""

# ════════════════════════════════════════════════════════════
#  WEB SERVER  (runs on core 1)
# ════════════════════════════════════════════════════════════
def _parse_path(raw):
    try:    return raw.split(b"\r\n")[0].decode().split(" ")[1]
    except: return "/"

def _respond(conn, code, ctype, body):
    if isinstance(body, str): body = body.encode()
    conn.sendall((
        f"HTTP/1.1 {code}\r\nContent-Type: {ctype}\r\n"
        f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n"
    ).encode() + body)

def web_server_thread():
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", SERVER_PORT))
    srv.listen(4)
    srv.settimeout(0.5)
    log_push("Web server ready on :80")

    while True:
        try:
            conn, _ = srv.accept()
        except OSError:
            continue
        try:
            conn.settimeout(3.0)
            path = _parse_path(conn.recv(512))

            if path in ("/", "/index.html"):
                _respond(conn, "200 OK", "text/html", _HTML)

            elif path == "/status":
                with _lock:
                    d = json.dumps({
                        "running": state["running"],
                        "script":  state["script"],
                        "detail":  state["detail"],
                        "pct":     state["pct"],
                    })
                _respond(conn, "200 OK", "application/json", d)

            elif path.startswith("/run"):
                try:    idx = int(path.split("idx=")[1])
                except: idx = -1
                with _lock:
                    busy = state["running"]
                if not busy and 0 <= idx < len(MENU):
                    with _lock:
                        state["web_trigger"] = idx
                _respond(conn, "200 OK", "text/plain", "ok")

            elif path == "/stop":
                with _lock:
                    state["stop"] = True
                _respond(conn, "200 OK", "text/plain", "ok")

            elif path == "/stats":
                import gc
                gc.collect()
                ap = network.WLAN(network.AP_IF)
                try:    rssi = ap.status('rssi')
                except: rssi = 0
                uptime_s = utime.ticks_diff(utime.ticks_ms(), _boot_ms) // 1000
                free_kb  = gc.mem_free() // 1024
                total_kb = (gc.mem_free() + gc.mem_alloc()) // 1024
                d = json.dumps({
                    "uptime_s": uptime_s,
                    "free_kb":  free_kb,
                    "total_kb": total_kb,
                    "rssi":     rssi,
                })
                _respond(conn, "200 OK", "application/json", d)

            elif path == "/macro":
                # Read POST body (custom text to type via HID)
                raw = conn.recv(1024).decode(errors="ignore")
                # Body is after the blank line
                if "\r\n\r\n" in raw:
                    body = raw.split("\r\n\r\n", 1)[1].strip()
                else:
                    body = ""
                with _lock:
                    busy = state["running"]
                if body and not busy:
                    with _lock:
                        state["web_macro"] = body[:200]   # cap at 200 chars
                    _respond(conn, "200 OK", "text/plain", "ok")
                else:
                    _respond(conn, "503 Busy", "text/plain", "busy")


                conn.settimeout(None)
                conn.sendall((
                    "HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n"
                    "Cache-Control: no-cache\r\nConnection: keep-alive\r\n\r\n"
                ).encode())
                with _lock:
                    backlog = list(state["log"])
                for line in backlog:
                    try: conn.send(f"data: {json.dumps(line)}\n\n".encode())
                    except: break
                with _lock:
                    state["clients"].append(conn)
                conn = None   # keep SSE socket open

            else:
                _respond(conn, "404 Not Found", "text/plain", "not found")

        except Exception:
            pass
        finally:
            if conn:
                try: conn.close()
                except: pass

# ════════════════════════════════════════════════════════════
#  BOOT & MAIN LOOP
# ════════════════════════════════════════════════════════════
show_boot_animation()

# Start WiFi AP (shown on LCD during splash residual)
ip = start_ap()
log_push(f"AP ready: {AP_SSID} @ {ip}")

# Start web server on core 1
_thread.start_new_thread(web_server_thread, ())

idx = 0
draw_menu(MENU, idx)

while True:
    # ── Web-triggered custom macro ───────────────────────────
    web_text = None
    with _lock:
        if state["web_macro"] is not None and not state["running"]:
            web_text = state["web_macro"]
            state["web_macro"] = None
    if web_text is not None:
        log_push(f"[WEB] Custom macro: {web_text[:40]}")
        run_macro({
            "name":  "Web Macro",
            "steps": [("string", web_text)],
        })
        draw_menu(MENU, idx)

    # ── Web-triggered script ─────────────────────────────────
    web_idx = -1
    with _lock:
        if state["web_trigger"] >= 0 and not state["running"]:
            web_idx = state["web_trigger"]
            state["web_trigger"] = -1

    if web_idx >= 0:
        idx = web_idx
        draw_menu(MENU, idx)
        utime.sleep_ms(80)
        name = MENU[idx]["name"]
        set_state(name, "", 0, running=True)
        with _lock: state["stop"] = False
        log_push(f"[WEB] {name}")
        try:
            MENU[idx]["fn"]()
        except Exception as e:
            draw_error(str(e)); log_push(f"ERROR: {e}")
        set_state("", "", 0, running=False)
        with _lock: state["stop"] = False
        log_push(f"[WEB] done: {name}")
        draw_menu(MENU, idx)

    # ── Physical joystick ────────────────────────────────────
    if pressed(joy_up):
        idx = (idx - 1) % len(MENU)
        draw_menu(MENU, idx); utime.sleep_ms(160)

    elif pressed(joy_down):
        idx = (idx + 1) % len(MENU)
        draw_menu(MENU, idx); utime.sleep_ms(160)

    elif pressed(key_a):
        utime.sleep_ms(60)
        name = MENU[idx]["name"]
        set_state(name, "", 0, running=True)
        with _lock: state["stop"] = False
        log_push(f"[BTN] {name}")
        try:
            MENU[idx]["fn"]()
        except Exception as e:
            draw_error(str(e)); log_push(f"ERROR: {e}")
        set_state("", "", 0, running=False)
        with _lock: state["stop"] = False
        log_push(f"[BTN] done: {name}")
        draw_menu(MENU, idx)

    utime.sleep_ms(10)

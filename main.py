import time
from collections import deque

import cv2
import numpy as np

WINDOW_NAME = "Hedef Takip"
CLOSE_BUTTON = (20, 20, 120, 50)   # x, y, w, h
MIN_SELECTION = 15                 # piksel, bundan kucuk secimler yok sayilir
TRAIL_LENGTH = 40                  # iz cizgisinde tutulacak nokta sayisi

# ---- Hedef dogrulama / yeniden yakalama ayarlari (gerekirse buradan oynayin) ----
APPEARANCE_MIN = 0.45      # takip kutusunun hedefe benzerlik esigi (renk korelasyonu, -1..1)
LOST_FRAMES = 6            # ust uste bu kadar dusuk skor -> hedef kayip sayilir
REACQUIRE_NCC = 0.60       # yeniden yakalamada sablon eslesme esigi
REACQUIRE_HIST = 0.55      # yeniden yakalamada renk benzerlik esigi
SEARCH_EVERY = 2           # kayipken her N karede bir tum kareyi tara
SEARCH_DOWNSCALE = 0.5     # tarama hizi icin kareyi kucult
SEARCH_SCALES = (0.6, 0.7, 0.8, 0.9, 1.0, 1.15, 1.3, 1.5, 1.75)
REFRESH_EVERY = 20         # guvenliyken "son gorunum" sablonunu yenileme araligi (kare)
REFRESH_MIN_SCORE = 0.80   # yenileme icin gereken minimum benzerlik


# --------------------------------------------------------------------------
# Yardimci fonksiyonlar
# --------------------------------------------------------------------------
def create_tracker():
    """Kurulu OpenCV surumundeki en iyi takipciyi dondurur: (tracker, isim)."""
    for name in ("TrackerCSRT_create", "TrackerKCF_create", "TrackerMIL_create"):
        for owner in (cv2, getattr(cv2, "legacy", None)):
            factory = getattr(owner, name, None) if owner is not None else None
            if factory is not None:
                return factory(), name.replace("Tracker", "").replace("_create", "")
    return None, None


def draw_dashed_line(image, start_point, end_point, color, thickness=2, dash_length=18, gap_length=10):
    x1, y1 = start_point
    x2, y2 = end_point
    total_length = int(np.hypot(x2 - x1, y2 - y1))
    if total_length == 0:
        return

    dx = (x2 - x1) / total_length
    dy = (y2 - y1) / total_length

    for distance in range(0, total_length, dash_length + gap_length):
        seg_end = min(distance + dash_length, total_length)
        start = (int(x1 + dx * distance), int(y1 + dy * distance))
        end = (int(x1 + dx * seg_end), int(y1 + dy * seg_end))
        cv2.line(image, start, end, color, thickness, cv2.LINE_AA)


def draw_dashed_rect(image, box, color, thickness=2):
    x, y, w, h = box
    draw_dashed_line(image, (x, y), (x + w, y), color, thickness, 8, 6)
    draw_dashed_line(image, (x + w, y), (x + w, y + h), color, thickness, 8, 6)
    draw_dashed_line(image, (x + w, y + h), (x, y + h), color, thickness, 8, 6)
    draw_dashed_line(image, (x, y + h), (x, y), color, thickness, 8, 6)


def draw_crosshair(image, center, color, size=18, thickness=2):
    cx, cy = center
    cv2.line(image, (cx - size, cy), (cx + size, cy), color, thickness, cv2.LINE_AA)
    cv2.line(image, (cx, cy - size), (cx, cy + size), color, thickness, cv2.LINE_AA)
    cv2.circle(image, (cx, cy), size // 2, color, thickness, cv2.LINE_AA)


def put_text(image, text, org, color=(255, 255, 255), scale=0.7, thickness=2):
    # Okunurluk icin once siyah kontur, sonra asil yazi
    cv2.putText(image, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thickness + 2, cv2.LINE_AA)
    cv2.putText(image, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)


def clamp_box(box, width, height):
    """(x, y, w, h) kutusunu kare sinirlari icine sikistirir; gecersizse None."""
    x, y, w, h = [int(round(v)) for v in box]
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(width, x + w), min(height, y + h)
    if x2 - x1 < MIN_SELECTION or y2 - y1 < MIN_SELECTION:
        return None
    return (x1, y1, x2 - x1, y2 - y1)


# --------------------------------------------------------------------------
# Hedef gorunum modeli: takibi dogrulamak ve kayipsa yeniden bulmak icin
# --------------------------------------------------------------------------
def compute_hist(bgr):
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1, 2], None, [12, 6, 6], [0, 180, 0, 256, 0, 256])
    cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
    return hist


class TargetModel:
    """Iki referans tutar: [0] ilk secim (asla degismez), [1] en son guvenilir gorunum."""

    def __init__(self, frame, box):
        x, y, w, h = box
        crop = frame[y:y + h, x:x + w].copy()
        self.templates = [crop, crop.copy()]
        self.hists = [compute_hist(crop), compute_hist(crop)]
        self.last_box = box

    def refresh(self, frame, box):
        x, y, w, h = box
        crop = frame[y:y + h, x:x + w]
        if crop.size == 0:
            return
        self.templates[1] = crop.copy()
        self.hists[1] = compute_hist(crop)

    def score(self, frame, box):
        """Kutunun icindeki goruntunun hedefe renk benzerligi (-1..1)."""
        x, y, w, h = box
        crop = frame[y:y + h, x:x + w]
        if crop.size == 0:
            return -1.0
        hist = compute_hist(crop)
        return max(cv2.compareHist(ref, hist, cv2.HISTCMP_CORREL) for ref in self.hists)

    def search(self, frame):
        """Tum karede coklu olcekli sablon eslesmesi. (skor, kutu) dondurur."""
        ds = SEARCH_DOWNSCALE
        small = cv2.resize(frame, None, fx=ds, fy=ds, interpolation=cv2.INTER_AREA)
        sh, sw = small.shape[:2]
        best_val, best_box = -1.0, None

        for tpl in self.templates:
            for s in SEARCH_SCALES:
                tw = int(tpl.shape[1] * s * ds)
                th = int(tpl.shape[0] * s * ds)
                if tw < 8 or th < 8 or tw >= sw or th >= sh:
                    continue
                resized = cv2.resize(tpl, (tw, th), interpolation=cv2.INTER_AREA)
                result = cv2.matchTemplate(small, resized, cv2.TM_CCOEFF_NORMED)
                _, val, _, loc = cv2.minMaxLoc(result)
                if not np.isfinite(val):
                    continue
                if val > best_val:
                    best_val = val
                    best_box = (int(loc[0] / ds), int(loc[1] / ds), int(tw / ds), int(th / ds))
        return best_val, best_box


# --------------------------------------------------------------------------
# Fare durumu (global degisken yerine tek bir nesne)
# --------------------------------------------------------------------------
class MouseState:
    def __init__(self):
        self.start = None        # surukleme baslangici
        self.end = None          # anlik fare konumu
        self.new_roi = None      # tamamlanmis yeni secim (x, y, w, h)
        self.close_requested = False


def on_mouse(event, x, y, flags, state):
    if event == cv2.EVENT_LBUTTONDOWN:
        bx, by, bw, bh = CLOSE_BUTTON
        if bx <= x <= bx + bw and by <= y <= by + bh:
            state.close_requested = True   # callback icinde SystemExit firlatmak guvensiz
            return
        state.start = (x, y)
        state.end = (x, y)

    elif event == cv2.EVENT_MOUSEMOVE and state.start is not None:
        state.end = (x, y)

    elif event == cv2.EVENT_LBUTTONUP and state.start is not None:
        x1, y1 = state.start
        left, top = min(x1, x), min(y1, y)
        right, bottom = max(x1, x), max(y1, y)
        if right - left >= MIN_SELECTION and bottom - top >= MIN_SELECTION:
            state.new_roi = (left, top, right - left, bottom - top)
        state.start = None
        state.end = None


# --------------------------------------------------------------------------
# Ana program
# --------------------------------------------------------------------------
def open_camera():
    capture = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not capture.isOpened():
        capture = cv2.VideoCapture(0)
    if not capture.isOpened():
        raise RuntimeError("Web kamera acilamadi.")
    return capture


def start_tracker(frame, box):
    tracker, name = create_tracker()
    if tracker is None:
        raise RuntimeError("Takipci bulunamadi. Kurun: pip install opencv-contrib-python")
    tracker.init(frame, box)
    return tracker, name


def main():
    capture = open_camera()
    state = MouseState()

    tracker = None
    tracker_name = None
    model = None
    target_box = None                       # (x, y, w, h)
    status = "SELECT"                       # SELECT | TRACKING | SEARCHING
    trail = deque(maxlen=TRAIL_LENGTH)

    low_count = 0                           # ust uste dusuk benzerlik sayaci
    frame_idx = 0
    since_refresh = 0
    last_search_val = None
    last_time = time.time()
    fps = 0.0

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(WINDOW_NAME, on_mouse, state)

    def reset_target():
        nonlocal tracker, model, target_box, status, low_count, last_search_val
        tracker = None
        model = None
        target_box = None
        status = "SELECT"
        low_count = 0
        last_search_val = None
        trail.clear()

    def go_searching():
        nonlocal tracker, target_box, status
        tracker = None
        target_box = None
        status = "SEARCHING"
        trail.clear()

    try:
        while True:
            ok, raw = capture.read()
            if not ok:
                break

            raw = cv2.flip(raw, 1)
            height, width = raw.shape[:2]
            frame_idx += 1
            since_refresh += 1

            # Takipci temiz kareyi gorur, cizimler ayri kopyaya yapilir
            frame = raw.copy()

            # ---- Yeni secim geldiyse modeli ve takipciyi baslat ----
            if state.new_roi is not None:
                box = clamp_box(state.new_roi, width, height)
                state.new_roi = None
                if box is not None:
                    tracker, tracker_name = start_tracker(raw, box)
                    model = TargetModel(raw, box)
                    target_box = box
                    status = "TRACKING"
                    low_count = 0
                    since_refresh = 0
                    trail.clear()

            confident = False

            # ---- Takip + dogrulama ----
            if status == "TRACKING" and tracker is not None:
                found, new_box = tracker.update(raw)
                box = clamp_box(new_box, width, height) if found else None

                if box is None:
                    low_count = LOST_FRAMES
                else:
                    score = model.score(raw, box)
                    if score >= APPEARANCE_MIN:
                        low_count = 0
                        confident = True
                        target_box = box
                        model.last_box = box
                        if score >= REFRESH_MIN_SCORE and since_refresh >= REFRESH_EVERY:
                            model.refresh(raw, box)
                            since_refresh = 0
                    else:
                        low_count += 1
                        target_box = box   # gosterilir ama "zayif" olarak

                if low_count >= LOST_FRAMES:
                    go_searching()

            # ---- Kayipken: tum karede hedefi ara, bulursan takibe devam et ----
            elif status == "SEARCHING" and model is not None:
                if frame_idx % SEARCH_EVERY == 0:
                    val, cand = model.search(raw)
                    last_search_val = val
                    if cand is not None and val >= REACQUIRE_NCC:
                        cand = clamp_box(cand, width, height)
                        if cand is not None and model.score(raw, cand) >= REACQUIRE_HIST:
                            tracker, tracker_name = start_tracker(raw, cand)
                            target_box = cand
                            model.last_box = cand
                            status = "TRACKING"
                            low_count = 0
                            since_refresh = 0
                            confident = True

            # ---- Cizimler ----
            draw_crosshair(frame, (width // 2, height // 2), (255, 255, 255))

            if status == "TRACKING" and target_box is not None:
                x, y, w, h = target_box
                cx, cy = x + w // 2, y + h // 2
                color = (0, 255, 255) if confident else (0, 165, 255)

                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                put_text(frame, "LOCKED" if confident else "ZAYIF", (x, max(25, y - 10)), color, 0.6)
                cv2.circle(frame, (cx, cy), 4, color, -1, cv2.LINE_AA)

                if confident:
                    trail.append((cx, cy))
                for i in range(1, len(trail)):
                    cv2.line(frame, trail[i - 1], trail[i], (0, 200, 255), 2, cv2.LINE_AA)

            elif status == "SEARCHING" and model is not None:
                draw_dashed_rect(frame, model.last_box, (0, 0, 255), 2)

            # Surukleme sirasindaki secim kutusu
            if state.start is not None and state.end is not None:
                cv2.rectangle(frame, state.start, state.end, (255, 0, 0), 2)

            # Tek satir durum mesaji (sol alt)
            if status == "SELECT":
                put_text(frame, "Hedef secmek icin alan cizin", (20, height - 20), (255, 255, 255), 0.6)
            elif status == "SEARCHING":
                msg = "Hedef kayip, araniyor..."
                if last_search_val is not None:
                    msg += f" ({last_search_val:.2f}/{REACQUIRE_NCC:.2f})"
                put_text(frame, msg, (20, height - 20), (0, 165, 255), 0.6)

            # Sag ust: FPS
            now = time.time()
            fps = 0.9 * fps + 0.1 * (1.0 / max(now - last_time, 1e-6))
            last_time = now
            put_text(frame, f"FPS {fps:.0f}", (width - 100, 30), (0, 255, 0), 0.6)

            # Kapat butonu (sol ust)
            bx, by, bw, bh = CLOSE_BUTTON
            cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (0, 0, 255), 2)
            put_text(frame, "CLOSE", (bx + 28, by + 32), (0, 0, 255))

            cv2.imshow(WINDOW_NAME, frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27) or state.close_requested:
                break
            if key == ord("r"):
                reset_target()
            # Pencere X ile kapatildiysa
            if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break

    finally:
        capture.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
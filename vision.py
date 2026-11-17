"""Screen capture + badge OCR. Replaces the old data_ingestion.py / classifier.py."""
import cv2
import dxcam
import numpy as np

import config

_reader = None


def _ocr():
    global _reader
    if _reader is None:
        import easyocr
        _reader = easyocr.Reader(["en"], verbose=False)
    return _reader


def crop(frame, box):
    l, t, r, b = box
    return frame[t:b, l:r]


def parse_total(text):
    """Turn OCR badge text into a hand total (int), 'BJ', or None.

    Soft hands are shown as 'low/high' (e.g. '5/15' or '10/20'). If the slash is
    read directly we take the part after '/'; if OCR drops the slash or misreads it
    as a digit ('515', '5115', '10120'), the high value is still the last two digits
    (12..20), so we take those. 'BJ' (natural blackjack) is returned as 'BJ'.
    """
    text = text.strip().upper()
    if not text:
        return None
    if "J" in text or text == "BJ":
        return "BJ"
    # Guard against '8' being read as 'B' when 'B' is in the allowlist
    text = text.replace("B", "8")
    if "/" in text:
        text = text.split("/")[-1].strip()
    if not text.isdigit():
        return None
    if len(text) <= 2:
        value = int(text)
    elif len(text) <= 5:
        value = int(text[-2:])
    else:
        return None
    return value if 1 < value <= 31 else None


def read_total(img_rgb):
    """OCR a total badge crop. Returns an int, 'BJ', or None if unreadable."""
    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
    gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    # Badge text is brighter than its background in some states and dimmer in
    # others, so normalise contrast instead of using a fixed threshold.
    gray = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4)).apply(gray)
    out = _ocr().readtext(gray, detail=0, allowlist="0123456789BJ/")
    return parse_total("".join(out))


def classify_color(img_rgb):
    """Dominant border colour of the player badge.

    Returns 'blue' (hand in play), 'green' (win), 'yellow' (push), 'red' (loss),
    or None if there is no clearly coloured border (e.g. badge absent).
    """
    hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    sat = (s > 110) & (v > 90)
    if sat.sum() < 40:
        return None
    hue = h[sat]                     # OpenCV hue range is 0-179
    counts = {
        "red": int(((hue < 10) | (hue > 165)).sum()),
        "yellow": int(((hue >= 15) & (hue <= 35)).sum()),
        "green": int(((hue >= 40) & (hue <= 85)).sum()),
        "blue": int(((hue >= 95) & (hue <= 130)).sum()),
    }
    best = max(counts, key=counts.get)
    return best if counts[best] >= 40 else None


def classify_action(img_rgb):
    """Last-action icon above the player's cards.

    Green downward arrow = 'hit', red palm = 'stand', nothing = None.
    The icon slides sideways with the number of cards, so pass a wide band that
    spans every possible position but stays above the cards (and their borders).
    """
    hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    sat = (s > 100) & (v > 90)
    green = int((sat & (h >= 40) & (h <= 85)).sum())
    red = int((sat & ((h < 10) | (h > 165))).sum())
    if max(green, red) < config.ICON_MIN_PIXELS:
        return None
    return "hit" if green > red else "stand"


class Screen:
    """Grabs frames and turns them into (player, dealer) readings.

    OCR only runs when a badge crop actually changed, which keeps polling cheap.
    """

    def __init__(self):
        self.camera = dxcam.create()
        self.frame = None
        self._cache = {}   # name -> (crop bytes hash, value)

    def grab(self):
        f = self.camera.grab(region=config.REGION)   # None if screen unchanged
        if f is not None:
            self.frame = f
        return self.frame

    def _cached(self, name, box, fn):
        img = crop(self.frame, box)
        key = img.tobytes()
        cached = self._cache.get(name)
        if cached and cached[0] == key:
            return cached[1]
        value = fn(img)
        self._cache[name] = (key, value)
        return value

    def read_badges(self):
        """Returns (player_total, dealer_total, border_colour, last_action); any may be None."""
        if self.grab() is None:
            return None, None, None, None
        return (self._cached("player", config.PLAYER_BADGE, read_total),
                self._cached("dealer", config.DEALER_BADGE, read_total),
                self._cached("color", config.PLAYER_BADGE, classify_color),
                self._cached("action", config.ACTION_BAND, classify_action))

"""Central settings. Coordinates are relative to the captured REGION frame."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
HANDS_CSV = os.path.join(DATA_DIR, "hands.csv")
DEBUG_DIR = os.path.join(DATA_DIR, "debug")

# Screen region of the game window: (left, top, right, bottom) in screen pixels
REGION = (1130, 450, 2800, 1540)

# Total badges, as [left, top, right, bottom] inside the REGION frame.
# 160 px wide (centred on x=838) so wider soft-total badges like '10/20' (133 px) fit.
DEALER_BADGE = (760, 350, 920, 425)
PLAYER_BADGE = (760, 950, 920, 1025)
# Wide band above the player's cards where the last-action icon (green arrow = hit,
# red palm = stand) appears; its x position shifts with the card count.
ACTION_BAND = (400, 555, 1300, 628)
ICON_MIN_PIXELS = 60

POLL_HZ = 12

# A badge total is trusted only after it has been identical for this long (seconds).
# Filters out mid-animation and OCR flicker.
STABLE_S = 0.4
# The result border and action icon are short-lived when playing fast, so they latch
# after this many consecutive identical polls instead of the full debounce above.
FAST_HOLD_S = 0.0
FAST_MIN_OBS = 2
# A red result this soon after the deal, with the dealer on 21 and no player
# action, is a dealer blackjack (not a hit/stand decision) and is discarded.
NATURAL_S = 2.5
# Badges missing this long mid-hand -> hand is discarded.
LOST_S = 3.0
# Hard cap on one hand, to avoid getting stuck in a state forever.
MAX_HAND_S = 600

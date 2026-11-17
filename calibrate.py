"""Checks the capture region and badge OCR. Run once after moving the game window.

Saves data/calibration/*.png so you can see exactly what the logger sees.
"""
import os

import cv2

import config
from vision import Screen, classify_action, classify_color, crop, read_total

out = os.path.join(config.DATA_DIR, "calibration")
os.makedirs(out, exist_ok=True)

screen = Screen()
frame = None
while frame is None:
    frame = screen.grab()

def save(name, img):
    cv2.imwrite(os.path.join(out, name), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))

save("frame.png", frame)
for name, box in (("player", config.PLAYER_BADGE), ("dealer", config.DEALER_BADGE)):
    img = crop(frame, box)
    save(f"{name}.png", img)
    print(f"{name} badge reads: {read_total(img)}, border: {classify_color(img)}")
band = crop(frame, config.ACTION_BAND)
save("action_band.png", band)
print(f"action icon: {classify_action(band)}")
print(f"Saved images to {out}")

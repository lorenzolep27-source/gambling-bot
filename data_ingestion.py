import dxcam
import os
import cv2

camera = dxcam.create()
frames = []

# Where screenshots are saved
OUTPUT_DIR = "captures"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Region to capture as (left, top, right, bottom) in screen pixels.
# Set this to the Chrome game window, or None to capture the full monitor.
REGION = (1130, 450, 2800, 1540)
dealerAmount = [610, 350, 730, 425]
playerAmount = [610, 950, 730, 1025]
#dealerAmount = [1740, 800, 1860, 875]
#playerAmount = [1740, 1400, 1860, 1475]

TARGET_FPS = 30
DURATION_SECONDS = 10  # how long to capture before stopping

# --- One-off screenshot ---
# grab() returns a single frame, or None if the screen hasn't changed
# since the last grab, so retry until it returns a frame.
frame = None
while frame is None:
    frame = camera.grab(region=REGION)

# dxcam returns RGB by default, but OpenCV writes BGR, so convert first
cv2.imwrite(os.path.join(OUTPUT_DIR, "screenshot.png"), cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
print(f"Saved screenshot, shape={frame.shape}")  # (height, width, 3)

# Crop both regions out of the same frame (numpy slicing is [top:bottom, left:right])
dealer_frame = frame[dealerAmount[1]:dealerAmount[3], dealerAmount[0]:dealerAmount[2]]
player_frame = frame[playerAmount[1]:playerAmount[3], playerAmount[0]:playerAmount[2]]

# dxcam returns RGB by default, but OpenCV writes BGR, so convert first
cv2.imwrite(os.path.join(OUTPUT_DIR, "dealer_amount.png"), cv2.cvtColor(dealer_frame, cv2.COLOR_RGB2BGR))
cv2.imwrite(os.path.join(OUTPUT_DIR, "player_amount.png"), cv2.cvtColor(player_frame, cv2.COLOR_RGB2BGR))


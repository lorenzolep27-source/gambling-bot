"""Debug window: shows what the logger believes it is capturing and reading.

Not used unless you run `python main.py --debug`. Kept separate from the logging code,
and any failure here disables the window instead of stopping the logger.
"""
import cv2
import numpy as np
import tkinter as tk
from PIL import Image, ImageTk

import config

VIEW_W = 820                       # width the captured frame is shown at
BOX_COLORS = {                     # BGR-agnostic: drawn on an RGB frame
    "player": (0, 200, 255),
    "dealer": (255, 160, 0),
    "action": (255, 0, 255),
}
BORDER_RGB = {"blue": (40, 120, 255), "green": (40, 200, 90), "yellow": (240, 200, 30),
              "red": (230, 50, 60), None: (120, 120, 120)}


class DebugView:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("gambling_bot debug view")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.alive = True
        self.image_label = tk.Label(self.root)
        self.image_label.pack(side="top")
        self.crop_label = tk.Label(self.root)
        self.crop_label.pack(side="top")
        self.text = tk.Label(self.root, justify="left", anchor="w", font=("Consolas", 10),
                             padx=8, pady=6)
        self.text.pack(side="top", fill="x")
        self._photo = None
        self._crop_photo = None

    def _on_close(self):
        self.alive = False
        self.root.destroy()

    # -- drawing -----------------------------------------------------------
    @staticmethod
    def _box(img, box, color, label):
        l, t, r, b = box
        cv2.rectangle(img, (l, t), (r, b), color, 3)
        cv2.putText(img, label, (l, max(20, t - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                    color, 2, cv2.LINE_AA)

    def _frame_image(self, frame, reading):
        player, dealer, color, action = reading
        img = np.ascontiguousarray(frame.copy())
        self._box(img, config.PLAYER_BADGE, BOX_COLORS["player"], f"player={player} {color}")
        self._box(img, config.DEALER_BADGE, BOX_COLORS["dealer"], f"dealer={dealer}")
        self._box(img, config.ACTION_BAND, BOX_COLORS["action"], f"icon={action}")
        h, w = img.shape[:2]
        return cv2.resize(img, (VIEW_W, int(h * VIEW_W / w)), interpolation=cv2.INTER_AREA)

    @staticmethod
    def _crop_strip(frame):
        """The exact pixels the readers see, side by side and enlarged."""
        def get(box, scale):
            l, t, r, b = box
            c = frame[t:b, l:r]
            return cv2.resize(c, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
        parts = [get(config.PLAYER_BADGE, 1.5), get(config.DEALER_BADGE, 1.5),
                 get(config.ACTION_BAND, 0.8)]
        height = max(p.shape[0] for p in parts)
        padded = [cv2.copyMakeBorder(p, 0, height - p.shape[0], 0, 6,
                                     cv2.BORDER_CONSTANT, value=(30, 30, 30)) for p in parts]
        strip = np.hstack(padded)
        if strip.shape[1] > VIEW_W:
            strip = cv2.resize(strip, (VIEW_W, int(strip.shape[0] * VIEW_W / strip.shape[1])))
        return strip

    # -- public ------------------------------------------------------------
    def update(self, frame, reading, tracker, recorder, last_record, last_error):
        """Call once per poll. Returns False once the window has been closed."""
        if not self.alive or frame is None:
            return self.alive

        self._photo = ImageTk.PhotoImage(Image.fromarray(self._frame_image(frame, reading)))
        self.image_label.configure(image=self._photo)
        self._crop_photo = ImageTk.PhotoImage(Image.fromarray(self._crop_strip(frame)))
        self.crop_label.configure(image=self._crop_photo)

        p, d, c, a = reading
        stable = lambda s: s.value if s.has_value else "-"
        self.text.configure(text=(
            f"STATE: {tracker.state.name}\n"
            f"raw      player={p}  dealer={d}  border={c}  icon={a}\n"
            f"stable   player={stable(tracker.p)}  dealer={stable(tracker.d)}  "
            f"border={stable(tracker.c)}  icon={stable(tracker.a)}\n"
            f"hand     dealer_up={tracker.dealer_up}  start={tracker.player_start}  "
            f"now={tracker.player_end}  hits={tracker.n_hit}  icon_stale={tracker.icon_stale}\n"
            f"session  saved={recorder.hand_no}  rejected={recorder.rejected}  "
            f"discarded={tracker.discarded}  mismatches={tracker.mismatches}\n"
            f"last discard: {tracker.last_discard_reason or '-'}\n"
            f"last hand:    {last_record or '-'}\n"
            f"last error:   {last_error or '-'}"
        ), fg="#111")

        try:
            self.root.update()
        except tk.TclError:
            self.alive = False
        return self.alive

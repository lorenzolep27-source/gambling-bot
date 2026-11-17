"""Validates finished hands and appends them to a CSV (load with pandas.read_csv)."""
import csv
import os
import time

import config

COLUMNS = ["session_id", "hand_no", "timestamp", "dealer_show", "player_start",
           "player_end", "n_hit", "stood", "outcome"]


def validate(rec):
    """Returns an error string, or None if the record is internally consistent."""
    if rec.outcome == "bust" and rec.player_end <= 21:
        return "bust but total <= 21"
    if rec.outcome != "bust" and rec.player_end > 21:
        return "total > 21 but not bust"
    if rec.n_hit == 0 and rec.player_end != rec.player_start:
        return "no hits but total changed"
    if rec.n_hit > 0 and rec.player_end == rec.player_start and rec.outcome != "bust":
        pass  # legal: soft hand hit to the same hard total
    if rec.outcome == "bust" and rec.stood:
        return "bust but stood"
    if rec.outcome == "BJ" and (rec.n_hit or rec.player_start != 21):
        return "invalid BJ"
    return None


class Recorder:
    def __init__(self, path=None, session_id=None):
        self.path = path or config.HANDS_CSV
        self.session_id = session_id or time.strftime("%Y%m%d-%H%M%S")
        self.hand_no = 0
        self.rejected = 0
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            with open(self.path, "w", newline="") as f:
                csv.writer(f).writerow(COLUMNS)

    def write(self, rec):
        err = validate(rec)
        if err:
            self.rejected += 1
            return err
        self.hand_no += 1
        row = [self.session_id, self.hand_no, time.strftime("%Y-%m-%d %H:%M:%S"),
               rec.dealer_show, rec.player_start, rec.player_end, rec.n_hit,
               rec.stood, rec.outcome]
        with open(self.path, "a", newline="") as f:
            csv.writer(f).writerow(row)
        return None

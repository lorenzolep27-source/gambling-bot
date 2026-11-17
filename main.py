"""Observe-only blackjack logger. You play; this watches and writes data/hands.csv.

Run:  python main.py            Stop: Ctrl+C
      python main.py --verbose  also print every change in the raw readings
      python main.py --debug    also open a window showing what is being captured
"""
import sys
import time

import config
from recorder import Recorder
from state_machine import HandTracker, Observation
from vision import Screen


def open_debug_view():
    try:
        from debug_view import DebugView
        return DebugView()
    except Exception as e:      # never let the debug window break logging
        print(f"Debug window unavailable: {e}")
        return None


def main():
    verbose = "--verbose" in sys.argv
    view = open_debug_view() if "--debug" in sys.argv else None
    screen = Screen()
    tracker = HandTracker()
    recorder = Recorder()
    period = 1.0 / config.POLL_HZ
    last_state = None
    last_raw = None
    last_discarded = 0
    last_record = last_error = None
    print(f"Logging to {recorder.path} (session {recorder.session_id}). Ctrl+C to stop.")

    try:
        while True:
            started = time.monotonic()
            player, dealer, color, action = screen.read_badges()
            rec = tracker.step(Observation(started, player, dealer, color, action))

            if tracker.discarded != last_discarded:
                print(f"  DISCARDED hand: {tracker.last_discard_reason}")
                last_discarded = tracker.discarded
            raw = (tracker.state, player, dealer, color, action)
            if verbose and raw != last_raw:
                print(f"  raw {time.strftime('%H:%M:%S')} {tracker.state.name:<11} "
                      f"player={player} dealer={dealer} border={color} icon={action}")
                last_raw = raw

            if tracker.state != last_state:
                print(f"[{tracker.state.name}] player={player} dealer={dealer} "
                      f"border={color} icon={action}")
                last_state = tracker.state

            if rec:
                err = recorder.write(rec)
                last_record, last_error = rec, err
                print(f"  hand {recorder.hand_no}: {rec}" if not err
                      else f"  REJECTED ({err}): {rec}")

            if view is not None:
                try:
                    if not view.update(screen.frame, (player, dealer, color, action),
                                       tracker, recorder, last_record, last_error):
                        print("Debug window closed; logging continues.")
                        view = None
                except Exception as e:
                    print(f"Debug window disabled: {e}")
                    view = None

            time.sleep(max(0.0, period - (time.monotonic() - started)))
    except KeyboardInterrupt:
        print(f"\nDone. {recorder.hand_no} hands saved, {recorder.rejected} rejected, "
              f"{tracker.discarded} discarded (last: {tracker.last_discard_reason or 'n/a'}), "
              f"{tracker.mismatches} colour/total mismatches.")


if __name__ == "__main__":
    main()

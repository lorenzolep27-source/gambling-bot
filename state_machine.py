"""Pure game-state logic. No screen or OCR code here, so it is fully unit-testable.

Feed it one Observation per poll via HandTracker.step(); it returns a finished
HandRecord when a hand completes, otherwise None.

The player badge's border colour is the game's own signal:
    blue = hand in play, green = win, yellow = push, red = loss.
A hand ends the moment the colour leaves blue, and the colour gives the result.
The outcome computed from the totals is only a cross-check (see `mismatches`).

States:  WAIT_HAND -> PLAYER_TURN -> (record) -> WAIT_CLEAR -> WAIT_HAND
Only hit and stand are modelled. Hands that don't fit are discarded.
"""
from dataclasses import dataclass, asdict
from enum import Enum, auto
from typing import Optional

import config

BLUE = "blue"


class State(Enum):
    WAIT_HAND = auto()
    PLAYER_TURN = auto()
    WAIT_CLEAR = auto()


@dataclass
class Observation:
    t: float                        # seconds (any monotonic clock)
    player: Optional[int | str]     # raw OCR total of player badge (int or 'BJ'), or None
    dealer: Optional[int | str]     # raw OCR total of dealer badge (int or 'BJ'), or None
    color: Optional[str] = BLUE     # player badge border: blue/green/yellow/red/None
    action: Optional[str] = None    # last-action icon above the cards: "hit" / "stand" / None


@dataclass
class HandRecord:
    dealer_show: str            # "2".."10" or "A"
    player_start: int
    player_end: int
    n_hit: int
    stood: bool
    outcome: str                # win / loss / bust / push / BJ

    def as_dict(self):
        return asdict(self)


class Stable:
    """Returns a value only once it has been seen unchanged for `hold` seconds
    and on at least `min_obs` consecutive polls."""

    def __init__(self, hold, min_obs=1):
        self.hold = hold
        self.min_obs = min_obs
        self.raw = object()     # sentinel: nothing seen yet
        self.since = 0.0
        self.count = 0
        self.value = None       # last accepted (stable) value
        self.has_value = False

    def update(self, raw, t):
        """Returns (value, changed). `value` is the latest stable reading."""
        if raw != self.raw:
            self.raw, self.since, self.count = raw, t, 0
        self.count += 1
        changed = False
        if (t - self.since >= self.hold and self.count >= self.min_obs
                and (not self.has_value or raw != self.value)):
            self.value, self.has_value, changed = raw, True, True
        return self.value, changed


def dealer_label(total):
    return "A" if total == 11 else str(total)


def outcome_from_totals(player_end, dealer_end, blackjack):
    """Cross-check only: what the totals say the result should be."""
    if player_end > 21:
        return "bust"
    if blackjack:
        return "push" if dealer_end == 21 else "BJ"
    if dealer_end > 21 or player_end > dealer_end:
        return "win"
    return "push" if player_end == dealer_end else "loss"


def outcome_from_color(color, player_end, natural):
    if color == "green":
        return "BJ" if natural else "win"
    if color == "yellow":
        return "push"
    if color == "red":
        return "bust" if player_end > 21 else "loss"
    return None


class HandTracker:
    def __init__(self, stable_s=None, lost_s=None, max_hand_s=None, natural_s=None):
        self.stable_s = config.STABLE_S if stable_s is None else stable_s
        self.lost_s = config.LOST_S if lost_s is None else lost_s
        self.max_hand_s = config.MAX_HAND_S if max_hand_s is None else max_hand_s
        self.natural_s = config.NATURAL_S if natural_s is None else natural_s
        self.p = Stable(self.stable_s)
        self.d = Stable(self.stable_s)
        # The result border and action icon are short-lived at fast play, so they latch
        # after a couple of consecutive polls instead of the full totals debounce.
        self.c = Stable(config.FAST_HOLD_S, min_obs=config.FAST_MIN_OBS)
        self.a = Stable(config.FAST_HOLD_S, min_obs=config.FAST_MIN_OBS)
        self.state = State.WAIT_HAND
        self.discarded = 0
        self.mismatches = 0
        self.last_discard_reason = ""
        self._clear_hand()

    # -- helpers -----------------------------------------------------------
    def _clear_hand(self):
        self.dealer_up = None
        self.player_start = None
        self.player_end = None
        self.n_hit = 0
        self.hand_started_at = 0.0
        self.lost_since = None
        self.icon_stale = True
        self.final_icon = None      # last real action icon seen this hand
        self.saw_hit_icon = False   # icon proves >= 1 hit even if the total never changed
        self.pending = None         # (result colour, time) once the border left blue
    def _discard(self, reason):
        self.discarded += 1
        self.last_discard_reason = reason
        self._clear_hand()
        self.state = State.WAIT_CLEAR

    # -- main entry --------------------------------------------------------
    def step(self, obs: Observation) -> Optional[HandRecord]:
        raw_p = 21 if obs.player == "BJ" else obs.player
        raw_d = 21 if obs.dealer == "BJ" else obs.dealer
        p, p_changed = self.p.update(raw_p, obs.t)
        d, _ = self.d.update(raw_d, obs.t)
        c, _ = self.c.update(obs.color, obs.t)
        a, a_changed = self.a.update(obs.action, obs.t)

        if self.state == State.WAIT_CLEAR:
            # Between hands the colour is red/green/yellow. A fresh blue badge (or the
            # badges vanishing) means the next hand is being dealt.
            if c == BLUE or p is None or d is None or raw_p is None or raw_d is None:
                self.state = State.WAIT_HAND
            return None

        if self.state == State.WAIT_HAND:
            self._wait_hand(p, d, c, a, obs)
            return None

        # PLAYER_TURN safety nets
        if obs.t - self.hand_started_at > self.max_hand_s:
            self._discard("hand timed out")
            return None
        # Badge OCR can fail on some result colours (e.g. dark red), so a latched result
        # border is enough to end the hand; only treat unreadable badges as "lost" while
        # there is no result border to go on.
        no_result_border = c in (None, BLUE)
        if self.pending is None and no_result_border and (
                raw_p is None or raw_d is None):
            if self.lost_since is None:
                self.lost_since = obs.t
            elif obs.t - self.lost_since > self.lost_s:
                self._discard("badges lost mid-hand")
            return None
        self.lost_since = None
        return self._player_turn(p, p_changed, d, c, a, a_changed, obs)

    # -- states ------------------------------------------------------------
    def _wait_hand(self, p, d, c, a, obs):
        if p is None or d is None or self.p.raw != p or self.d.raw != d:
            return
        # A fresh hand has a blue border (or None with no leftover action icon).
        # A natural blackjack ('BJ') can resolve immediately to a green/yellow border
        # without ever pausing on blue, so allow starting directly from 'BJ' as well.
        is_bj_deal = obs.player == "BJ" and c in ("green", "yellow") and a is None
        fresh = c == BLUE or (c is None and a is None and self.a.raw is None) or is_bj_deal
        if not fresh:
            return
        if not (4 <= p <= 21 and 2 <= d <= 11):
            return          # implausible reading (mid-deal), keep waiting
        self.dealer_up = d
        self.player_start = self.player_end = p
        self.n_hit = 0
        self.hand_started_at = obs.t
        # An icon already showing at the deal is left over from the previous hand
        # until it changes; ignore it until then.
        self.icon_stale = a is not None
        self.state = State.PLAYER_TURN

    def _player_turn(self, p, p_changed, d, c, a, a_changed, obs):
        result_visible = obs.color not in (None, BLUE)
        # After the result has latched, only keep updating the total while the result
        # border is still on screen; otherwise it may be the next hand's deal.
        if (p_changed and p is not None and p != self.player_end
                and (self.pending is None or result_visible)):
            self.player_end = p
            self.n_hit += 1
        if a_changed:
            self.icon_stale = False
            if a is not None:
                self.final_icon = a
                if a == "hit":
                    self.saw_hit_icon = True

        # Latch the result the moment the border leaves blue. Remember it even if the
        # border returns to blue before we finish: fast play must not lose the hand.
        if self.pending is None:
            if c in (None, BLUE):
                return None
            self.pending = (c, obs.t)
        colour, latched_at = self.pending

        # Give the final total a moment to settle before recording. If it is still
        # changing, wait a little longer, but never past a hard cap: by then any
        # change is the next hand's deal, not this hand's final card.
        waited = obs.t - latched_at
        if waited < self.stable_s + 0.1:
            return None
        if self.p.raw != self.p.value and waited < self.stable_s + 0.6:
            return None

        # The icon is a floor, not a counter: it catches a hit that left the total
        # unchanged (soft 17 + 10) without double counting a hit the total also showed.
        if self.saw_hit_icon and self.n_hit == 0:
            self.n_hit = 1

        natural = self.player_start == 21 and self.n_hit == 0
        elapsed = latched_at - self.hand_started_at
        icon = self.final_icon

        # Dealer blackjack: the hand ends before the player gets to act, so no hit/stand
        # icon ever appeared. With a 10-value upcard the peek is near-instant; with an
        # ace upcard it follows the insurance prompt (always treated as declined), so
        # it can take as long as the player does to answer, and elapsed time is useless.
        if (colour == "red" and self.n_hit == 0 and d == 21 and icon is None
                and (elapsed < self.natural_s or self.dealer_up == 11)):
            self._discard("dealer natural, no decision")
            return None

        outcome = outcome_from_color(colour, self.player_end, natural)
        expected = outcome_from_totals(self.player_end, d, natural) if d is not None else outcome
        if expected != outcome:
            self.mismatches += 1

        # The game's own last-action icon is authoritative when it has been seen:
        #   hit  -> at least one hit (catches a hit that left the total unchanged)
        #   stand -> the player chose to stand; a hit icon means play ended by bust or
        #            an automatic stand on 21, so stood is False.
        if icon is not None:
            stood = icon == "stand"
        else:
            stood = outcome != "bust" and not natural   # fallback inference

        record = HandRecord(dealer_label(self.dealer_up), self.player_start,
                            self.player_end, self.n_hit, stood=stood, outcome=outcome)
        self._clear_hand()
        self.state = State.WAIT_CLEAR
        return record

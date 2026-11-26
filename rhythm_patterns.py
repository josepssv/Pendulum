"""
Variable-Length Rhythmic Step Pattern Engine (1..8 steps per direction).
Provides real time-slot grids where active hits ('x') fire at their exact
temporal slot across a pendulum's half-period, ties ('~') sustain the previous
hit across subsequent slots, and rests ('-') remain silent.
"""

import random
from typing import List, Tuple

MIN_PATTERN_STEPS = 1
MAX_PATTERN_STEPS = 8
DEFAULT_PATTERN_STEPS = 6

STEP_REST = 0
STEP_HIT = 1
STEP_TIE = 2


def _coerce_step(val) -> int:
    """Normalizes legacy bools, ints, or ASCII symbols into STEP_REST/STEP_HIT/STEP_TIE."""
    if isinstance(val, str):
        s = val.strip()
        if s in ("x", "X", "1", "●"):
            return STEP_HIT
        if s in ("~", "="):
            return STEP_TIE
        return STEP_REST
    if isinstance(val, bool):
        return STEP_HIT if val else STEP_REST
    if isinstance(val, int):
        if val == STEP_TIE:
            return STEP_TIE
        if val == STEP_HIT:
            return STEP_HIT
        return STEP_REST
    return STEP_HIT if val else STEP_REST


def is_hit(step) -> bool:
    """Returns True if step triggers a new note hit."""
    return step == STEP_HIT


def is_tie(step) -> bool:
    """Returns True if step sustains the previous hit."""
    return step == STEP_TIE


def is_rest(step) -> bool:
    """Returns True if step is a silent rest."""
    return step == STEP_REST


def count_hits(steps) -> int:
    """Counts active note hits (STEP_HIT) without counting ties or rests."""
    if isinstance(steps, int):
        return max(0, steps)
    return sum(1 for s in steps if s == STEP_HIT)


def has_ties(steps) -> bool:
    """Returns True if the sequence contains at least one tie step (STEP_TIE)."""
    if isinstance(steps, int):
        return False
    return any(s == STEP_TIE for s in steps)


def normalize_pattern(conf, default_len: int = DEFAULT_PATTERN_STEPS) -> List[int]:
    """
    Normalizes an int hit count, step sequence, or 'x'/'~'/'-' pattern string
    into a validated list of step states (STEP_REST, STEP_HIT, STEP_TIE) of length 1..MAX_PATTERN_STEPS.
    """
    def_len = max(MIN_PATTERN_STEPS, min(MAX_PATTERN_STEPS, int(default_len)))

    if isinstance(conf, str):
        parsed: List[int] = []
        for ch in conf:
            if ch in (" ", "\t", "|", "/"):
                continue
            if ch in ("x", "X", "1", "●"):
                parsed.append(STEP_HIT)
            elif ch in ("~", "="):
                parsed.append(STEP_TIE)
            elif ch in ("-", ".", "0", "_", "○"):
                parsed.append(STEP_REST)
        if not parsed:
            return [STEP_HIT] + [STEP_REST] * (def_len - 1)
        return parsed[:MAX_PATTERN_STEPS]

    if isinstance(conf, (list, tuple)):
        if len(conf) == 0:
            return [STEP_REST] * def_len
        return [_coerce_step(x) for x in conf[:MAX_PATTERN_STEPS]]

    if isinstance(conf, int):
        c = max(0, min(MAX_PATTERN_STEPS, conf))
        n_len = max(def_len, c)
        return [STEP_HIT] * c + [STEP_REST] * (n_len - c)

    return [STEP_HIT] + [STEP_REST] * (def_len - 1)


def resize_pattern(steps: List[int], new_len: int) -> List[int]:
    """Resizes a step pattern to new_len (1..MAX_PATTERN_STEPS), padding with rests ('-')."""
    target_len = max(MIN_PATTERN_STEPS, min(MAX_PATTERN_STEPS, int(new_len)))
    cur = [_coerce_step(x) for x in steps]
    if len(cur) >= target_len:
        return cur[:target_len]
    return cur + [STEP_REST] * (target_len - len(cur))


def toggle_pattern_step(steps: List[int], step_idx: int) -> List[int]:
    """
    Binary toggles step_idx between hit and rest if inside current length,
    or extends the pattern to step_idx + 1 with intermediate rests and turns step_idx on.
    """
    idx = int(step_idx)
    cur = [_coerce_step(x) for x in steps]
    if idx < 0 or idx >= MAX_PATTERN_STEPS:
        return cur
    if idx < len(cur):
        cur[idx] = STEP_REST if cur[idx] == STEP_HIT else STEP_HIT
        return cur
    while len(cur) < idx:
        cur.append(STEP_REST)
    cur.append(STEP_HIT)
    return cur


def cycle_pattern_step(steps: List[int], step_idx: int) -> List[int]:
    """
    Cycles step_idx through Rest ('-') -> Hit ('x') -> Tie ('~') -> Rest ('-').
    If step_idx is past current length within MAX_PATTERN_STEPS, extends with rests and sets Hit.
    """
    idx = int(step_idx)
    cur = [_coerce_step(x) for x in steps]
    if idx < 0 or idx >= MAX_PATTERN_STEPS:
        return cur
    if idx < len(cur):
        state = cur[idx]
        if state == STEP_REST:
            cur[idx] = STEP_HIT
        elif state == STEP_HIT:
            cur[idx] = STEP_TIE
        else:
            cur[idx] = STEP_REST
        return cur
    while len(cur) < idx:
        cur.append(STEP_REST)
    cur.append(STEP_HIT)
    return cur


def toggle_pattern_tie(steps: List[int], step_idx: int) -> List[int]:
    """
    Toggles step_idx directly between Tie ('~') and Rest ('-').
    If step_idx is past current length within MAX_PATTERN_STEPS, extends with rests and sets Tie.
    """
    idx = int(step_idx)
    cur = [_coerce_step(x) for x in steps]
    if idx < 0 or idx >= MAX_PATTERN_STEPS:
        return cur
    if idx < len(cur):
        cur[idx] = STEP_REST if cur[idx] == STEP_TIE else STEP_TIE
        return cur
    while len(cur) < idx:
        cur.append(STEP_REST)
    cur.append(STEP_TIE)
    return cur


def set_pattern_step(steps: List[int], step_idx: int, value) -> List[int]:
    """
    Sets step_idx to coerced state ('x' if STEP_HIT, '~' if STEP_TIE, '-' if STEP_REST).
    If state is not STEP_REST and step_idx is past current length (within MAX_PATTERN_STEPS),
    extends the pattern to step_idx + 1 with intermediate rests and sets the target state.
    If state is STEP_REST and step_idx is past current length, returns the pattern unchanged.
    """
    idx = int(step_idx)
    cur = [_coerce_step(x) for x in steps]
    if idx < 0 or idx >= MAX_PATTERN_STEPS:
        return cur
    target_state = _coerce_step(value)
    if idx < len(cur):
        cur[idx] = target_state
        return cur
    if target_state == STEP_REST:
        return cur
    while len(cur) < idx:
        cur.append(STEP_REST)
    cur.append(target_state)
    return cur


def rotate_pattern(steps: List[int], shift: int) -> List[int]:
    """Circularly rotates steps while preserving length and ties (shift < 0 left, shift > 0 right)."""
    cur = [_coerce_step(x) for x in steps]
    n = len(cur)
    if n <= 1:
        return cur
    k = (-int(shift)) % n
    return cur[k:] + cur[:k]


def invert_pattern(steps: List[int]) -> List[int]:
    """Flips hits ('x') to rests ('-') and non-hits to hits while preserving pattern length."""
    return [STEP_REST if _coerce_step(x) == STEP_HIT else STEP_HIT for x in steps]


def reverse_pattern(steps: List[int]) -> List[int]:
    """Mirrors the step pattern backwards while preserving length and ties."""
    return [_coerce_step(x) for x in reversed(steps)]


def euclidean_pattern(hits: int, steps: int = DEFAULT_PATTERN_STEPS) -> List[int]:
    """Generates a Bjorklund Euclidean rhythm of length 1..MAX_PATTERN_STEPS."""
    n_steps = max(MIN_PATTERN_STEPS, min(MAX_PATTERN_STEPS, int(steps)))
    k = max(0, min(n_steps, int(hits)))
    if k <= 0:
        return [STEP_REST] * n_steps
    if k >= n_steps:
        return [STEP_HIT] * n_steps

    pattern = [[STEP_HIT] for _ in range(k)]
    remainder = [[STEP_REST] for _ in range(n_steps - k)]
    while len(remainder) > 1:
        new_pattern = [p + r for p, r in zip(pattern, remainder)]
        if len(pattern) < len(remainder):
            remainder = remainder[len(pattern):]
        else:
            remainder = pattern[len(remainder):]
        pattern = new_pattern

    result: List[int] = []
    for seq in pattern:
        result.extend(seq)
    for seq in remainder:
        result.extend(seq)
    return result[:n_steps]


def format_pattern(steps: List[int]) -> str:
    """Formats a step sequence into ASCII 'x'/'~'/'-' notation (e.g. 'xx~x---')."""
    chars = []
    for s in steps:
        st = _coerce_step(s)
        if st == STEP_HIT:
            chars.append("x")
        elif st == STEP_TIE:
            chars.append("~")
        else:
            chars.append("-")
    return "".join(chars)


def compute_pattern_slot_delays(
    n_steps: int,
    half_period: float,
    ratio: float = 1.0,
    speed_factor: float = 1.0,
) -> List[float]:
    """
    Computes exact temporal slot offsets (seconds) for an N-step rhythmic grid across
    one half_period crossing. When ratio == 1.0 and speed_factor == 1.0, slots sit at
    [0, hp/N, 2*hp/N, ..., (N-1)*hp/N]. Rest slots ('-') preserve their empty time gap.
    """
    n = max(1, int(n_steps))
    if n <= 1:
        return [0.0]

    hp = max(0.05, float(half_period))
    sf = max(0.15, float(speed_factor))
    grid_span = (hp * sf) if sf <= 1.0 else min(hp * 0.98, hp * sf)

    safe_ratio = max(0.05, float(ratio))
    weights = [safe_ratio ** j for j in range(n)]
    sum_w = sum(weights)
    if sum_w <= 0.0001:
        weights = [1.0] * n
        sum_w = float(n)

    scale = grid_span / sum_w
    max_delay = max(0.0, hp - 0.008)
    offsets: List[float] = []
    acc = 0.0
    for j in range(n):
        offsets.append(min(max(0.0, acc * scale), max_delay))
        acc += weights[j]
    return offsets


def compute_step_tie_span(
    cur_steps: List[int],
    next_steps: List[int],
    step_idx: int,
    half_period: float,
    cur_delays: List[float],
    next_delays: List[float],
) -> Tuple[int, float, float]:
    """
    Walks forward from step_idx across cur_steps and into next_steps (crossing boundaries)
    while consecutive slots are STEP_TIE ('~').
    Returns (tie_count, slot_span_sec, tied_span_sec).
    """
    hp = max(0.05, float(half_period))
    if not cur_steps or step_idx < 0 or step_idx >= len(cur_steps):
        return (0, hp, hp)

    cur_s = cur_steps
    cur_d = cur_delays if len(cur_delays) == len(cur_s) else compute_pattern_slot_delays(len(cur_s), hp)
    if not next_steps:
        next_s = cur_s
        next_d = cur_d
    else:
        next_s = next_steps
        next_d = next_delays if len(next_delays) == len(next_s) else compute_pattern_slot_delays(len(next_s), hp)

    def _steps_for(c: int) -> List[int]:
        return cur_s if (c % 2 == 0) else next_s

    def _delays_for(c: int) -> List[float]:
        return cur_d if (c % 2 == 0) else next_d

    def _pos_time(c: int, j: int) -> float:
        return c * hp + float(_delays_for(c)[j])

    def _pos_state(c: int, j: int) -> int:
        return _coerce_step(_steps_for(c)[j])

    def _advance(c: int, j: int) -> Tuple[int, int]:
        j += 1
        if j >= len(_steps_for(c)):
            c += 1
            j = 0
        return c, j

    t_start = _pos_time(0, step_idx)
    c, j = _advance(0, step_idx)
    slot_span_sec = max(0.02, _pos_time(c, j) - t_start)

    tie_count = 0
    max_walk = 2 * (len(cur_s) + len(next_s))
    while tie_count < max_walk and _pos_state(c, j) == STEP_TIE:
        tie_count += 1
        c, j = _advance(c, j)

    tied_span_sec = max(slot_span_sec, _pos_time(c, j) - t_start)
    return (tie_count, slot_span_sec, tied_span_sec)


def generate_random_pattern_side(length: int, style: str = "random") -> List[int]:
    """Generates a pattern side of exact length (1..MAX_PATTERN_STEPS) for a given style."""
    n_len = max(MIN_PATTERN_STEPS, min(MAX_PATTERN_STEPS, int(length)))
    st = (style or "random").lower()

    if st == "euclidean":
        if n_len == 1:
            return [STEP_HIT]
        low_k = 2 if n_len >= 4 else 1
        high_k = max(low_k, n_len - 1)
        hits = random.randint(low_k, high_k)
        pat = euclidean_pattern(hits, n_len)
        return rotate_pattern(pat, random.randint(0, n_len - 1))

    if st == "syncopated":
        if n_len == 1:
            return [STEP_HIT]
        pat = [STEP_REST] * n_len
        n_hits = random.randint(max(1, n_len // 3), max(1, (2 * n_len) // 3))
        candidates = list(range(1, n_len))
        chosen = random.sample(candidates, min(n_hits, len(candidates)))
        for idx in chosen:
            pat[idx] = STEP_HIT
        if not any(is_hit(x) for x in pat):
            pat[min(1, n_len - 1)] = STEP_HIT
        return pat

    if st == "flamenco":
        if n_len == 1:
            return [STEP_HIT]
        pat = [STEP_HIT if (random.random() < 0.70) else STEP_REST for _ in range(n_len)]
        pat[0] = STEP_HIT
        if n_len >= 3 and count_hits(pat) < 2:
            pat[1] = STEP_HIT
        return pat

    if st == "chaos":
        pat = [STEP_HIT if (random.random() < 0.45) else STEP_REST for _ in range(n_len)]
        if not any(is_hit(x) for x in pat):
            pat[random.randrange(n_len)] = STEP_HIT
        return pat

    # 'random' / 'ida' / 'vuelta'
    min_h = 1
    max_h = max(1, n_len - (1 if n_len >= 3 else 0))
    n_hits = random.randint(min_h, max_h)
    chosen = set(random.sample(range(n_len), n_hits))
    return [STEP_HIT if (i in chosen) else STEP_REST for i in range(n_len)]

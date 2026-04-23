from buddy import (
    Species, BUDDY_X_CENTER, BUDDY_Y_OVERLAY, BUDDY_Y_BASE,
    BUDDY_DIM, BUDDY_WHITE, BUDDY_HEART, BUDDY_YEL, BUDDY_CYAN, BUDDY_GREEN,
    COLOR_CAPYBARA,
)

BODY = COLOR_CAPYBARA


def do_sleep(r, t):
    FLAT    = ["            ", "            ", "    .--.    ", "  _( -- )_  ", " (___zz___) "]
    BREATHE = ["            ", "    .--.    ", "  _( -- )_  ", " (___..___) ", "  ~~~~~~~~  "]
    SNORE   = ["            ", "    .--.    ", "  _( __ )_  ", " (___oO___) ", "  ~~~~~~~~  "]
    SIDE    = ["            ", "            ", "  .---___   ", " (--   --)= ", "  `~~~~~~`  "]
    SIDE_Z  = ["            ", "            ", "  .---___   ", " (-- ZZZ-)= ", "  `~~~~~~`  "]
    YAWN    = ["            ", "    .--.    ", "  _( ^^ )_  ", " (___O____) ", "  ~~~~~~~~  "]

    P = [FLAT, BREATHE, SNORE, SIDE, SIDE_Z, YAWN]
    SEQ = [0,1,0,1,0,1,2,1, 0,1,0,1, 3,4,3,4,3,4, 3,3, 1,5,1,1]
    beat = (t // 5) % len(SEQ)
    r.print_sprite(P[SEQ[beat]], 5, 0, BODY)

    p1 = t % 10
    p2 = (t + 4) % 10
    p3 = (t + 7) % 10
    r.print_at(BUDDY_X_CENTER + 20 + p1, BUDDY_Y_OVERLAY + 18 - p1 * 2, "z", BUDDY_DIM)
    r.print_at(BUDDY_X_CENTER + 26 + p2, BUDDY_Y_OVERLAY + 14 - p2, "Z", BUDDY_WHITE)
    r.print_at(BUDDY_X_CENTER + 16 + p3 // 2, BUDDY_Y_OVERLAY + 10 - p3 // 2, "z", BUDDY_DIM)


def do_idle(r, t):
    REST    = ["            ", "  n______n  ", " ( o    o ) ", " (   oo   ) ", "  `------'  "]
    LOOK_L  = ["            ", "  n______n  ", " (o     o ) ", " (   oo   ) ", "  `------'  "]
    LOOK_R  = ["            ", "  n______n  ", " ( o     o) ", " (   oo   ) ", "  `------'  "]
    LOOK_U  = ["            ", "  n______n  ", " ( ^    ^ ) ", " (   oo   ) ", "  `------'  "]
    BLINK   = ["            ", "  n______n  ", " ( -    - ) ", " (   oo   ) ", "  `------'  "]
    EAR_TW  = ["            ", "  ^______n  ", " ( o    o ) ", " (   oo   ) ", "  `------'  "]
    CHEW_A  = ["            ", "  n______n  ", " ( o    o ) ", " (   ww   ) ", "  `------'  "]
    CHEW_B  = ["            ", "  n______n  ", " ( o    o ) ", " (   WW   ) ", "  `------'  "]
    YAWN    = ["            ", "  n______n  ", " ( -    - ) ", " (   OO   ) ", "  `------'  "]
    STRETCH = ["            ", " /n______n\\", "/( o    o )\\", " (   oo   ) ", "  `------'  "]

    P = [REST, LOOK_L, LOOK_R, LOOK_U, BLINK, EAR_TW, CHEW_A, CHEW_B, YAWN, STRETCH]
    SEQ = [0,0,0,1,0,2,0,4, 0,5,0,0, 6,7,6,7, 0,0,3,3,0,4, 8,8,0,0, 9,9,0,0]
    beat = (t // 5) % len(SEQ)
    r.print_sprite(P[SEQ[beat]], 5, 0, BODY)


def do_busy(r, t):
    TYPE_A = ["            ", "  n______n  ", " ( v    v ) ", " (   --   ) ", " /`------'\\ "]
    TYPE_B = ["            ", "  n______n  ", " ( v    v ) ", " (   __   ) ", " \\`------'/ "]
    THINK  = ["      ?     ", "  n______n  ", " ( ^    ^ ) ", " (   ..   ) ", "  `------'  "]
    SIP    = ["    [_]     ", "  n_____|n  ", " ( o    o|) ", " (   --   ) ", "  `------'  "]
    EUREKA = ["      *     ", "  n______n  ", " ( O    O ) ", " (   ^^   ) ", " /`------'\\ "]
    RELIEF = ["    ~~~     ", "  n______n  ", " ( -    - ) ", " (   __   ) ", "  `------'  "]

    P = [TYPE_A, TYPE_B, THINK, SIP, EUREKA, RELIEF]
    SEQ = [0,1,0,1,0,1, 2,2, 0,1,0,1, 3,3, 2,4, 0,1,0,1,5]
    beat = (t // 5) % len(SEQ)
    r.print_sprite(P[SEQ[beat]], 5, 0, BODY)

    DOTS = [".  ", ".. ", "...", " ..", "  .", "   "]
    r.print_at(BUDDY_X_CENTER + 22, BUDDY_Y_OVERLAY + 14, DOTS[t % 6], BUDDY_WHITE)


def do_attention(r, t):
    ALERT  = ["    ^  ^    ", " /^_____^\\  ", "( O      O )", " (   O    ) ", "  `------'  "]
    SCAN_L = ["    ^  ^    ", " /^_____^\\  ", "(O       O )", " (   O    ) ", "  `------'  "]
    SCAN_R = ["    ^  ^    ", " /^_____^\\  ", "( O       O)", " (   O    ) ", "  `------'  "]
    SCAN_U = ["    ^  ^    ", " /^_____^\\  ", "( ^      ^ )", " (   O    ) ", "  `------'  "]
    TENSE  = ["    ^  ^    ", "/^^_____^^\\ ", "( O      O )", " (   O    ) ", " /`------'\\ "]
    HUSH   = ["    ^  ^    ", " /^_____^\\  ", "( o      o )", " (   .    ) ", "  `------'  "]

    P = [ALERT, SCAN_L, SCAN_R, SCAN_U, TENSE, HUSH]
    SEQ = [0,4,0,1,0,2,0,3, 4,4,0,1,2,0, 5,0]
    beat = (t // 5) % len(SEQ)
    pose = SEQ[beat]
    x_off = (1 if t & 1 else -1) if pose == 4 else 0
    r.print_sprite(P[pose], 5, 0, BODY, x_off)

    if (t // 2) & 1:
        r.print_at(BUDDY_X_CENTER - 4, BUDDY_Y_OVERLAY, "!", BUDDY_YEL)
    if (t // 3) & 1:
        r.print_at(BUDDY_X_CENTER + 4, BUDDY_Y_OVERLAY + 4, "!", BUDDY_YEL)


def do_celebrate(r, t):
    CROUCH = ["            ", "  n______n  ", " ( ^    ^ ) ", " (   ww   ) ", " /`------'\\ "]
    JUMP   = ["  \\(    )/  ", "   n____n   ", " ( ^    ^ ) ", " (   ww   ) ", "  `------'  "]
    PEAK   = ["  \\^    ^/  ", "   n____n   ", " ( ^    ^ ) ", " (   WW   ) ", "  `------'  "]
    SPIN_L = ["            ", "  n______n  ", "( <    < ) /", " (   ww   ) ", "  `------'  "]
    SPIN_R = ["            ", "  n______n  ", "\\( >    > )", " (   ww   ) ", "  `------'  "]
    POSE   = ["    \\__/    ", "  n______n  ", " ( ^    ^ ) ", "/(   WW   )\\", "  `------'  "]

    P = [CROUCH, JUMP, PEAK, SPIN_L, SPIN_R, POSE]
    SEQ = [0,1,2,1,0, 3,4,3,4, 0,1,2,1,0, 5,5]
    Y_SHIFT = [0,-3,-6,-3,0, 0,0,0,0, 0,-3,-6,-3,0, 0,0]
    beat = (t // 3) % len(SEQ)
    r.print_sprite(P[SEQ[beat]], 5, Y_SHIFT[beat], BODY)

    cols = [BUDDY_YEL, BUDDY_HEART, BUDDY_CYAN, BUDDY_WHITE, BUDDY_GREEN]
    for i in range(6):
        phase = (t * 2 + i * 11) % 22
        x = BUDDY_X_CENTER - 36 + i * 14
        y = BUDDY_Y_OVERLAY - 6 + phase
        if y > BUDDY_Y_BASE + 20 or y < 0:
            continue
        ch = "*" if (i + t // 2) & 1 else "."
        r.print_at(x, y, ch, cols[i % 5])


def do_dizzy(r, t):
    TILT_L  = ["            ", " n______n   ", "( @    @ )  ", " (   ~~   ) ", "  `------'  "]
    TILT_R  = ["            ", "   n______n ", "  ( @    @ )", " (   ~~   ) ", "  `------'  "]
    WOOZY   = ["            ", "  n______n  ", " ( x    @ ) ", " (   ~v   ) ", "  `------'  "]
    WOOZY2  = ["            ", "  n______n  ", " ( @    x ) ", " (   v~   ) ", "  `------'  "]
    STUMBLE = ["            ", "  n______n  ", " ( @    @ ) ", " (   --   ) ", " /`-_---_'\\ "]

    P = [TILT_L, TILT_R, WOOZY, WOOZY2, STUMBLE]
    SEQ = [0,1,0,1, 2,3, 0,1,0,1, 4,4, 2,3]
    X_SHIFT = [-3,3,-3,3, 0,0, -3,3,-3,3, 0,0, 0,0]
    beat = (t // 4) % len(SEQ)
    r.print_sprite(P[SEQ[beat]], 5, 0, BODY, X_SHIFT[beat])

    OX = [0, 5, 7, 5, 0, -5, -7, -5]
    OY = [-5, -3, 0, 3, 5, 3, 0, -3]
    p1 = t % 8
    p2 = (t + 4) % 8
    r.print_at(BUDDY_X_CENTER + OX[p1] - 2, BUDDY_Y_OVERLAY + 6 + OY[p1], "*", BUDDY_CYAN)
    r.print_at(BUDDY_X_CENTER + OX[p2] - 2, BUDDY_Y_OVERLAY + 6 + OY[p2], "*", BUDDY_YEL)


def do_heart(r, t):
    DREAMY = ["            ", "  n______n  ", " ( ^    ^ ) ", " (   ww   ) ", "  `------'  "]
    BLUSH  = ["            ", "  n______n  ", " (#^    ^#) ", " (   ww   ) ", "  `------'  "]
    EYES_C = ["            ", "  n______n  ", " ( <3  <3 ) ", " (   ww   ) ", "  `------'  "]
    TWIRL  = ["            ", "  n______n  ", " ( @    @ ) ", " (   ww   ) ", " /`------'\\ "]
    SIGH   = ["            ", "  n______n  ", " ( -    - ) ", " (   ^^   ) ", "  `------'  "]

    P = [DREAMY, BLUSH, EYES_C, TWIRL, SIGH]
    SEQ = [0,0,1,0, 2,2,0, 1,0,4, 0,0,3,3, 0,1,0,2, 1,0]
    Y_BOB = [0,-1,0,-1, 0,-1,0, -1,0,0, -1,0,0,0, -1,0,-1,0, -1,0]
    beat = (t // 5) % len(SEQ)
    r.print_sprite(P[SEQ[beat]], 5, Y_BOB[beat], BODY)

    for i in range(5):
        phase = (t + i * 4) % 16
        y = BUDDY_Y_OVERLAY + 16 - phase
        if y < -2 or y > BUDDY_Y_BASE:
            continue
        x = BUDDY_X_CENTER - 20 + i * 8 + ((phase // 3) & 1) * 2 - 1
        r.print_at(x, y, "v", BUDDY_HEART)


SPECIES = Species(
    name="capybara",
    body_color=BODY,
    states=[do_sleep, do_idle, do_busy, do_attention, do_celebrate, do_dizzy, do_heart],
)

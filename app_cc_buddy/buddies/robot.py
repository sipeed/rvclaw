from buddy import (
    Species, BUDDY_X_CENTER, BUDDY_Y_OVERLAY, BUDDY_Y_BASE,
    BUDDY_DIM, BUDDY_WHITE, BUDDY_HEART, BUDDY_YEL, BUDDY_CYAN, BUDDY_GREEN,
    BUDDY_RED, BUDDY_PURPLE,
    COLOR_ROBOT,
)

BODY = COLOR_ROBOT


def do_sleep(r, t):
    PWR_DN = ["            ", "   .[__].   ", "  [ -    - ]", "  [ ____ ]  ", "  `------'  "]
    DIM_A  = ["            ", "   .[..].   ", "  [ .    . ]", "  [ ____ ]  ", "  `------'  "]
    DIM_B  = ["            ", "   .[  ].   ", "  [        ]", "  [ ____ ]  ", "  `------'  "]
    PING   = ["            ", "   .[||].   ", "  [ -    - ]", "  [ z__z ]  ", "  `------'  "]
    DREAM  = ["    .[*].   ", "   .[||].   ", "  [ -    - ]", "  [ zzzz ]  ", "  `------'  "]
    REBOOT = ["            ", "   .[..].   ", "  [ o    - ]", "  [ ____ ]  ", "  `------'  "]

    P = [PWR_DN, DIM_A, DIM_B, PING, DREAM, REBOOT]
    SEQ = [0,1,2,1,0,1,2,1, 0,0,3,3, 4,4,4,3, 0,1,2,1,0, 5,0,1,0]
    beat = (t // 5) % len(SEQ)
    r.print_sprite(P[SEQ[beat]], 5, 0, BODY)

    p1 = t % 10
    p2 = (t + 4) % 10
    p3 = (t + 7) % 10
    r.print_at(BUDDY_X_CENTER + 20 + p1, BUDDY_Y_OVERLAY + 18 - p1 * 2, "z", BUDDY_DIM)
    r.print_at(BUDDY_X_CENTER + 26 + p2, BUDDY_Y_OVERLAY + 14 - p2, "Z", BUDDY_CYAN)
    r.print_at(BUDDY_X_CENTER + 16 + p3 // 2, BUDDY_Y_OVERLAY + 10 - p3 // 2, "z", BUDDY_DIM)


def do_idle(r, t):
    REST   = ["            ", "   .[||].   ", "  [ o    o ]", "  [ ==== ]  ", "  `------'  "]
    SCAN_L = ["            ", "   .[||].   ", "  [o     o ]", "  [ ==== ]  ", "  `------'  "]
    SCAN_R = ["            ", "   .[||].   ", "  [ o     o]", "  [ ==== ]  ", "  `------'  "]
    BLINK  = ["            ", "   .[||].   ", "  [ -    - ]", "  [ ==== ]  ", "  `------'  "]
    ANT_L  = ["            ", "   .[\\\\].   ", "  [ o    o ]", "  [ ==== ]  ", "  `------'  "]
    ANT_R  = ["            ", "   .[//].   ", "  [ o    o ]", "  [ ==== ]  ", "  `------'  "]
    BEEP_A = ["            ", "   .[||].   ", "  [ o    o ]", "  [ -==- ]  ", "  `------'  "]
    BEEP_B = ["            ", "   .[||].   ", "  [ o    o ]", "  [ =--= ]  ", "  `------'  "]
    PING   = ["    .[*].   ", "   .[||].   ", "  [ ^    ^ ]", "  [ ==== ]  ", "  `------'  "]
    CLICK  = ["            ", "   .[||].   ", "  [ o    o ]", "  [ ==== ]  ", " /`------'\\ "]

    P = [REST, SCAN_L, SCAN_R, BLINK, ANT_L, ANT_R, BEEP_A, BEEP_B, PING, CLICK]
    SEQ = [0,0,1,1,0,2,2,0, 3,0,0, 4,5,4,5,0, 6,7,6,7,0, 0,8,8,0, 9,9,0,3,0]
    beat = (t // 5) % len(SEQ)
    r.print_sprite(P[SEQ[beat]], 5, 0, BODY)

    if (t // 4) & 1:
        r.print_at(BUDDY_X_CENTER - 1, BUDDY_Y_BASE - 4, ".", BUDDY_RED)


def do_busy(r, t):
    CALC_A = ["    01010   ", "   .[||].   ", "  [ #    # ]", "  [ ==== ]  ", " /`------'\\ "]
    CALC_B = ["    10101   ", "   .[||].   ", "  [ #    # ]", "  [ -==- ]  ", " \\`------'/ "]
    PROC   = ["     ?      ", "   .[||].   ", "  [ ^    ^ ]", "  [ .... ]  ", "  `------'  "]
    WHIRR  = ["    [@@]    ", "   .[||].   ", "  [ o    o ]", "  [ ==== ]  ", "  `------'  "]
    DING   = ["     !      ", "   .[||].   ", "  [ O    O ]", "  [ ^^^^ ]  ", " /`------'\\ "]
    COOL   = ["    ~~~     ", "   .[||].   ", "  [ -    - ]", "  [ ____ ]  ", "  `------'  "]

    P = [CALC_A, CALC_B, PROC, WHIRR, DING, COOL]
    SEQ = [0,1,0,1,0,1, 2,2, 0,1,0,1, 3,3, 2,4, 0,1,0,1, 5]
    beat = (t // 5) % len(SEQ)
    r.print_sprite(P[SEQ[beat]], 5, 0, BODY)

    BITS = ["1  ", "10 ", "101", "010", "10 ", "1  "]
    r.print_at(BUDDY_X_CENTER + 22, BUDDY_Y_OVERLAY + 14, BITS[t % 6], BUDDY_GREEN)


def do_attention(r, t):
    ALERT  = ["    [!]     ", "   .[||].   ", "  [ O    O ]", "  [ #### ]  ", " /`------'\\ "]
    SCAN_L = ["    [!]     ", "   .[\\\\].   ", "  [O     O ]", "  [ #### ]  ", " /`------'\\ "]
    SCAN_R = ["    [!]     ", "   .[//].   ", "  [ O     O]", "  [ #### ]  ", " /`------'\\ "]
    SCAN_U = ["    [!]     ", "   .[||].   ", "  [ ^    ^ ]", "  [ #### ]  ", " /`------'\\ "]
    SIREN  = ["    {!!}    ", "   .[||].   ", "  [ X    X ]", "  [ #### ]  ", "//`------'\\\\"]
    HUSH   = ["    [.]     ", "   .[||].   ", "  [ o    o ]", "  [ .... ]  ", "  `------'  "]

    P = [ALERT, SCAN_L, SCAN_R, SCAN_U, SIREN, HUSH]
    SEQ = [0,4,0,1,0,2,0,3, 4,4,0,1,2,0, 5,0]
    beat = (t // 5) % len(SEQ)
    pose = SEQ[beat]
    x_off = (1 if t & 1 else -1) if pose == 4 else 0
    r.print_sprite(P[pose], 5, 0, BODY, x_off)

    if (t // 2) & 1:
        r.print_at(BUDDY_X_CENTER - 6, BUDDY_Y_OVERLAY, "!", BUDDY_YEL)
    if (t // 3) & 1:
        r.print_at(BUDDY_X_CENTER + 6, BUDDY_Y_OVERLAY + 4, "!", BUDDY_RED)
    if (t // 2) & 1:
        r.print_at(BUDDY_X_CENTER - 1, BUDDY_Y_BASE - 4, "*", BUDDY_RED)


def do_celebrate(r, t):
    CROUCH = ["            ", "   .[||].   ", "  [ ^    ^ ]", "  [ ==== ]  ", " /`------'\\ "]
    JUMP   = ["  \\[||]/    ", "   .----.   ", "  [ ^    ^ ]", "  [ ==== ]  ", "  `------'  "]
    PEAK   = ["  \\[**]/    ", "   .----.   ", "  [ O    O ]", "  [ ^^^^ ]  ", "  `------'  "]
    SPIN_L = ["            ", "   .[\\\\].   ", "  [ <    < ]", "  [ ==== ] /", "  `------'  "]
    SPIN_R = ["            ", "   .[//].   ", "  [ >    > ]", " \\[ ==== ]  ", "  `------'  "]
    POSE   = ["    [**]    ", "   .[||].   ", "  [ ^    ^ ]", " /[ #### ]\\ ", "  `------'  "]

    P = [CROUCH, JUMP, PEAK, SPIN_L, SPIN_R, POSE]
    SEQ = [0,1,2,1,0, 3,4,3,4, 0,1,2,1,0, 5,5]
    Y_SHIFT = [0,-3,-6,-3,0, 0,0,0,0, 0,-3,-6,-3,0, 0,0]
    beat = (t // 3) % len(SEQ)
    r.print_sprite(P[SEQ[beat]], 5, Y_SHIFT[beat], BODY)

    cols = [BUDDY_YEL, BUDDY_CYAN, BUDDY_GREEN, BUDDY_WHITE, BUDDY_PURPLE]
    for i in range(6):
        phase = (t * 2 + i * 11) % 22
        x = BUDDY_X_CENTER - 36 + i * 14
        y = BUDDY_Y_OVERLAY - 6 + phase
        if y > BUDDY_Y_BASE + 20 or y < 0:
            continue
        ch = "+" if (i + t // 2) & 1 else "*"
        r.print_at(x, y, ch, cols[i % 5])


def do_dizzy(r, t):
    TILT_L  = ["            ", "  .[||].    ", " [ x    x ] ", " [ ~~~~ ]   ", "  `------'  "]
    TILT_R  = ["            ", "    .[||].  ", "  [ x    x ]", "   [ ~~~~ ] ", "  `------'  "]
    GLITCH  = ["            ", "   .[/\\].   ", "  [ X    @ ]", "  [ #v#v ]  ", "  `--__--'  "]
    GLITCH2 = ["            ", "   .[\\/].   ", "  [ @    X ]", "  [ v#v# ]  ", "  `--__--'  "]
    CRASH   = ["            ", "   .[??].   ", "  [ x    x ]", "  [ ____ ]  ", " /`-_--_-'\\ "]

    P = [TILT_L, TILT_R, GLITCH, GLITCH2, CRASH]
    SEQ = [0,1,0,1, 2,3, 0,1,0,1, 4,4, 2,3]
    X_SHIFT = [-3,3,-3,3, 0,0, -3,3,-3,3, 0,0, 0,0]
    beat = (t // 4) % len(SEQ)
    r.print_sprite(P[SEQ[beat]], 5, 0, BODY, X_SHIFT[beat])

    OX = [0, 5, 7, 5, 0, -5, -7, -5]
    OY = [-5, -3, 0, 3, 5, 3, 0, -3]
    p1 = t % 8
    p2 = (t + 4) % 8
    r.print_at(BUDDY_X_CENTER + OX[p1] - 2, BUDDY_Y_OVERLAY + 6 + OY[p1], "?", BUDDY_YEL)
    r.print_at(BUDDY_X_CENTER + OX[p2] - 2, BUDDY_Y_OVERLAY + 6 + OY[p2], "x", BUDDY_RED)


def do_heart(r, t):
    DREAMY = ["    [<3]    ", "   .[||].   ", "  [ ^    ^ ]", "  [ ==== ]  ", "  `------'  "]
    BLUSH  = ["    [<3]    ", "   .[||].   ", "  [#^    ^#]", "  [ ==== ]  ", "  `------'  "]
    EYES_C = ["    [<3]    ", "   .[||].   ", "  [ <3  <3 ]", "  [ ==== ]  ", "  `------'  "]
    TWIRL  = ["    [<3]    ", "   .[||].   ", "  [ @    @ ]", "  [ ==== ]  ", " /`------'\\ "]
    SIGH   = ["    [<3]    ", "   .[||].   ", "  [ -    - ]", "  [ ^^^^ ]  ", "  `------'  "]

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
    name="robot",
    body_color=BODY,
    states=[do_sleep, do_idle, do_busy, do_attention, do_celebrate, do_dizzy, do_heart],
)

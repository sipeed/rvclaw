from buddy import (
    Species, BUDDY_X_CENTER, BUDDY_Y_OVERLAY, BUDDY_Y_BASE,
    BUDDY_DIM, BUDDY_WHITE, BUDDY_HEART, BUDDY_YEL, BUDDY_CYAN, BUDDY_GREEN,
    COLOR_CAPYBARA,
)

BODY = COLOR_CAPYBARA


def do_sleep(r, t):
    LOAF    = ["            ", "            ", "   .-..-.   ", "  ( -.- )   ", "  `------`~ "]
    BREATHE = ["            ", "            ", "   .-..-.   ", "  ( -.- )_  ", " `~------'~ "]
    CURL    = ["            ", "            ", "   .-/\\.    ", "  (  ..  )) ", "  `~~~~~~`  "]
    CURL_TW = ["            ", "            ", "   .-/\\.    ", "  (  ..  )) ", "  `~~~~~~`~ "]
    PURR    = ["            ", "            ", "   .-..-.   ", "  ( u.u )   ", " `~------'~ "]
    DREAM   = ["            ", "            ", "   .-..-.   ", "  ( o.o )   ", "  `------`  "]

    P = [LOAF, BREATHE, LOAF, PURR, CURL, CURL_TW]
    SEQ = [0,1,0,1,0,1, 3,3,0,1, 4,5,4,5,4,5, 2,2, 0,1,0,1, 5,5,4,4]
    beat = (t // 5) % len(SEQ)
    r.print_sprite(P[SEQ[beat]], 5, 0, BODY)

    p1 = t % 12
    p2 = (t + 5) % 12
    p3 = (t + 9) % 12
    r.print_at(BUDDY_X_CENTER + 18 + p1, BUDDY_Y_OVERLAY + 18 - p1 * 2, "z", BUDDY_DIM)
    r.print_at(BUDDY_X_CENTER + 24 + p2, BUDDY_Y_OVERLAY + 14 - p2, "Z", BUDDY_WHITE)
    r.print_at(BUDDY_X_CENTER + 14 + p3 // 2, BUDDY_Y_OVERLAY + 8 - p3 // 2, "z", BUDDY_DIM)


def do_idle(r, t):
    REST    = ["            ", "   /\\_/\\    ", "  ( o   o ) ", "  (  w   )  ", "  (\")_(\")   "]
    LOOK_L  = ["            ", "   /\\_/\\    ", "  (o    o ) ", "  (  w   )  ", "  (\")_(\")   "]
    LOOK_R  = ["            ", "   /\\_/\\    ", "  ( o    o) ", "  (  w   )  ", "  (\")_(\")   "]
    BLINK   = ["            ", "   /\\_/\\    ", "  ( -   - ) ", "  (  w   )  ", "  (\")_(\")   "]
    SLOW_BL = ["            ", "   /\\-/\\    ", "  ( _   _ ) ", "  (  w   )  ", "  (\")_(\")   "]
    EAR_L   = ["            ", "   <\\_/\\    ", "  ( o   o ) ", "  (  w   )  ", "  (\")_(\")   "]
    EAR_R   = ["            ", "   /\\_/>    ", "  ( o   o ) ", "  (  w   )  ", "  (\")_(\")   "]
    TAIL_L  = ["            ", "   /\\_/\\    ", "  ( o   o ) ", "  (  w   )  ", "  (\")_(\")~  "]
    TAIL_R  = ["            ", "   /\\_/\\    ", "  ( o   o ) ", "  (  w   )  ", " ~(\")_(\")   "]
    GROOM   = ["            ", "   /\\_/\\    ", "  ( ^   ^ ) ", "  (  P   )  ", "  (\")_(\")   "]

    P = [REST, LOOK_L, LOOK_R, BLINK, SLOW_BL, EAR_L, EAR_R, TAIL_L, TAIL_R, GROOM]
    SEQ = [0,0,0,3,0,1,0,2,0, 7,8,7,8,7, 0,5,0,6,0, 4,4,0, 9,9,9,0, 0,3,0, 8,7,8,7, 0,0,4,0]
    beat = (t // 5) % len(SEQ)
    r.print_sprite(P[SEQ[beat]], 5, 0, BODY)


def do_busy(r, t):
    PAW_UP  = ["      .     ", "   /\\_/\\    ", "  ( o   o ) ", "  (  w   )/ ", "  (\")_(\")   "]
    PAW_TAP = ["    .       ", "   /\\_/\\    ", "  ( o   o ) ", "  (  w   )_ ", "  (\")_(\")   "]
    STARE   = ["            ", "   /\\_/\\    ", "  ( O   O ) ", "  (  w   )  ", "  (\")_(\")   "]
    NUDGE   = ["    o       ", "   /\\_/\\    ", "  ( o   o ) ", "  ( -w   )  ", "  (\")_(\")   "]
    SHOVE   = ["  o         ", "   /\\_/\\    ", "  ( o   o ) ", "  (-w    )  ", "  (\")_(\")   "]
    SMUG    = ["            ", "   /\\_/\\    ", "  ( -   - ) ", "  (  w   )  ", "  (\")_(\")   "]

    P = [PAW_UP, PAW_TAP, STARE, NUDGE, SHOVE, SMUG]
    SEQ = [2,2,2, 0,1,0,1, 3,4,3,4, 5,5, 2,2, 0,1,0,1, 5,2]
    beat = (t // 5) % len(SEQ)
    r.print_sprite(P[SEQ[beat]], 5, 0, BODY)

    DOTS = [".  ", ".. ", "...", " ..", "  .", "   "]
    r.print_at(BUDDY_X_CENTER + 22, BUDDY_Y_OVERLAY + 14, DOTS[t % 6], BUDDY_WHITE)


def do_attention(r, t):
    ALERT  = ["            ", "   /^_^\\    ", "  ( O   O ) ", "  (  v   )  ", "  (\")_(\")   "]
    SCAN_L = ["            ", "   /^_^\\    ", "  (O    O ) ", "  (  v   )  ", "  (\")_(\")   "]
    SCAN_R = ["            ", "   /^_^\\    ", "  ( O    O) ", "  (  v   )  ", "  (\")_(\")   "]
    SCAN_U = ["            ", "   /^_^\\    ", "  ( ^   ^ ) ", "  (  v   )  ", "  (\")_(\")   "]
    CROUCH = ["            ", "   /^_^\\    ", " /( O   O )\\", " (   v    ) ", " /(\")_(\")\\  "]
    HISS   = ["            ", "   /^_^\\    ", "  ( O   O ) ", "  (  >   )  ", "  (\")_(\")   "]

    P = [ALERT, SCAN_L, SCAN_R, SCAN_U, CROUCH, HISS]
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
    CROUCH = ["            ", "   /\\_/\\    ", "  ( ^   ^ ) ", "  (  W   )  ", " /(\")_(\")\\  "]
    JUMP   = ["  \\^   ^/   ", "    /\\_/\\   ", "  ( ^   ^ ) ", "  (  W   )  ", "  (\")_(\")   "]
    PEAK   = ["  \\^   ^/   ", "    /\\_/\\   ", "  ( * * * ) ", "  (  W   )  ", "  (\")_(\")~  "]
    SPIN_L = ["            ", "   /\\_/\\    ", "  ( <   < ) ", "  (  W   ) /", " ~(\")_(\")   "]
    SPIN_R = ["            ", "   /\\_/\\    ", "  ( >   > ) ", " \\(  W   )  ", "  (\")_(\")~  "]
    POSE   = ["    \\o/     ", "   /\\_/\\    ", "  ( ^   ^ ) ", " /(  W   )\\ ", "  (\")_(\")   "]

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
    TILT_L = ["            ", "  /\\_/\\     ", " ( @   @ )  ", " (   ~~  )  ", " (\")_(\")    "]
    TILT_R = ["            ", "    /\\_/\\   ", "  ( @   @ ) ", "  (  ~~  )  ", "    (\")_(\") "]
    WOOZY  = ["            ", "   /\\_/\\    ", "  ( x   @ ) ", "  (  v   )  ", "  (\")_(\")~  "]
    WOOZY2 = ["            ", "   /\\_/\\    ", "  ( @   x ) ", "  (  v   )  ", " ~(\")_(\")   "]
    SPLAT  = ["            ", "   /\\_/\\    ", "  ( @   @ ) ", "  (  -   )  ", " /(\")_(\")\\~ "]

    P = [TILT_L, TILT_R, WOOZY, WOOZY2, SPLAT]
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
    DREAMY  = ["            ", "   /\\_/\\    ", "  ( ^   ^ ) ", "  (  u   )  ", "  (\")_(\")~  "]
    BLUSH   = ["            ", "   /\\_/\\    ", "  (#^   ^#) ", "  (  u   )  ", "  (\")_(\")   "]
    HEART_E = ["            ", "   /\\_/\\    ", "  ( <3 <3 ) ", "  (  u   )  ", "  (\")_(\")~  "]
    PURR    = ["            ", "   /\\-/\\    ", "  ( ~   ~ ) ", "  (  u   )  ", " ~(\")_(\")~  "]
    HEAD_T  = ["            ", "   /\\_/\\    ", "  ( ^   - ) ", "  (  u   )  ", "  (\")_(\")   "]

    P = [DREAMY, BLUSH, HEART_E, PURR, HEAD_T]
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
    name="cat",
    body_color=BODY,
    states=[do_sleep, do_idle, do_busy, do_attention, do_celebrate, do_dizzy, do_heart],
)

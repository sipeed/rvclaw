# CC Buddy — Claude Code Integration

Two connection paths from Claude to the Picoclaw CC Buddy device:

## Path A: Claude Desktop (BLE)

Built-in. Claude Desktop's Hardware Buddy bridge connects directly to the
device via Bluetooth LE. No extra software needed on the desktop.

1. Power on the Picoclaw (it advertises as `Claude-XXXX`)
2. In Claude Desktop: Developer → Open Hardware Buddy → Connect
3. Pick `Claude-XXXX` from the scan list

## Path B: Claude Code CLI (Hooks + Daemon)

For the `claude` terminal command. A small daemon on your desktop bridges
Claude Code hook events to the device over TCP.

### Architecture

```
Claude Code CLI (sessions)
    │ HTTP hooks (auto-injected)
    ▼
cc_buddy_daemon.py (:9876)
    │ TCP
    ▼
Picoclaw device (:19000)
```

### Setup

**1. Start the daemon on your desktop:**

```bash
python3 cc_buddy_daemon.py --device <PICOCLAW_IP>
```

The daemon automatically:
- Injects hook entries into `~/.claude/settings.json` (using the actual port)
- Connects to the Picoclaw's TCP port 19000
- Listens for Claude Code hooks on `http://127.0.0.1:9876`
- Removes hook entries from settings on shutdown (Ctrl+C or SIGTERM)

To use a different port:

```bash
python3 cc_buddy_daemon.py --device <PICOCLAW_IP> --port 9877
```

To skip automatic hook injection (manual management):

```bash
python3 cc_buddy_daemon.py --device <PICOCLAW_IP> --no-inject
```

**2. Use Claude Code normally:**

```bash
claude
```

The daemon receives hook events, assembles heartbeat JSON (same protocol
as the BLE Hardware Buddy), and pushes to the device. When Claude needs
permission, the device shows the approval prompt. Press A to approve,
B to deny — the decision flows back through the daemon to Claude Code.

### Hooks used

| Hook | Purpose |
|------|---------|
| SessionStart/End | Track active session count |
| PreToolUse | Track "running" state + build transcript |
| PostToolUse | Clear "running" state |
| Stop | Session finished generating |
| PermissionRequest | **Blocks** until device approve/deny (25s timeout) |
| PermissionDenied | Clear "waiting" state |
| PreCompact | Token count |

### Both paths simultaneously

The Picoclaw runs both BLE (for Claude Desktop) and TCP (for CLI hooks)
at the same time. Whichever path sends a heartbeat updates the same
TamaState — the device shows the combined state.

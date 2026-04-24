# tcp-udp-socket-programming

> HTTP/1.1 file server and real-time multiplayer game server — both built on raw TCP/UDP sockets in Python, no framework abstractions.

---

## What Was Built

| Component | What It Is |
|---|---|
| **HTTP File Server** | Single-threaded HTTP/1.1 server built on raw TCP sockets — handles GET, MIME routing, query parameters, 307 redirects, and 404 responses |
| **Multiplayer Guessing Game** | Real-time game server using a TCP/UDP hybrid: TCP for session control and scoring, UDP for low-latency guess submission |

---

## Architecture Overview

### HTTP File Server (TCP)

```
Client (Browser)
      │
      │  HTTP/1.1 GET
      ▼
┌─────────────────────────────────────────┐
│           TCP Server  :9931             │
│                                         │
│  accept() → recv(2048) → parse request  │
│                                         │
│  Route table:                           │
│  /, /en, /index.html  → main_en.html   │
│  /ar, /main_ar.html   → main_ar.html   │
│  /myform.html?image_name=X             │
│    ├─ file exists → 200 + binary body  │
│    └─ not found  → 307 redirect        │
│  /css_files/*         → CSS file       │
│  /images/*            → image file     │
│  otherwise            → HTML file      │
│                                         │
│  Response builder:                      │
│  307 → Status + Location header        │
│  404 → Status + HTML error body        │
│  200 → Status + Content-Type + body    │
└─────────────────────────────────────────┘
```

**Content-Type routing table (MIME map):**

| Extension | Content-Type |
|---|---|
| `html` | `text/html` |
| `css` | `text/css` |
| `png` | `image/png` |
| `jpg` / `jpeg` | `image/jpeg` |
| `mp4` | `video/mp4` |
| unknown | `application/octet-stream` |

---

### TCP/UDP Hybrid Game Server

```
                     ┌──────────────────────────────┐
                     │        Game Server            │
                     │                               │
TCP :6000 ──────────►│  handle_tcp_client()          │
                     │  • Player name registration   │
                     │  • UDP port handshake         │
                     │  • Disconnect handling        │
                     │  • Broadcast: game state      │
                     │                               │
UDP :6001 ──────────►│  handle_udp_messages()        │
                     │  • Guess validation           │
                     │  • Hint feedback (Higher/     │
                     │    Lower/Correct)             │
                     │  • Out-of-range warnings      │
                     └──────────┬───────────────────┘
                                │
                         game_loop() thread
                         • 60s timer
                         • min/max player guard
                         • auto-restart on timeout
```

**Protocol flow — session setup:**

```
Client                              Server
  │                                    │
  │──── TCP connect :6000 ────────────►│
  │◄─── "Enter your name:" ────────────│
  │──── "<player_name>" ──────────────►│
  │◄─── "Welcome <n>! Waiting..." ─────│
  │──── "UDP_PORT:<port>" ────────────►│  (UDP address registration)
  │                                    │
  │       [game starts when ≥2 players join]
  │                                    │
  │──── UDP guess → :6001 ────────────►│
  │◄─── UDP "Higher" / "Lower" / "Correct"──│
  │◄─── TCP broadcast (winner/scores) ─│
```

**Game state machine:**

```
WAITING (< min_players)
    │  ≥ 2 players joined
    ▼
ACTIVE ──── timeout (60s) ──► GAME OVER → restart
    │
    │  correct guess
    ▼
ROUND END → scores broadcast → 5s delay → new round
    │
    │  player count drops below 2
    ▼
PAUSED → "not enough players" broadcast
```

---

## Component Breakdown

### HTTP File Server (`http-server/server.py`)

- Built entirely on Python's `socket` module — no `http.server`, no Flask
- Manual HTTP/1.1 response construction: status line, headers, CRLF separator, binary body
- Query string parsing via `urllib.parse.unquote` for case-insensitive filename matching
- `os.path.normpath` used on CSS paths to prevent basic path traversal
- Binary file streaming using `.read()` on open file handles — no full-file buffering
- Bilingual routing: serves `main_en.html` and `main_ar.html` from separate URL paths
- Image search fallback: when a requested image file is absent, issues a `307 Temporary Redirect` to a Google Images/video search for that filename

### Multiplayer Game Server (`game-server/server.py` + `client.py`)

- Three concurrent threads per server: TCP accept loop, UDP listener, game timer loop
- Each client handled in its own daemon thread (`threading.Thread`, `daemon=True`)
- UDP port registration: client sends `UDP_PORT:<n>` over TCP after connect; server stores `(tcp_conn, tcp_addr, udp_addr)` per player
- Score persistence across rounds using `collections.defaultdict(int)` keyed by player name
- Guess validation: integer parse → range check → comparison → unicast UDP feedback
- Player disconnect handling: removes from dict, broadcasts departure, pauses game if `< min_players`
- Game restart: automatic after 5s cooldown when a round ends (by correct guess or timeout)

---

## Protocols & Signal Tables

### HTTP Status Codes Implemented

| Code | Trigger |
|---|---|
| `200 OK` | File found, returns body |
| `307 Temporary Redirect` | Image not in local `images/` directory |
| `404 Not Found` | Any path that resolves to a nonexistent file |

### UDP Game Message Protocol

| Direction | Message | Meaning |
|---|---|---|
| Client → Server | `<integer>` | Player's guess |
| Server → Client | `Higher` | Guess too low |
| Server → Client | `Lower` | Guess too high |
| Server → Client | `Correct` | Correct guess |
| Server → Client | `Please guess between 1 and 100` | Out-of-range input |
| Server → Client | `Invalid guess. Please enter a number.` | Non-integer input |

### TCP Game Control Messages (broadcast)

| Message | Trigger |
|---|---|
| `Game started with players: <names>` | min_players threshold reached |
| `Player <n> has joined/left` | Connect/disconnect event |
| `<n> guessed the correct number: <n>!` | Correct UDP guess |
| `Current scores:\n<n>: <score>` | After each correct guess |
| `New round starting in 5 seconds...` | Round end |
| `Game over! Time limit reached.` | 60s timer expired |
| `Not enough players. Game paused...` | Player count drops below 2 |

---

## Test & Verification

### HTTP Server Tests

| Test Case | Method | Expected | Result |
|---|---|---|---|
| Root path `/` | Browser GET | Serve `main_en.html` | ✅ |
| `/ar` | Browser GET | Serve `main_ar.html` | ✅ |
| `/images/profile1.png` | Browser GET | Binary PNG response, `image/png` header | ✅ |
| `/myform.html?image_name=profile1.png` | Browser GET | File served | ✅ |
| `/myform.html?image_name=missing.png` | Browser GET | 307 → Google Images | ✅ |
| `/notexist.html` | Browser GET | 404 with client IP/port in body | ✅ |
| CSS load via linked stylesheet | Browser GET | `text/css` header | ✅ |

Verified with browser and Wireshark packet capture; HTTP request/response headers inspected manually.

### Game Server Tests

| Test Case | Result |
|---|---|
| 2 players join → game starts automatically | ✅ |
| Guess 102 (out of range) → warning sent via UDP | ✅ |
| Correct guess → winner announced, scores broadcast, new round begins after 5s | ✅ |
| 1 of 3 players disconnects → game continues with remaining 2 | ✅ |
| Player count drops to 1 → game pauses | ✅ |
| 60s timer expires with no winner → secret revealed, new round | ✅ |
| Max 4 players → 5th connection rejected | ✅ |

---

## Known Limitations

### HTTP Server

**Single-threaded blocking accept loop**
- Root cause: `server_socket.accept()` blocks the main thread; no threading or `select()` used
- Effect: only one client connection processed at a time; concurrent requests queue or drop
- Fix path: wrap `handle_file_request` in a `threading.Thread` per connection, or use `selectors`

**No persistent connections / keep-alive**
- Each connection is closed after one response
- HTTP/1.1 clients that send pipelined requests will not get the expected behavior

**No Content-Length header**
- Response headers omit `Content-Length`; clients must detect EOF to know the body is complete
- Some HTTP clients or proxies may behave incorrectly

**Minimal path traversal protection**
- CSS paths use `os.path.normpath` but image and HTML paths do not; a crafted `../` path could escape the served directories

### Game Server

**No state persistence**
- All scores and player data are in-memory; restarting the server resets everything
- Fix path: serialize `player_scores` to a JSON file on each update

**No authentication**
- Any client that knows the TCP port can join; player names are trust-based, with only a duplicate-name check

**UDP unordered delivery**
- If a player sends two guesses quickly, there is no sequence number; an older guess could be processed after a newer one

**LAN only**
- No NAT traversal or STUN; requires all clients and server to be on the same local network or VPN

---

## How to Run

### HTTP File Server

> **Path note:** The server resolves files relative to its working directory using hardcoded folder names (`html_files`, `css_files`, `images`). You must run it from inside `http-server/` — not from the repo root — otherwise all file lookups will fail with 404.

```bash
cd http-server
python server.py
# Server starts on port 9931
# Open browser: http://localhost:9931
```

### Game Server

> **Path note:** `server.py` and `client.py` have no file I/O dependencies, so working directory doesn't matter. Just ensure both scripts are run with the same Python environment.

**Terminal 1 — start server:**
```bash
cd game-server
python server.py
# TCP listening on :6000, UDP on :6001
```

**Terminal 2+ — connect clients (run once per player):**
```bash
python client.py
# Enter server IP (or press Enter for localhost)
# Enter TCP port (or press Enter for 6000)
# Enter your player name
# Game starts when ≥ 2 players have joined
```

**Gameplay:**
- Once the game starts, type your integer guess and press Enter
- Receive `Higher` / `Lower` / `Correct` feedback via UDP
- First player to guess correctly wins the round

---

## Skills Demonstrated

| What Was Built | Technical Domain |
|---|---|
| Raw socket HTTP server (no framework) | Systems programming, network protocol implementation |
| Manual HTTP/1.1 response construction | Application-layer protocol design |
| TCP/UDP hybrid server with threading | Concurrent server design, transport-layer protocols |
| Protocol state machine (game lifecycle) | Distributed state management |
| Wireshark packet analysis | Network observability, protocol verification |
| Bilingual (AR/EN) content serving | Encoding-aware server-side logic |

---

## Repository Structure

```
tcp-udp-socket-programming/
├── http-server/
│   ├── server.py
│   ├── html_files/
│   │   ├── main_en.html
│   │   ├── main_ar.html
│   │   ├── profile_en.html
│   │   └── profile_ar.html
│   ├── css_files/
│   │   ├── main_style.css
│   │   ├── profile_style_ar.css
│   │   └── profile_style_en.css
│   └── images/
│       ├── profile1.png
│       ├── profile2.png
│       ├── profile3.png
│       ├── topic1.jpg
│       └── topic2.jpg
├── game-server/
│   ├── server.py
│   └── client.py
├── docs/
│   └── socket-programming-report.pdf
└── README.md
```

---

*Computer Networks (ENCS3320) — Electrical and Computer Engineering, Birzeit University, 2024–2025*
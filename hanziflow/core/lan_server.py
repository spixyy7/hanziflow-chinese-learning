"""
core/lan_server.py — HanziFlow LAN Server

Omogućava:
  • LAN discovery (UDP broadcast na portu 55777)
  • Friends system (add_friend, accept_friend, remove_friend)
  • Encrypted chat između prijatelja (XOR + SHA256 key derivation — lagano, bez zavisnosti)
  • Persistence u users/{username}_friends.json i {username}_messages.json

Pokretanje:
    from hanziflow.core.lan_server import LANServer
    server = LANServer(profile, db)
    server.start()          # počinje slušati
    server.stop()           # zaustavi
    server.broadcast_presence()  # objavi sebe na mreži

Poruka format (JSON over TCP port 55778):
    { "type": "friend_request" | "friend_accept" | "chat" | "ping",
      "from": username, "to": username,
      "data": <encrypted string> | <plain string>,
      "timestamp": ISO string }
"""
from __future__ import annotations

import hashlib, json, logging, os, secrets, socket, struct, threading, time
from datetime import datetime, date
from pathlib import Path
from typing import Callable, Optional

from ..config import secret, validate_username

logger = logging.getLogger("HanziFlow.LAN")

DISCOVERY_PORT = 55777
CHAT_PORT      = 55778
BUFFER         = 4096
USERS_DIR      = Path("users")
APP_ID         = "HANZIFLOW_v1"


# ─────────────────────────────────────────────────────────────────────────────
#  Encryption (XOR stream cipher, key = SHA256(shared_secret))
#  NOT suitable for internet — fine for LAN between friends
# ─────────────────────────────────────────────────────────────────────────────

def _make_key(user_a: str, user_b: str) -> bytes:
    """Deterministic 32-byte key from two usernames (alphabetical order)."""
    pair   = "_".join(sorted([user_a, user_b])) + "_HANZIFLOW_2025"
    return hashlib.sha256(pair.encode()).digest()


def _xor_encrypt(plaintext: str, key: bytes) -> str:
    """XOR encrypt, returns hex string."""
    data  = plaintext.encode("utf-8")
    n     = len(key)
    out   = bytes(b ^ key[i % n] for i, b in enumerate(data))
    return out.hex()


def _xor_decrypt(hextext: str, key: bytes) -> str:
    """XOR decrypt from hex string."""
    try:
        data = bytes.fromhex(hextext)
        n    = len(key)
        out  = bytes(b ^ key[i % n] for i, b in enumerate(data))
        return out.decode("utf-8")
    except Exception:
        return "[decryption error]"


# ─────────────────────────────────────────────────────────────────────────────
#  Friends persistence
# ─────────────────────────────────────────────────────────────────────────────

def _friends_path(username: str) -> Path:
    return USERS_DIR / f"{validate_username(username)}_friends.json"


def _messages_path(username: str) -> Path:
    return USERS_DIR / f"{validate_username(username)}_messages.json"


def load_friends(username: str) -> dict:
    """
    Returns:
    {
      "friends":  [username, ...],            # accepted
      "pending":  [username, ...],            # requests sent by me, not yet accepted
      "requests": [username, ...],            # requests received, waiting my accept
    }
    """
    path = _friends_path(username)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"friends": [], "pending": [], "requests": []}


def save_friends(username: str, data: dict) -> None:
    USERS_DIR.mkdir(exist_ok=True)
    path = _friends_path(username)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_messages(username: str) -> list:
    """Returns list of message dicts sorted by timestamp."""
    path = _messages_path(username)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def save_message(username: str, msg: dict) -> None:
    USERS_DIR.mkdir(exist_ok=True)
    msgs = load_messages(username)
    msgs.append(msg)
    # Keep last 500 messages
    if len(msgs) > 500:
        msgs = msgs[-500:]
    _messages_path(username).write_text(
        json.dumps(msgs, ensure_ascii=False, indent=2), encoding="utf-8")


def get_chat_history(my_username: str, friend_username: str) -> list:
    """Returns messages between two users, decrypted, sorted by time."""
    msgs = load_messages(my_username)
    key  = _make_key(my_username, friend_username)
    result = []
    for m in msgs:
        if m.get("from") == friend_username or m.get("to") == friend_username:
            decrypted = _xor_decrypt(m.get("data", ""), key)
            result.append({
                "from":      m.get("from"),
                "to":        m.get("to"),
                "text":      decrypted,
                "timestamp": m.get("timestamp", ""),
                "mine":      m.get("from") == my_username,
            })
    return sorted(result, key=lambda x: x["timestamp"])

def _outbox_path(username: str) -> Path:
    return USERS_DIR / f"{validate_username(username)}_outbox.json"


def load_outbox(username: str) -> list:
    p = _outbox_path(username)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def save_outbox(username: str, items: list) -> None:
    USERS_DIR.mkdir(exist_ok=True)
    _outbox_path(username).write_text(
        json.dumps(items[-200:], ensure_ascii=False, indent=2), encoding="utf-8")


def queue_outbox(username: str, payload: dict) -> None:
    items = load_outbox(username)
    payload.setdefault("queued_at", datetime.now().isoformat())
    items.append(payload)
    save_outbox(username, items)


def dequeue_outbox(username: str, to_username: str) -> list:
    items = load_outbox(username)
    pending = [i for i in items if i.get("to") == to_username]
    remaining = [i for i in items if i.get("to") != to_username]
    save_outbox(username, remaining)
    return pending




# ─────────────────────────────────────────────────────────────────────────────
#  LAN Server
# ─────────────────────────────────────────────────────────────────────────────

class LANServer:
    """
    Manages LAN presence, friend requests, and encrypted messaging.

    All network I/O is on daemon threads — never blocks UI.
    """

    def __init__(self, profile, db):
        self._profile   = profile
        self._db        = db
        self._username  = validate_username(profile.username)
        self._running   = False
        self._peers: dict[str, dict] = {}  # username → {"ip": str, "last_seen": float}
        self._online_timeout = 35  # seconds before considered offline

        # Callbacks (set from UI)
        self.on_friend_request: Optional[Callable] = None  # (from_username)
        self.on_friend_accepted: Optional[Callable] = None # (from_username)
        self.on_message: Optional[Callable] = None          # (msg_dict)
        self.on_peer_discovered: Optional[Callable] = None  # (username, ip)

    # ── Start / stop ──────────────────────────────────────────────────────────

    def start(self) -> None:
        if secret("HANZIFLOW_ENABLE_LAN") != "1":
            logger.info("LAN networking is disabled.")
            return
        if self._running:
            return
        self._running = True
        threading.Thread(target=self._listen_udp,  daemon=True, name="LAN-UDP").start()
        threading.Thread(target=self._listen_tcp,  daemon=True, name="LAN-TCP").start()
        threading.Thread(target=self._broadcast_loop, daemon=True, name="LAN-Bcast").start()
        logger.info(f"LAN server started for {self._username}")

    def stop(self) -> None:
        self._running = False
        logger.info("LAN server stopped")

    # ── UDP discovery ─────────────────────────────────────────────────────────

    def _broadcast_loop(self) -> None:
        """Broadcast presence every 10 seconds."""
        while self._running:
            self.broadcast_presence()
            time.sleep(10)

    def broadcast_presence(self) -> None:
        if not self._running:
            return
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(2)
            msg  = json.dumps({
                "app":      APP_ID,
                "type":     "presence",
                "username": self._username,
            }).encode()
            sock.sendto(msg, ("<broadcast>", DISCOVERY_PORT))
            sock.close()
        except Exception as e:
            logger.debug(f"UDP broadcast error: {e}")

    def _listen_udp(self) -> None:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", DISCOVERY_PORT))
            sock.settimeout(2)
            while self._running:
                try:
                    data, addr = sock.recvfrom(BUFFER)
                    msg = json.loads(data.decode())
                    if msg.get("app") != APP_ID:
                        continue
                    if msg.get("type") == "presence":
                        uname = validate_username(msg.get("username", ""))
                        ip    = addr[0]
                        if not uname or uname == self._username:
                            continue
                        is_new = uname not in self._peers
                        self._peers[uname] = {"ip": ip, "last_seen": time.time()}
                        if is_new:
                            if self.on_peer_discovered:
                                self.on_peer_discovered(uname, ip)
                        pending = load_outbox(self._username)
                        has_pending = any(i.get("to") == uname for i in pending)
                        if has_pending:
                            threading.Thread(
                                target=self._flush_outbox,
                                args=(uname,), daemon=True).start()
                except socket.timeout:
                    pass
                except Exception as e:
                    logger.debug(f"UDP recv error: {e}")
        except Exception as e:
            logger.warning(f"UDP listen error: {e}")

    # ── TCP messaging ─────────────────────────────────────────────────────────

    def _listen_tcp(self) -> None:
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("", CHAT_PORT))
            srv.listen(5)
            srv.settimeout(2)
            while self._running:
                try:
                    conn, _ = srv.accept()
                    threading.Thread(
                        target=self._handle_connection,
                        args=(conn,), daemon=True).start()
                except socket.timeout:
                    pass
            srv.close()
        except Exception as e:
            logger.warning(f"TCP listen error: {e}")

    def _handle_connection(self, conn: socket.socket) -> None:
        try:
            conn.settimeout(5)
            raw  = conn.recv(BUFFER * 4)
            msg  = json.loads(raw.decode())
            if msg.get("to") != self._username:
                return
            mtype = msg.get("type")
            frm   = validate_username(msg.get("from", ""))

            if mtype == "friend_request":
                self._on_friend_request(frm)
            elif mtype == "friend_accept":
                self._on_friend_accepted(frm)
            elif mtype == "friend_remove":
                self._on_friend_removed(frm)
            elif mtype == "chat":
                self._on_chat_message(msg, frm)
            elif mtype == "ping":
                conn.send(b"pong")
        except Exception as e:
            logger.debug(f"TCP handle error: {e}")
        finally:
            try: conn.close()
            except Exception: pass

    def _send_tcp(self, to_username: str, payload: dict) -> bool:
        validate_username(to_username)
        if not self._running:
            return False
        ip = (self._peers.get(to_username) or {}).get("ip")
        if not ip:
            return False
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((ip, CHAT_PORT))
            sock.send(json.dumps(payload).encode())
            sock.close()
            return True
        except Exception as e:
            logger.debug(f"TCP send to {to_username} failed: {e}")
            return False

    def _deliver_local(self, to_username: str, payload: dict) -> bool:
        """
        Direktna isporuka kada su oba usera na istom racunaru.
        Upisuje u fajl primaoca umjesto TCP-a.
        """
        try:
            if not self._db.user_exists(validate_username(to_username)):
                return False
            from ..core.notifications import NotifStore
            ns = NotifStore(to_username)
            mtype = payload.get("type", "")
            frm   = payload.get("from", self._username)
            if mtype == "friend_request":
                rec_data = load_friends(to_username)
                if frm not in rec_data.get("requests", []):
                    rec_data.setdefault("requests", []).append(frm)
                    save_friends(to_username, rec_data)
                ns.add_friend_request(frm)
                logger.info(f"Local delivery: friend_request from {frm} to {to_username}")
                return True
            elif mtype == "friend_accept":
                rec_data = load_friends(to_username)
                if frm in rec_data.get("pending", []):
                    rec_data["pending"].remove(frm)
                if frm not in rec_data.get("friends", []):
                    rec_data.setdefault("friends", []).append(frm)
                save_friends(to_username, rec_data)
                ns.add_friend_accepted(frm)
                logger.info(f"Local delivery: friend_accept from {frm} to {to_username}")
                return True
            elif mtype == "friend_remove":
                rec_data = load_friends(to_username)
                if frm in rec_data.get("friends", []):
                    rec_data["friends"].remove(frm)
                save_friends(to_username, rec_data)
                logger.info(f"Local delivery: friend_remove from {frm} to {to_username}")
                return True
            elif mtype == "chat":
                save_message(to_username, payload)
                logger.info(f"Local delivery: chat from {frm} to {to_username}")
                return True
        except Exception as e:
            logger.debug(f"Local delivery failed: {e}")
        return False

    def _send_or_queue(self, to_username: str, payload: dict) -> bool:
        if self._deliver_local(to_username, payload):
            return True
        sent = self._send_tcp(to_username, payload)
        if not sent:
            queue_outbox(self._username, payload)
            logger.info(f"Queued offline message to {to_username}: {payload.get('type')}")
        return True

    def _flush_outbox(self, to_username: str) -> None:
        pending = dequeue_outbox(self._username, to_username)
        if not pending:
            return
        logger.info(f"Flushing {len(pending)} queued messages to {to_username}")
        for payload in pending:
            sent = self._send_tcp(to_username, payload)
            if not sent:
                queue_outbox(self._username, payload)
                break

    # ── Friend actions ────────────────────────────────────────────────────────

    def send_friend_request(self, to_username: str) -> bool:
        """Send a friend request to another user on LAN."""
        data = load_friends(self._username)
        if to_username in data.get("friends", []):
            return False
        if to_username in data.get("pending", []):
            return False
        # Also check if we already received one from them
        if to_username in data.get("requests", []):
            return False

        data["pending"].append(to_username)
        save_friends(self._username, data)

        self._send_or_queue(to_username, {
            "type": "friend_request",
            "from": self._username,
            "to":   to_username,
            "timestamp": datetime.now().isoformat(),
        })
        return True

    def accept_friend_request(self, from_username: str) -> None:
        """Accept a received friend request."""
        data = load_friends(self._username)
        if from_username in data["requests"]:
            data["requests"].remove(from_username)
        if from_username not in data["friends"]:
            data["friends"].append(from_username)
        save_friends(self._username, data)

        self._send_or_queue(from_username, {
            "type": "friend_accept",
            "from": self._username,
            "to":   from_username,
            "timestamp": datetime.now().isoformat(),
        })

    def decline_friend_request(self, from_username: str) -> None:
        data = load_friends(self._username)
        if from_username in data.get("requests", []):
            data["requests"].remove(from_username)
        save_friends(self._username, data)
        # Remove from sender's pending list
        sender_data = load_friends(from_username)
        if self._username in sender_data.get("pending", []):
            sender_data["pending"].remove(self._username)
            save_friends(from_username, sender_data)

    def remove_friend(self, friend_username: str) -> None:
        data = load_friends(self._username)
        if friend_username in data["friends"]:
            data["friends"].remove(friend_username)
        save_friends(self._username, data)
        self._send_or_queue(friend_username, {
            "type": "friend_remove",
            "from": self._username,
            "to":   friend_username,
            "timestamp": datetime.now().isoformat(),
        })

    def send_message(self, to_username: str, text: str) -> bool:
        """Send an encrypted chat message."""
        key       = _make_key(self._username, to_username)
        encrypted = _xor_encrypt(text, key)
        ts        = datetime.now().isoformat()

        msg = {
            "type":      "chat",
            "from":      self._username,
            "to":        to_username,
            "data":      encrypted,
            "timestamp": ts,
        }
        save_message(self._username, msg)

        self._send_or_queue(to_username, msg)
        return True

    def get_online_friends(self) -> list[str]:
        data    = load_friends(self._username)
        friends = data.get("friends", [])
        now = time.time()
        return [f for f in friends
                if f in self._peers and
                now - self._peers[f].get("last_seen", 0) < self._online_timeout]

    def get_all_peers(self) -> dict:
        """All recently discovered users on LAN {username: ip}."""
        now = time.time()
        return {u: d["ip"] for u, d in self._peers.items()
                if now - d.get("last_seen", 0) < self._online_timeout}

    def get_peer_last_seen(self, username: str) -> float:
        """Returns unix timestamp of last seen, or 0 if never."""
        return self._peers.get(username, {}).get("last_seen", 0)

    def is_online(self, username: str) -> bool:
        """True if user sent a presence broadcast within timeout window."""
        ls = self.get_peer_last_seen(username)
        return ls > 0 and (time.time() - ls) < self._online_timeout

    # ── Internal event handlers ───────────────────────────────────────────────

    def _on_friend_request(self, from_username: str) -> None:
        data = load_friends(self._username)
        if from_username not in data["requests"]:
            data["requests"].append(from_username)
        save_friends(self._username, data)
        logger.info(f"Friend request from {from_username}")
        if self.on_friend_request:
            self.on_friend_request(from_username)

    def _on_friend_removed(self, from_username: str) -> None:
        data = load_friends(self._username)
        if from_username in data.get("friends", []):
            data["friends"].remove(from_username)
        save_friends(self._username, data)
        logger.info(f"Removed from friends by {from_username}")

    def _on_friend_accepted(self, from_username: str) -> None:
        data = load_friends(self._username)
        if from_username in data.get("pending", []):
            data["pending"].remove(from_username)
        if from_username not in data["friends"]:
            data["friends"].append(from_username)
        save_friends(self._username, data)
        logger.info(f"Friend accepted: {from_username}")
        if self.on_friend_accepted:
            self.on_friend_accepted(from_username)

    def _on_chat_message(self, msg: dict, from_username: str) -> None:
        if from_username not in load_friends(self._username).get("friends", []):
            return
        save_message(self._username, msg)
        logger.debug(f"Chat message from {from_username}")
        if self.on_message:
            key   = _make_key(self._username, from_username)
            plain = _xor_decrypt(msg.get("data", ""), key)
            self.on_message({
                "from":      from_username,
                "text":      plain,
                "timestamp": msg.get("timestamp", ""),
                "mine":      False,
            })
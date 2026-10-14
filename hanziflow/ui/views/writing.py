"""
ui/views/writing.py — Writing Mode v5 (SRS Edition)
• AI generates sentences from user vocab (Gemini), cached locally
• Smart queue: Spaced Repetition System (SRS) sa hibernacijom
• Gigantski bonus za najnovije reči
• Auto-advance after correct answer (no manual Next button)
• Smarter translation checker (semicolon split, containment)
• Language from profile.lang (no per-view toggle)
"""
from __future__ import annotations
import hashlib, json, math, random, threading, time, unicodedata
import tkinter as tk
from datetime import date
from pathlib import Path
from typing import Callable, Optional

from ..theme import C, F, S, GhostButton, PrimaryButton, SuccessButton
from ..widgets import NotificationManager
from ...core import Database, UserProfile, check_achievements, play_audio, gemini
from ...core.adaptive import WeaknessDetector
from ...config import validate_username

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_ATTEMPTS      = 3
TEXTS_PER_SESSION = 6
STREAK_THRESHOLD  = 3
CACHE_MAX         = 50
DEFAULT_TIME      = {"easy": 40, "medium": 70, "hard": 100}

G = "#FFD700"; OK = "#4CAF50"; WN = "#FF9800"; NG = "#F44336"
LB = "#1E88E5"; PU = "#8E24AA"; DB = "#0D1B2A"; GB = "#665500"
TB = "#1E1E2E"; TF = "#EEEEEE"


# ── Sentence cache (SRS) ──────────────────────────────────────────────────────
def _cpath(u): return Path("users") / f"{validate_username(u)}_writing_cache.json"

def _load_cache(u):
    p = _cpath(u)
    if p.exists():
        try: return json.loads(p.read_text(encoding="utf-8"))
        except Exception: pass
    return []

def _save_cache(u, s):
    p = _cpath(u); p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps(s[-CACHE_MAX:], ensure_ascii=False, indent=2), encoding="utf-8")

def _add_to_cache(u, s):
    cache = _load_cache(u)
    if s.get("chinese") not in {c.get("chinese") for c in cache}:
        # Inicijalizujemo SRS statistiku
        s["_stats"] = {"seen": 0, "mistakes": 0, "streak": 0, "last_practiced": 0, "last_score": 0}
        cache.append(s); _save_cache(u, cache)

def _update_cache_stats(u, txt_id, mistakes, score):
    if not txt_id: return
    cache = _load_cache(u)
    now = time.time()
    for c in cache:
        if c.get("id") == txt_id:
            stats = c.get("_stats", {"seen": 0, "mistakes": 0, "streak": 0, "last_practiced": 0, "last_score": 0})
            stats["seen"] = stats.get("seen", 0) + 1
            stats["last_practiced"] = now
            stats["last_score"] = score

            if mistakes == 0:
                # Ako je tačno odgovorio iz prve, raste mu niz (streak)
                stats["streak"] = stats.get("streak", 0) + 1
                stats["mistakes"] = 0  # Brišemo prethodne greške jer je sada naučio
            else:
                # Ako je pogrešio, niz se resetuje na nulu i mora ispočetka!
                stats["streak"] = 0
                stats["mistakes"] = stats.get("mistakes", 0) + mistakes

            c["_stats"] = stats
            break
    _save_cache(u, cache)


# ── Static fallback texts ─────────────────────────────────────────────────────
STATIC = [
    {"id":"s01","difficulty":"easy","chinese":"我每天早上喝咖啡。","pinyin":"Wǒ měitiān zǎoshang hē kāfēi.",
     "words":{"我":{"en":"I","sr":"Ja"},"每天":{"en":"every day","sr":"svaki dan"},
              "早上":{"en":"morning","sr":"jutro"},"喝":{"en":"drink","sr":"piti"},"咖啡":{"en":"coffee","sr":"kafa"}},
     "answers":{"en":["I drink coffee every morning.","Every morning I drink coffee."],
                "sr":["Svaki dan ujutro pijem kafu.","Svako jutro pijem kafu."]}},
    {"id":"s02","difficulty":"medium","chinese":"她正在学习中文，因为她想去中国旅游。","pinyin":"Tā zhèngzài xuéxí Zhōngwén.",
     "words":{"她":{"en":"she","sr":"ona"},"学习":{"en":"study","sr":"uciti"},"中文":{"en":"Chinese","sr":"kineski"},
              "因为":{"en":"because","sr":"jer"},"中国":{"en":"China","sr":"Kina"},"旅游":{"en":"travel","sr":"putovati"}},
     "answers":{"en":["She is studying Chinese because she wants to travel to China.",
                      "She is learning Chinese because she wants to visit China."],
                "sr":["Ona uci kineski jer zeli da putuje u Kinu."]}},
    {"id":"s03","difficulty":"easy","chinese":"如果明天天气好，我们就去爬山。","pinyin":"Rúguǒ míngtiān tiānqì hǎo.",
     "words":{"如果":{"en":"if","sr":"ako"},"明天":{"en":"tomorrow","sr":"sutra"},
              "天气":{"en":"weather","sr":"vreme"},"我们":{"en":"we","sr":"mi"},"爬山":{"en":"hike","sr":"planinariti"}},
     "answers":{"en":["If the weather is nice tomorrow we will go hiking.",
                      "We will go hiking tomorrow if the weather is good."],
                "sr":["Ako sutra bude lepo vreme idemo na planinarenje."]}},
    {"id":"s04","difficulty":"medium","chinese":"我喜欢在周末和家人一起吃饭聊天。","pinyin":"Wǒ xǐhuān zài zhōumò hé jiārén yīqǐ.",
     "words":{"喜欢":{"en":"like","sr":"voleti"},"周末":{"en":"weekend","sr":"vikend"},
              "家人":{"en":"family","sr":"porodica"},"一起":{"en":"together","sr":"zajedno"},
              "吃饭":{"en":"eat","sr":"jesti"},"聊天":{"en":"chat","sr":"razgovarati"}},
     "answers":{"en":["I like to eat and chat with my family on weekends."],
                "sr":["Volim da jedem i razgovaram sa porodicom vikendom."]}},
    {"id":"s05","difficulty":"hard","chinese":"这个城市的交通非常拥挤，尤其是在上下班高峰期。","pinyin":"Zhège chéngshì de jiāotōng.",
     "words":{"交通":{"en":"traffic","sr":"saobracaj"},"非常":{"en":"very","sr":"veoma"},
              "拥挤":{"en":"congested","sr":"zagušen"},"尤其是":{"en":"especially","sr":"narocito"}},
     "answers":{"en":["The traffic in this city is very congested especially during rush hours."],
                "sr":["Saobracaj u ovom gradu je veoma zagušen narocito u spicu."]}},
    {"id":"s06","difficulty":"easy","chinese":"你好！你叫什么名字？","pinyin":"Nǐ hǎo! Nǐ jiào shénme míngzi?",
     "words":{"你好":{"en":"hello","sr":"zdravo"},"叫":{"en":"called","sr":"zovem se"},"名字":{"en":"name","sr":"ime"}},
     "answers":{"en":["Hello what is your name?","Hi what is your name?"],
                "sr":["Zdravo kako se zoves?"]}},
    {"id":"s07","difficulty":"medium","chinese":"我昨天晚上复习了生词，现在感觉好多了。","pinyin":"Wǒ zuótiān wǎnshang fùxí le shēngcí.",
     "words":{"昨天":{"en":"yesterday","sr":"juce"},"晚上":{"en":"evening","sr":"vece"},
              "复习":{"en":"review","sr":"ponoviti"},"生词":{"en":"new words","sr":"nove reci"},
              "现在":{"en":"now","sr":"sada"}},
     "answers":{"en":["Last night I reviewed new words and now I feel much better.",
                      "I reviewed vocabulary last night now I feel much better."],
                "sr":["Sinoc sam ponovio nove reci i sada se osecam mnogo bolje."]}},
]


# ── Queue builder ─────────────────────────────────────────────────────────────
def _score(txt, weak, vocab, newest_words):
    w = set(txt.get("words", {}).keys())
    f = set(txt.get("focus", []))
    base_score = (len(w & weak) + len(f & weak)) * 3 + len(w & vocab)

    # === GIGANTSKI BONUS ZA NOVE REČI ===
    if w & newest_words:
        base_score += 200
    # ====================================

    stats = txt.get("_stats", {"seen": 0, "mistakes": 0, "streak": 0, "last_practiced": 0})
    streak = stats.get("streak", 0)
    mistakes = stats.get("mistakes", 0)
    last_practiced = stats.get("last_practiced", 0)
    now = time.time()

    if last_practiced == 0:
        return base_score + 5

    time_since_last = now - last_practiced

    if mistakes > 0 or streak == 0:
        return base_score + 15

    intervals = {1: 86400, 2: 86400 * 3, 3: 86400 * 7}
    required_interval = intervals.get(streak, 86400 * 14)

    if time_since_last >= required_interval:
        return base_score + 25
    else:
        return base_score - 50

def _build_queue(profile, n=TEXTS_PER_SESSION):
    try:
        wd    = WeaknessDetector(profile)
        weak  = {w.hanzi for w in wd.weak_words(threshold=0.65)}
        vocab = {w.get("hanzi","") for w in profile.vocab}
    except Exception:
        weak, vocab = set(), set()

    # Izolujemo 15 najnovijih reči koje si ubacio
    newest_words = {w.get("hanzi") for w in profile.vocab[-15:] if w.get("hanzi")}

    ai = sorted(_load_cache(profile.username),
                key=lambda t: _score(t, weak, vocab, newest_words) + random.uniform(0, 3.5), reverse=True)
    st = sorted(STATIC,
                key=lambda t: _score(t, weak, vocab, newest_words) + random.uniform(0, 1.5), reverse=True)

    n_ai  = min(len(ai), max(1, int(n * 0.65)))
    q     = ai[:n_ai] + st[:n - n_ai]
    random.shuffle(q)
    return q[:n]


# ── AI generation (background) ────────────────────────────────────────────────
def _gen_async(profile, count=4, on_done=None):
    def _work():
        try:
            wd   = WeaknessDetector(profile)
            weak = [w.hanzi for w in wd.weak_words(threshold=0.65)]
        except Exception:
            weak = []

        vocab = list(profile.vocab)
        if not vocab: return

        # Analiziraj SRS keš. Koje reči spavaju u hibernaciji?
        cache = _load_cache(profile.username)
        mastered_words = set()
        now = time.time()

        for c in cache:
            stats = c.get("_stats", {})
            streak = stats.get("streak", 0)
            last_practiced = stats.get("last_practiced", 0)
            intervals = {1: 86400, 2: 86400 * 3, 3: 86400 * 7}
            required_interval = intervals.get(streak, 86400 * 14)

            # Reč je "mastered" SAMO ako ima streak i JOŠ NIJE vreme za ponavljanje
            if streak > 0 and (now - last_practiced) < required_interval:
                for w in c.get("words", {}).keys():
                    mastered_words.add(w)

        # Nove reči (poslednjih 15 dodatih) uvek imaju prioritet
        newest_words = vocab[-15:] if len(vocab) > 15 else vocab

        done = 0
        for _ in range(count * 3):
            if done >= count: break
            try:
                # Pravimo pool (bazen) reči
                pool = newest_words + random.sample(vocab, min(25, len(vocab)))
                pool_unique = list({v.get("hanzi", ""): v for v in pool if v.get("hanzi")}.values())

                # UZIMAMO SAMO ONE KOJE NISU MASTERED (osim ako nemamo šta drugo)
                filtered_pool = [v for v in pool_unique if v.get("hanzi") not in mastered_words]
                if len(filtered_pool) < 10:
                    filtered_pool = pool_unique # Ako smo previše strogi, vrati sve

                sample = random.sample(filtered_pool, min(20, len(filtered_pool)))
                r = gemini.generate_writing_sentence(sample, weak, lang=profile.lang)

                if r and r.get("chinese"):
                    _add_to_cache(profile.username, r)
                    done += 1
                    if on_done: on_done(r)
            except Exception: pass
            time.sleep(0.6)

    threading.Thread(target=_work, daemon=True, name="WritingAI").start()


# ── Timer ─────────────────────────────────────────────────────────────────────
def _est_time(txt, profile):
    h = getattr(profile, "xp_at_login", {})
    if isinstance(h, dict):
        s = h.get(f"wt_{txt.get('id','')}")
        if s: return max(20, int(float(s) * 1.25))
    return max(20, DEFAULT_TIME.get(txt.get("difficulty", "medium"), 70) + len(txt.get("chinese", "")) * 2)

def _save_time(tid, el, profile, db):
    try:
        if not isinstance(profile.xp_at_login, dict): profile.xp_at_login = {}
        k = f"wt_{tid}"; p = profile.xp_at_login.get(k)
        profile.xp_at_login[k] = (float(p) + el) / 2 if p else el
        db.save_user(profile)
    except Exception: pass


# ── Translation checker ───────────────────────────────────────────────────────
_STOPS = {"a","an","the","to","of","in","on","at","is","are","i","he","she","we","it","and","or","but","je","se","da","u"}

def _norm(t):
    t = t.lower().strip()
    t = "".join(c for c in unicodedata.normalize("NFD",t) if unicodedata.category(c)!="Mn")
    for ch in ".,!?;:'\"()-": t=t.replace(ch," ")
    return " ".join(t.split())

def _tok(t): return {w for w in _norm(t).split() if w and w not in _STOPS}
def _jac(a,b): sa,sb=_tok(a),_tok(b); return len(sa&sb)/len(sa|sb) if (sa|sb) else 1.0
def _cont(u,r): su,sr=_tok(u),_tok(r); return len(su&sr)/len(su) if su else 0.0

def _exp(answers):
    out = list(answers)
    for a in answers:
        for p in a.split(";"):
            p=p.strip()
            if not p: continue
            out += [p, p.lower()]
            if p.lower().startswith("to "): out += [p[3:], p[3:].lower()]
            for pr in ("a ","an ","the "):
                if p.lower().startswith(pr): out.append(p[len(pr):])
    return list(dict.fromkeys(out))

def check_translation(inp, answers, lang):
    un = _norm(inp)
    if not un:
        return {"correct":False,"score":0,"feedback":"Unesite prevod." if lang=="sr" else "Enter a translation."}
    ex = _exp(answers)
    for a in ex:
        if un == _norm(a):
            return {"correct":True,"score":100,"feedback":"Savršeno! ✓" if lang=="sr" else "Perfect! ✓"}
    bj=bc=0.0
    for a in ex: bj=max(bj,_jac(un,a)); bc=max(bc,_cont(un,a))
    if bj>=0.68: return {"correct":True, "score":int(bj*100),"feedback":"Odlično! ✓" if lang=="sr" else "Excellent! ✓"}
    if bc>=0.82: return {"correct":True, "score":int(bc*100),"feedback":"Prihvaćeno! ✓" if lang=="sr" else "Accepted! ✓"}
    if bj>=0.48 or bc>=0.60: return {"correct":False,"score":int(max(bj,bc)*100),"feedback":"Delimično tačno." if lang=="sr" else "Partially correct."}
    return {"correct":False,"score":int(bj*100),"feedback":"Netačno." if lang=="sr" else "Incorrect."}


# ── Completion overlay ────────────────────────────────────────────────────────
class _Overlay:
    CC = ["#00FF88","#FFD700","#FF6600","#00AAFF","#FF00AA","#AAFFAA"]

    def __init__(self, root, chinese, trans, on_done):
        self._root    = root
        self._done    = on_done
        self._closed  = False
        self._audio_done = False
        self._min_shown  = False  # shown for at least min_time

        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()

        w = tk.Toplevel(root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.attributes("-alpha", 0.0)
        w.geometry(f"{sw}x{sh}+0+0")
        w.configure(bg="#030810")

        cv = tk.Canvas(w, bg="#030810", highlightthickness=0, width=sw, height=sh)
        cv.pack(fill="both", expand=True)
        self._w = w; self._cv = cv; self._sw = sw; self._sh = sh; self._ids = []

        # Chinese + translation text
        cv.create_text(sw//2, sh//2-80, text=chinese,
                       font=("Segoe UI Emoji", 42, "bold"), fill=G, tags="t")
        cv.create_text(sw//2, sh//2+10, text=trans,
                       font=("Segoe UI Emoji", 18), fill="#FFFFFF", tags="t", width=sw-80)

        # Audio progress bar
        bar_w = 300; bar_h = 6
        bx = sw//2 - bar_w//2; by = sh//2 + 70
        cv.create_rectangle(bx, by, bx+bar_w, by+bar_h,
                            fill="#333355", outline="", tags="t")
        self._bar_bg  = (bx, by, bar_w, bar_h)
        self._bar_fill = cv.create_rectangle(bx, by, bx, by+bar_h,
                                             fill="#00FF88", outline="", tags="t")
        # 🔊 icon
        cv.create_text(bx-24, by+bar_h//2, text="🔊",
                       font=("Segoe UI Emoji", 14), tags="t")

        cv.create_text(sw//2, sh-50, text="[ tap to continue ]",
                       font=("Segoe UI Emoji", 11), fill="#555", tags="t")

        self._ps = [
            {"x": random.randint(sw//4, sw*3//4),
             "y": random.randint(-sh//2, sh//4),
             "vx": random.uniform(-3, 3), "vy": random.uniform(2, 6),
             "r": random.randint(4, 14), "col": random.choice(self.CC),
             "rot": random.uniform(0, 360), "dr": random.uniform(-8, 8)}
            for _ in range(55)
        ]
        w.bind("<Button-1>", lambda e: self._on_tap())
        self._fi()

        # Play audio and track progress
        self._audio_start = time.time()
        self._audio_dur   = 3.0  # estimated, updated after play
        try:
            play_audio(chinese, on_done=self._on_audio_done)
            self._audio_dur = max(2.0, len(chinese) * 0.4)
        except Exception:
            self._audio_dur = max(2.0, len(chinese) * 0.4)
            w.after(int(self._audio_dur * 1000), self._on_audio_done)

        self._progress_anim()
        w.after(int(self._audio_dur * 1000) + 400, self._on_min_time)

    def _on_tap(self):
        if self._audio_done:
            self._close()

    def _on_audio_done(self):
        self._audio_done = True
        if self._min_shown:
            self._close()

    def _on_min_time(self):
        self._min_shown = True
        if self._audio_done:
            self._close()

    def _progress_anim(self):
        if self._closed: return
        try:
            elapsed = time.time() - self._audio_start
            frac    = min(1.0, elapsed / max(self._audio_dur, 0.1))
            bx, by, bar_w, bar_h = self._bar_bg
            self._cv.coords(self._bar_fill,
                            bx, by, bx + int(bar_w * frac), by + bar_h)
            if frac < 1.0:
                self._w.after(50, self._progress_anim)
            else:
                self._cv.coords(self._bar_fill, bx, by, bx + bar_w, by + bar_h)
        except tk.TclError:
            pass

    def _fi(self, s=0):
        a = min(1.0, s/10)
        try: self._w.attributes("-alpha", a)
        except tk.TclError: return
        if a < 1.0: self._w.after(16, lambda: self._fi(s+1))
        else: self._anim()

    def _anim(self):
        if self._closed: return
        cv = self._cv
        for i in self._ids: cv.delete(i)
        self._ids.clear(); alive = []
        for p in self._ps:
            p["x"] += p["vx"]; p["y"] += p["vy"]
            p["vy"] += 0.15;   p["rot"] += p["dr"]
            if p["y"] < self._sh + 20:
                cx, cy = p["x"], p["y"]
                a = math.radians(p["rot"]); r = p["r"]; pts = []
                for dx, dy in [(-r,-r),(r,-r),(r,r),(-r,r)]:
                    pts.extend([cx + dx*math.cos(a) - dy*math.sin(a),
                                 cy + dx*math.sin(a) + dy*math.cos(a)])
                self._ids.append(cv.create_polygon(pts, fill=p["col"], outline=""))
                cv.tag_raise("t")
                alive.append(p)
        self._ps = alive
        if alive: self._w.after(28, self._anim)

    def _close(self):
        if self._closed: return
        self._closed = True
        self._fo()

    def _fo(self, s=0):
        a = max(0.0, 1.0 - s/8)
        try: self._w.attributes("-alpha", a)
        except tk.TclError:
            if self._done: self._done()
            return
        if a > 0:
            self._w.after(16, lambda: self._fo(s+1))
        else:
            try: self._w.destroy()
            except tk.TclError: pass
            if self._done: self._done()


# ── Strings ───────────────────────────────────────────────────────────────────
_T = {
    "en": {"title":"✍  Writing","back":"Back","choose":"Choose your mode",
           "learn":"Learning Mode","learn_s":"Hover tooltips · Pinyin · TTS · AI sentences",
           "chal":"Challenge Mode","chal_s":"Timer · No hints · 3 attempts · AI sentences",
           "start":"Start","prog":"Text {}/{}","diff":"{}","hint":"Type your translation here...",
           "check":"✔  Check","next":"Next  →","skip":"Skip","cor_ans":"Correct answer:",
           "done":"Session Complete! 🎉","snote":"Keep it up every day!","new":"New Session",
           "ml":"LEARNING","mc":"CHALLENGE","sg":"🔥 Streak +1!  Day {}",
           "tl":"{} s","tu":"⏱ Time's up!","lis":"🔊 Listen","ai":"✨ AI",
           "gen":"Generating AI sentences..."},
    "sr": {"title":"✍  Writing","back":"Nazad","choose":"Izaberi mod",
           "learn":"Learning Mode","learn_s":"Hover prevodi · Pinyin · TTS · AI rečenice",
           "chal":"Challenge Mode","chal_s":"Timer · Bez pomoći · 3 pokušaja · AI rečenice",
           "start":"Počni","prog":"Tekst {}/{}","diff":"{}","hint":"Unesite prevod ovde...",
           "check":"✔  Provjeri","next":"Sledeći  →","skip":"Preskoči","cor_ans":"Tačan prevod:",
           "done":"Sesija završena! 🎉","snote":"Svaki dan čuva tvoj streak!","new":"Nova sesija",
           "ml":"LEARNING","mc":"CHALLENGE","sg":"🔥 Streak +1!  Dan {}",
           "tl":"{} s","tu":"⏱ Vreme isteklo!","lis":"🔊 Slušaj","ai":"✨ AI",
           "gen":"Generišem AI rečenice..."},
}


# ── WritingView ───────────────────────────────────────────────────────────────
class WritingView(tk.Frame):
    def __init__(self, parent, profile: UserProfile,
                 notif: NotificationManager, on_back: Callable):
        super().__init__(parent, bg=C.BG)
        self._p = profile; self._n = notif; self._ob = on_back
        self._db = Database(); self._lang = profile.lang
        self._mode = None; self._q = []; self._idx = 0
        self._att = 0; self._done = 0; self._xp = 0
        self._tips = []; self._tj = None; self._ts = 0.0
        self._tl = 0; self._bl = False; self._gl = None
        self._build_hdr()
        self._body = tk.Frame(self, bg=C.BG); self._body.pack(fill="both", expand=True)
        self._mode_sel()

    def _t(self, k, *a):
        v = _T[self._lang].get(k, k)
        return v.format(*a) if a else v

    def _build_hdr(self):
        h = tk.Frame(self, bg=C.BG_SIDEBAR); h.pack(fill="x")
        GhostButton(h, text=self._t("back"), command=self._back).pack(side="left", padx=S.MD, pady=S.SM)
        tk.Label(h, text=self._t("title"), bg=C.BG_SIDEBAR, fg=C.TEXT, font=F.H2).pack(side="left")
        self._ml = tk.Label(h, text="", bg=C.BG_SIDEBAR, fg=C.TEXT_MUTED, font=F.SMALL)
        self._ml.pack(side="right", padx=S.MD)

    def _back(self):
        self._stop_t(); self._dtips()
        if self._ob: self._ob()

    def _mode_sel(self):
        self._clr(); self._ml.config(text=""); self._lang = self._p.lang

        if self._p.vocab:
            def _cb(t):
                try:
                    if self._gl and self._gl.winfo_exists():
                        n = len(_load_cache(self._p.username))
                        self._gl.config(text=f"✨ {n} AI sentences ready", fg=OK)
                except Exception: pass

            cache = _load_cache(self._p.username)
            active_count = 0
            now = time.time()

            newest_hanzi = {w.get("hanzi") for w in self._p.vocab[-15:] if w.get("hanzi")}
            words_in_cache = set()

            for c in cache:
                words_in_cache.update(c.get("words", {}).keys())
                stats = c.get("_stats", {})
                streak = stats.get("streak", 0)
                last_practiced = stats.get("last_practiced", 0)
                intervals = {1: 86400, 2: 86400 * 3, 3: 86400 * 7}
                required_interval = intervals.get(streak, 86400 * 14)

                if streak == 0 or (now - last_practiced) >= required_interval:
                    active_count += 1

            missing_new_words = newest_hanzi - words_in_cache

            if missing_new_words or active_count < 10:
                _gen_async(self._p, count=8, on_done=_cb)
            else:
                _gen_async(self._p, count=2, on_done=_cb)

        outer = tk.Frame(self._body, bg=C.BG); outer.pack(expand=True, fill="both", padx=S.XL, pady=S.LG)
        tk.Label(outer, text=self._t("choose"), bg=C.BG, fg=C.TEXT, font=F.H1).pack(pady=(S.LG, S.LG))
        for mk, col, lk, sk in [("learning", LB, "learn", "learn_s"), ("challenge", PU, "chal", "chal_s")]:
            card = tk.Frame(outer, bg=col, cursor="hand2"); card.pack(fill="x", pady=S.SM)
            inn = tk.Frame(card, bg=col); inn.pack(fill="x", padx=S.LG, pady=S.MD)
            tk.Label(inn, text=self._t(lk), bg=col, fg="#FFF", font=(F.FAMILY,16,"bold")).pack(anchor="w")
            tk.Label(inn, text=self._t(sk), bg=col, fg="#DDD", font=F.SMALL).pack(anchor="w", pady=(2,0))
            tk.Button(inn, text=self._t("start")+"  →", bg="#FFF", fg=col, font=F.BODY_B,
                      relief="flat", bd=0, cursor="hand2", padx=S.LG, pady=S.XS,
                      command=lambda m=mk: self._start(m)).pack(anchor="e", pady=(S.SM,0))
            for w in [card, inn]: w.bind("<Button-1>", lambda e, m=mk: self._start(m))
        n = len(_load_cache(self._p.username))
        self._gl = tk.Label(outer,
                             text=f"✨ {n} AI sentences ready" if n > 0 else self._t("gen"),
                             bg=C.BG, fg=OK if n > 0 else C.TEXT_MUTED, font=F.SMALL)
        self._gl.pack(pady=(S.SM, 0))

    def _start(self, mode):
        self._mode = mode; self._idx = 0; self._done = 0; self._xp = 0
        self._lang = self._p.lang
        self._q = _build_queue(self._p, TEXTS_PER_SESSION)
        self._ml.config(text=f"[{self._t('ml') if mode=='learning' else self._t('mc')}]",
                        fg=LB if mode == "learning" else PU)
        self._load()

    def _load(self):
        self._stop_t(); self._clr(); self._dtips()
        if self._idx >= len(self._q):
            if self._p.vocab: _gen_async(self._p, count=4)
            self._ses_done(); return
        self._att = 0; self._ts = time.time(); txt = self._q[self._idx]

        outer_frame = tk.Frame(self._body, bg=C.BG)
        outer_frame.pack(fill="both", expand=True)
        scv = tk.Canvas(outer_frame, bg=C.BG, highlightthickness=0)
        sb  = tk.Scrollbar(outer_frame, orient="vertical", command=scv.yview)
        sb.pack(side="right", fill="y")
        scv.pack(side="left", fill="both", expand=True)
        scv.configure(yscrollcommand=sb.set)
        pg = tk.Frame(scv, bg=C.BG)
        wid = scv.create_window((0, 0), window=pg, anchor="nw")
        def _cfg(e=None):
            scv.configure(scrollregion=scv.bbox("all"))
            scv.itemconfig(wid, width=scv.winfo_width())
        pg.bind("<Configure>", _cfg)
        scv.bind("<Configure>", _cfg)
        def _scroll(e): scv.yview_scroll(-1*(e.delta//120), "units")
        scv.bind("<MouseWheel>", _scroll)
        pg.bind("<MouseWheel>", _scroll)

        pad = S.XL
        pr = tk.Frame(pg, bg=C.BG); pr.pack(fill="x", padx=pad, pady=(S.SM,0))
        dc = {"easy":OK,"medium":WN,"hard":NG}.get(txt.get("difficulty","medium"), WN)
        tk.Label(pr, text=self._t("prog",self._idx+1,len(self._q)), bg=C.BG,fg=C.TEXT_MUTED,font=F.SMALL).pack(side="left")
        if txt.get("_ai_generated"):
            tk.Label(pr, text=self._t("ai"), bg=C.BG, fg="#AA88FF", font=F.SMALL).pack(side="left", padx=4)
        tk.Label(pr, text=self._t("diff",txt.get("difficulty","").upper()), bg=C.BG, fg=dc, font=F.SMALL).pack(side="right")

        self._tl_lbl = None
        if self._mode == "challenge":
            self._tl = _est_time(txt, self._p); self._trem = self._tl
            tr = tk.Frame(pg, bg=C.BG); tr.pack(fill="x", padx=pad, pady=(2,0))
            self._tl_lbl = tk.Label(tr, text=self._t("tl",self._trem), bg=C.BG, fg=OK, font=(F.FAMILY,13,"bold"))
            self._tl_lbl.pack(side="right")
            self._tbo = tk.Frame(tr, bg=C.BORDER, height=5); self._tbo.pack(side="right",fill="x",expand=True,padx=(0,S.SM))
            self._tb  = tk.Frame(self._tbo, bg=OK, height=5); self._tb.place(x=0,y=0,relwidth=1.0,height=5)
            self._start_t()

        co = tk.Frame(pg, bg=GB, pady=1, padx=1); co.pack(fill="x", padx=pad, pady=(S.SM,0))
        cc = tk.Frame(co, bg=DB); cc.pack(fill="x")
        ci = tk.Frame(cc, bg=DB); ci.pack(fill="x", padx=S.LG, pady=S.LG)
        if self._mode == "learning":
            self._build_click(ci, txt, DB)
        else:
            tk.Label(ci, text=txt["chinese"], bg=DB, fg=G, font=(F.FAMILY,28,"bold"),
                     wraplength=460, justify="center").pack()

        tk.Button(pg, text=self._t("lis"), bg=C.BG_CARD, fg=C.PRIMARY, font=F.SMALL,
                  relief="flat", bd=0, cursor="hand2", activebackground=C.BG_HOVER,
                  command=lambda: play_audio(txt["chinese"])).pack(pady=(S.XS,0))

        self._pyl = tk.Label(pg, text="", bg=C.BG, fg=C.TEXT_MUTED, font=(F.FAMILY,11,"italic"))
        self._pyl.pack(pady=(S.XS,0))
        if self._mode == "learning": self._pyl.config(text=txt.get("pinyin",""))

        lang_name = "English" if self._lang == "en" else "Srpski"

        self._df = tk.Frame(pg, bg=C.BG); self._df.pack(pady=(S.XS,0))
        self._udots()

        self._fl = tk.Label(pg, text="", bg=C.BG, fg=C.TEXT, font=F.LABEL_B, wraplength=480, justify="left")
        self._fl.pack(padx=pad, pady=(S.XS,0), anchor="w")

        self._ao = tk.Frame(pg, bg=WN, pady=1, padx=1)
        self._ai_f = tk.Frame(self._ao, bg=C.BG_CARD); self._ai_f.pack(fill="x")
        self._al  = tk.Label(self._ai_f, text="", bg=C.BG_CARD, fg=C.TEXT, font=F.BODY,
                               wraplength=460, justify="left", padx=S.LG, pady=S.SM)
        self._al.pack(anchor="w")

        tk.Label(pg, text="English Translation:" if self._lang=="en" else "Prevod:",
                 bg=C.BG, fg=C.TEXT_MUTED, font=(F.FAMILY, 10, "bold")).pack(
                 anchor="w", padx=pad, pady=(S.SM, 2))

        _INPUT_BG     = "#22253d"
        _INPUT_BORDER = "#3a3d58"
        _INPUT_FOCUS  = "#4a90e2"
        ib_outer = tk.Frame(pg, bg=_INPUT_BORDER, pady=1, padx=1)
        ib_outer.pack(fill="x", padx=pad, pady=(0, S.SM))
        ib_inner = tk.Frame(ib_outer, bg=_INPUT_BG)
        ib_inner.pack(fill="x")
        self._e = tk.Text(ib_inner, height=3, font=(F.FAMILY, 12),
                          bg=_INPUT_BG, fg="#E8E8F0",
                          insertbackground="#E8E8F0", relief="flat",
                          highlightbackground=_INPUT_BORDER,
                          highlightthickness=2, wrap="word",
                          padx=14, pady=10)
        self._e.pack(fill="x")
        self._e.bind("<Control-Return>", lambda e: self._chk())
        self._e.focus_set()
        hint = self._t("hint")
        self._e.insert("1.0", hint); self._e.config(fg="#555577")
        def _fi(ev):
            if self._e.get("1.0","end-1c") == hint:
                self._e.delete("1.0","end")
                self._e.config(fg="#E8E8F0")
            ib_outer.config(bg=_INPUT_FOCUS)
            self._e.config(highlightbackground=_INPUT_FOCUS)
        def _fo(ev):
            if not self._e.get("1.0","end-1c").strip():
                self._e.insert("1.0", hint)
                self._e.config(fg="#555577")
            ib_outer.config(bg=_INPUT_BORDER)
            self._e.config(highlightbackground=_INPUT_BORDER)
        self._e.bind("<FocusIn>",  _fi)
        self._e.bind("<FocusOut>", _fo)

        br = tk.Frame(pg, bg=C.BG); br.pack(fill="x", padx=pad, pady=(S.SM, S.LG))
        self._cb = tk.Button(br, text=self._t("check"),
                             bg="#22c55e", fg="#FFFFFF",
                             font=(F.FAMILY, 11, "bold"),
                             relief="flat", bd=0, cursor="hand2",
                             padx=22, pady=8,
                             activebackground="#16a34a",
                             command=self._chk)
        self._cb.pack(side="left")
        self._sb = tk.Button(br, text=self._t("skip"),
                             bg=C.BG, fg=C.TEXT_MUTED,
                             font=(F.FAMILY, 11),
                             relief="flat", bd=0, cursor="hand2",
                             padx=18, pady=8,
                             highlightbackground=C.BORDER,
                             highlightthickness=1,
                             activebackground=C.BG_HOVER,
                             command=self._skip)
        self._sb.pack(side="left", padx=(S.SM, 0))
        self._nb = tk.Button(br, text=self._t("next"),
                             bg="#3b82f6", fg="#FFFFFF",
                             font=(F.FAMILY, 11, "bold"),
                             relief="flat", bd=0, cursor="hand2",
                             padx=22, pady=8,
                             activebackground="#2563eb",
                             command=self._nxt)
        self._nb.pack(side="right")
        self._nb.config(state="disabled")
        pg.after(150, lambda: scv.yview_moveto(0.0))

    def _build_click(self, parent, txt, bg):
        ch = txt["chinese"]; ws = txt.get("words",{})
        sk = sorted(ws.keys(), key=lambda w: -len(w))
        segs, rem = [], ch
        while rem:
            bp, bw = len(rem), None
            for w in sk:
                i = rem.find(w)
                if 0 <= i < bp: bp, bw = i, w
            if bw is None: segs.append((rem,None)); break
            if bp > 0: segs.append((rem[:bp],None))
            segs.append((bw, ws[bw])); rem = rem[bp+len(bw):]
        row = tk.Frame(parent, bg=bg); row.pack(anchor="center")
        for st, wd in segs:
            lb = tk.Label(row, text=st, bg=bg, fg=G, font=(F.FAMILY,26,"bold"),
                          cursor="hand2" if wd else "arrow",
                          padx=0, pady=0)
            lb.pack(side="left", ipadx=0)
            if wd:
                tr2 = wd.get(self._lang, st); tp = [None]; tj = [None]
                def _sh(e, lb=lb, tr=tr2, sg=st, t=tp, j=tj):
                    self._dtips()
                    tip = tk.Toplevel(self.winfo_toplevel()); tip.overrideredirect(True)
                    tip.attributes("-topmost",True); tip.configure(bg=TB,highlightbackground="#444466",highlightthickness=1)
                    tk.Label(tip,text=f"{sg}  →  {tr}",bg=TB,fg=TF,font=F.SMALL,padx=8,pady=4).pack()
                    tip.geometry(f"+{lb.winfo_rootx()}+{lb.winfo_rooty()+lb.winfo_height()+4}")
                    t[0]=tip; self._tips.append(tip)
                    def _do_play(s=sg):
                        try:
                            import pygame
                            if pygame.mixer.music.get_busy():
                                pygame.mixer.music.stop()
                        except Exception: pass
                        play_audio(s)
                    j[0]=self.after(200, _do_play)
                def _hd(e, t=tp, j=tj):
                    if t[0]:
                        try: t[0].destroy()
                        except tk.TclError: pass
                        t[0]=None
                    if j[0]:
                        try: self.after_cancel(j[0])
                        except Exception: pass
                        j[0]=None
                lb.bind("<Enter>",_sh); lb.bind("<Leave>",_hd)
            lb.bind("<Button-1>",lambda e,s=st:play_audio(s))

    def _dtips(self):
        for t in self._tips:
            try: t.destroy()
            except tk.TclError: pass
        self._tips.clear()

    def _udots(self):
        for w in self._df.winfo_children(): w.destroy()
        for i in range(MAX_ATTEMPTS):
            cv=tk.Canvas(self._df,width=12,height=12,bg=C.BG,highlightthickness=0)
            cv.create_oval(1,1,11,11,fill=NG if i<self._att else C.BORDER,outline="")
            cv.pack(side="left",padx=3)

    def _start_t(self): self._stop_t(); self._tick()
    def _stop_t(self):
        if self._tj:
            try: self.after_cancel(self._tj)
            except Exception: pass
            self._tj=None

    def _tick(self):
        if not self._tl_lbl or not self._tl_lbl.winfo_exists(): return
        try:
            self._trem=max(0,self._tl-int(time.time()-self._ts))
            pct=self._trem/max(self._tl,1)
            c=OK if pct>0.5 else WN if pct>0.25 else NG
            self._tl_lbl.config(text=self._t("tl",self._trem),fg=c)
            self._tb.config(bg=c); self._tb.place(x=0,y=0,relwidth=pct,height=5)
            if self._trem<=0: self._time_up(); return
            self._tj=self.after(1000,self._tick)
        except tk.TclError: pass

    def _time_up(self):
        self._stop_t()
        if not self._e.winfo_exists(): return
        self._fl.config(text=self._t("tu"),fg=NG)
        ans=self._q[self._idx]["answers"].get(self._lang,self._q[self._idx]["answers"]["en"])
        self._rev(ans); self._done+=1
        self._cb.config(state="disabled"); self._sb.config(state="disabled"); self._nb.config(state="normal")

    def _chk(self):
        if self._bl: return
        hint = self._t("hint"); ui = self._e.get("1.0", "end-1c").strip()
        if not ui or ui == hint:
            self._fl.config(text=hint, fg=WN); return
        txt = self._q[self._idx]
        ans = txt["answers"].get(self._lang, txt["answers"].get("en", []))
        local_res = check_translation(ui, ans, self._lang)

        if local_res["correct"] and local_res.get("score", 0) >= 95:
            self._finish_correct(local_res, txt, ans)
            return

        self._fl.config(text="🤖 Checking...", fg="#AA88FF")
        self._cb.config(state="disabled")
        chinese = txt.get("chinese", "")
        lang = self._lang

        def _ai_check():
            try:
                ai_res = gemini.check_writing_answer(chinese, ui, ans, lang)
            except Exception:
                ai_res = None
            if self.winfo_exists():
                self.after(0, lambda: self._handle_ai_result(ai_res, local_res, txt, ans))

        threading.Thread(target=_ai_check, daemon=True).start()

    def _handle_ai_result(self, ai_res, local_res, txt, ans):
        try:
            if not self.winfo_exists(): return
            self._cb.config(state="normal")

            ai_score   = ai_res.get("score", 0) if ai_res else 0
            local_ok   = local_res.get("correct", False)
            final_res  = ai_res if ai_res else local_res
            correct    = local_ok or ai_score >= 55

            if correct:
                final_res["correct"] = True
                if ai_score > 0:
                    final_res["score"] = ai_score
                if ai_score >= 90:
                    final_res["feedback"] = "Perfect! ✓" if self._lang == "en" else "Savršeno! ✓"
                elif ai_score >= 75:
                    final_res["feedback"] = "Great! Same meaning ✓" if self._lang == "en" else "Odlično! Isti smisao ✓"
                elif ai_score >= 55:
                    final_res["feedback"] = "Accepted! Close enough ✓" if self._lang == "en" else "Prihvaćeno! Dovoljno blizu ✓"
                self._finish_correct(final_res, txt, ans)
                return

            self._att += 1; self._udots()
            try:
                from ...core.sounds import play as _s; _s("wrong")
            except Exception: pass

            score      = final_res.get("score", 0)
            fb         = final_res.get("feedback", local_res.get("feedback", ""))
            suggestion = final_res.get("suggestion", "")

            if self._att >= MAX_ATTEMPTS:
                # === ZABELEŽI DA JE KORISNIK PAO (SRS reset) ===
                if txt.get("_ai_generated"):
                    _update_cache_stats(self._p.username, txt.get("id"), mistakes=self._att, score=score)
                # ===============================================
                self._stop_t()
                self._fl.config(text=fb, fg=NG)
                self._e.config(highlightbackground=NG, highlightthickness=2)
                best = suggestion if suggestion else (ans[0] if ans else "")
                if best:
                    _lbl = "Tačan prevod" if self._lang == "sr" else "Correct translation"
                    self._al.config(text=f"{_lbl}:\n{best}")
                    self._ao.pack(fill="x", padx=S.XL, before=self._fl)
                self._e.config(state="disabled")
                self._done += 1
                self._cb.config(state="disabled"); self._sb.config(state="disabled")
                self._nb.config(state="normal")
            else:
                color = WN if score >= 40 else NG
                close = (" (close!)" if self._lang=="en" else " (blizu!)") if score >= 40 else ""
                self._fl.config(text=fb + close, fg=color)
                self._e.config(highlightbackground=color, highlightthickness=2)
                if self._mode == "learning" and self._att >= 2:
                    self._pyl.config(text=txt.get("pinyin", ""), fg=WN)
        except Exception: pass

    def _finish_correct(self, res, txt, ans):
        el = time.time() - self._ts
        self._stop_t()
        self._att += 1; self._udots()
        self._fl.config(text=res.get("feedback", "✓"), fg=OK)
        self._e.config(highlightbackground=OK, highlightthickness=2)
        try:
            from ...core.sounds import play as _s
            _s("correct")
        except Exception: pass
        self._gain_xp(max(5, 20 - (self._att - 1) * 5))
        self._done += 1
        _save_time(txt.get("id", ""), el, self._p, self._db)

        # === Ažuriraj SRS statistiku, NE briši odmah ===
        if txt.get("_ai_generated"):
            _update_cache_stats(self._p.username, txt.get("id"), mistakes=max(0, self._att - 1), score=res.get("score", 100))
        # =================================================

        self._cb.config(state="disabled"); self._sb.config(state="disabled")
        if self._done >= STREAK_THRESHOLD: self._award()
        self._bl = True
        _Overlay(self.winfo_toplevel(), txt["chinese"], ans[0] if ans else "", self._auto)

    def _auto(self):
        self._bl=False; self._idx+=1; self._load()

    def _rev(self, ans, suggestion=""):
        best = suggestion if suggestion else (ans[0] if ans else "")
        self._al.config(text=self._t("cor_ans")+"\n"+best)
        self._ao.pack(fill="x",padx=S.XL,before=self._fl)
        self._e.config(state="disabled")

    def _gain_xp(self, v):
        self._xp+=v; self._p.xp+=v; self._p.daily_xp+=v
        t=date.today().isoformat(); self._p.daily_xp_history[t]=self._p.daily_xp
        if self._p.daily_xp>=self._p.daily_goal:
            if t not in self._p.completed_days: self._p.completed_days.append(t)
        self._db.save_user(self._p)

    def _award(self):
        try:
            g=self._p.award_session_streak()
            if g:
                self._n.show(self._t("sg",self._p.streak),"success")
                try:
                    from ..streak_overlay import StreakFireOverlay
                    r=self.winfo_toplevel()
                    r.after(300,lambda:StreakFireOverlay.show(r,self._p,self._lang))
                except Exception: pass
                try:
                    for a in check_achievements(self._p,event="streak"): self._n.show_achievement(a)
                except Exception: pass
            self._db.save_user(self._p)
        except Exception: pass

    def _nxt(self):
        if self._bl: return
        self._stop_t(); self._dtips(); self._idx+=1; self._load()

    def _skip(self):
        self._stop_t(); self._dtips(); self._idx+=1; self._load()

    def _ses_done(self):
        self._clr()
        if self._done>=STREAK_THRESHOLD: self._award()
        f=tk.Frame(self._body,bg=C.BG); f.pack(fill="both",expand=True,padx=S.XL,pady=S.LG)
        tk.Label(f,text="🎉",bg=C.BG,font=(F.FAMILY,52)).pack(pady=(S.LG,S.XS))
        tk.Label(f,text=self._t("done"),bg=C.BG,fg=C.TEXT,font=F.H1).pack()
        row=tk.Frame(f,bg=C.BG); row.pack(pady=S.LG)
        for lbl,val,col in [("Texts" if self._lang=="en" else "Tekstova",str(self._done),C.PRIMARY),
                             ("XP",f"+{self._xp}",G),("Streak",f"{self._p.streak} 🔥",WN)]:
            card=tk.Frame(row,bg=C.BG_CARD,highlightbackground=C.BORDER,highlightthickness=1)
            card.pack(side="left",padx=S.SM,ipadx=S.LG,ipady=S.MD)
            tk.Label(card,text=val,bg=C.BG_CARD,fg=col,font=(F.FAMILY,22,"bold")).pack()
            tk.Label(card,text=lbl,bg=C.BG_CARD,fg=C.TEXT_MUTED,font=F.TINY).pack()
        tk.Label(f,text=self._t("snote"),bg=C.BG,fg=C.TEXT_MUTED,font=F.SMALL).pack(pady=(0,S.LG))
        br=tk.Frame(f,bg=C.BG); br.pack()
        PrimaryButton(br,text=self._t("new"),command=self._restart).pack(side="left",padx=S.SM)
        GhostButton(br,text=self._t("back"),command=self._back).pack(side="left")

    def _restart(self):
        self._stop_t(); self._mode=None; self._idx=0; self._done=0; self._xp=0
        self._bl=False; self._ml.config(text=""); self._mode_sel()

    def _clr(self):
        self._dtips()
        for w in self._body.winfo_children(): w.destroy()
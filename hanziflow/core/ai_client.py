"""
core/ai_client.py — Gemini API wrapper sa rate limit zaštitom.
"""
from __future__ import annotations
import base64, hashlib, io, json, logging, os, re, time, threading, wave
from collections import OrderedDict
from typing import Optional
import requests

logger = logging.getLogger("HanziFlow.AI")


from ..config import secret

API_KEY = secret("OPENROUTER_API_KEY")
GEMINI_KEY = secret("GEMINI_API_KEY")
MODEL = "google/gemini-3-flash-preview"
OR_URL = "https://openrouter.ai/api/v1/chat/completions"
TTS_MODEL = "gemini-2.5-flash-preview-tts"
TTS_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{TTS_MODEL}:generateContent"
_SPEAK_MODEL = "gemini-2.5-flash"
BASE_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{_SPEAK_MODEL}:generateContent"

if not API_KEY:
    logger.info("OpenRouter is unconfigured; AI text features are unavailable.")


# Rate limits - OpenRouter is much more generous than Gemini free tier
_api_lock        = threading.Semaphore(3)   # 3 concurrent AI requests
_tts_lock        = threading.Semaphore(1)
_speak_lock      = threading.Semaphore(1)
_last_call_time  = 0.0
_last_tts_time   = 0.0
_last_speak_time = 0.0
_MIN_INTERVAL       = 0.5    # OpenRouter: no strict interval needed
_MIN_TTS_INTERVAL   = 1.0
_MIN_SPEAK_INTERVAL = 5.0

_req_timestamps: list  = []
_speak_timestamps: list = []
_req_lock   = threading.Lock()
_MAX_RPM         = 60   # OpenRouter allows much higher RPM
_MAX_SPEAK_RPM   = 10

def _wait_for_rpm_slot(speaking: bool = False):
    """Blokira dok nema slobodnog slota u RPM limitu."""
    timestamps = _speak_timestamps if speaking else _req_timestamps
    max_rpm    = _MAX_SPEAK_RPM  if speaking else _MAX_RPM
    while True:
        with _req_lock:
            now = time.time()
            cutoff = now - 60.0
            while timestamps and timestamps[0] < cutoff:
                timestamps.pop(0)
            if len(timestamps) < max_rpm:
                timestamps.append(now)
                return
            wait_until = timestamps[0] + 61.0
        wait_sec = max(0.5, wait_until - time.time())
        kind = "speaking" if speaking else "API"
        logger.debug(f"RPM limit {kind} ({len(timestamps)}/min): čekam {wait_sec:.1f}s")
        time.sleep(min(wait_sec, 5.0))


class GeminiClient:

    _MAX_CACHE = 300   # max broj keširanih odgovora (LRU eviction)

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})
        self._cache: "OrderedDict[str, str]" = OrderedDict()

    def _cache_key(self, payload: dict) -> str:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(raw.encode()).hexdigest()

    def _cache_get(self, key: str) -> "Optional[str]":
        if key not in self._cache:
            return None
        # LRU: pomjeri na kraj (najskorije korišten)
        self._cache.move_to_end(key)
        return self._cache[key]

    def _cache_set(self, key: str, value: str) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self._MAX_CACHE:
            self._cache.popitem(last=False)  # izbaci najstariji (LRU)

    def _convert_to_openrouter_content(self, payload: dict) -> str | list:
        """Converts Gemini-format payload to OpenRouter content format (including images)."""
        try:
            parts = payload["contents"][0]["parts"]
            or_content = []
            has_image = False

            for p in parts:
                if "text" in p:
                    or_content.append({
                        "type": "text",
                        "text": p["text"]
                    })
                elif "inline_data" in p or "inlineData" in p:
                    has_image = True
                    key = "inline_data" if "inline_data" in p else "inlineData"
                    mime = p[key].get("mime_type", "image/png")
                    b64_data = p[key].get("data", "")

                    # OpenRouter / OpenAI Vision format
                    or_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime};base64,{b64_data}"
                        }
                    })

            # Ako nema slike, vrati samo običan string (bolja kompatibilnost za non-vision modele)
            if not has_image:
                return " ".join(item["text"] for item in or_content if item["type"] == "text")

            return or_content
        except Exception as e:
            logger.error("Payload conversion failed (%s)", type(e).__name__)
            return str(payload)

    def _post_openrouter(self, content: str | list, timeout: int = 25,
                         system: str = "") -> Optional[str]:
        """Send content (text or vision array) to OpenRouter, return response text."""

        # 1. Provera ključa pre slanja
        if not API_KEY or not API_KEY.startswith("sk-or-v1-"):
            logger.error(f"KRITIČNO: Ključ '{API_KEY[:10]}...' nije validan OpenRouter format!")
            return None

        global _last_call_time
        messages = []
        if system:
            messages.append({"role": "system", "content": system})

        messages.append({"role": "user", "content": content})

        or_payload = {
            "model":       MODEL,
            "messages":     messages,
            "temperature": 0.2,
            "max_tokens":  1000,
        }

        with _api_lock:
            _wait_for_rpm_slot()
            elapsed = time.time() - _last_call_time
            if elapsed < _MIN_INTERVAL:
                time.sleep(_MIN_INTERVAL - elapsed)

            for attempt in range(1, 3):
                try:
                    _last_call_time = time.time()
                    r = self._session.post(
                        OR_URL,
                        json=or_payload,
                        headers={
                            "Content-Type":  "application/json",
                            "Authorization": f"Bearer {API_KEY}",
                            "HTTP-Referer":  "https://hanziflow.app",
                            "X-Title":       "HanziFlow",
                        },
                        timeout=timeout
                    )
                    if r.status_code == 200:
                        data = r.json()
                        text = data["choices"][0]["message"]["content"]
                        return text.strip()
                    if r.status_code == 429:
                        with _req_lock:
                            if _req_timestamps: _req_timestamps.pop()
                        if attempt == 1:
                            logger.warning("OpenRouter rate limit. Waiting 10s...")
                            time.sleep(10)
                            continue
                        return None
                    if r.status_code in (500, 502, 503):
                        time.sleep(3)
                        continue
                    logger.error("OpenRouter HTTP %s", r.status_code)
                    return None
                except requests.exceptions.Timeout:
                    logger.warning(f"OpenRouter timeout (attempt {attempt})")
                    if attempt < 2: time.sleep(2)
                except requests.exceptions.ConnectionError as e:
                    logger.warning("OpenRouter connection failed (%s)", type(e).__name__)
                    return None
                except Exception as e:
                    logger.error("OpenRouter request failed (%s)", type(e).__name__)
                    return None
        return None

    def call(self, payload: dict, timeout: int = 25, cache: bool = False) -> Optional[str]:
        """Main call method - converts Gemini payload format to OpenRouter."""
        if cache:
            k = self._cache_key(payload)
            cached = self._cache_get(k)
            if cached is not None:
                return cached

        # Ekstraktujemo tekst i slike u OpenRouter format
        content = self._convert_to_openrouter_content(payload)

        gen_config = payload.get("generationConfig", {})
        text = self._post_openrouter(content, timeout=timeout)
        if text is None:
            return None
        text = text.replace("```json", "").replace("```", "").strip()
        if cache:
            self._cache_set(self._cache_key(payload), text)
        return text

    # ISPRAVKA: Implementiran Regex fallback ako AI ne vrati čist JSON
    def call_json(self, payload: dict, timeout: int = 25, cache: bool = False) -> Optional[dict | list]:
        text = self.call(payload, timeout=timeout, cache=cache)
        if text is None:
            return None

        import re
        clean_text = text.strip()

        try:
            # Pokušaj 1: Idealan slučaj
            return json.loads(clean_text)
        except json.JSONDecodeError:
            # Pokušaj 2: AI je zaboravio [ ] oko niza objekata (ovo rešava "Extra data" grešku)
            if clean_text.startswith("{") and clean_text.endswith("}"):
                try:
                    return json.loads(f"[{clean_text}]")
                except json.JSONDecodeError:
                    pass

            # Pokušaj 3: Tražimo [ ... ] negde unutar teksta
            m_array = re.search(r'\[.*\]', clean_text, re.DOTALL)
            if m_array:
                try:
                    return json.loads(m_array.group(0))
                except json.JSONDecodeError:
                    pass

            # Pokušaj 4: Tražimo { ... } i nasilno ih pakujemo u niz
            m_obj = re.search(r'\{.*\}', clean_text, re.DOTALL)
            if m_obj:
                extracted = m_obj.group(0)
                try:
                    return json.loads(extracted)
                except json.JSONDecodeError:
                    try:
                        # Ako padne, to znači da ih ima više odvojenih zarezom. Pakujemo ih u niz!
                        return json.loads(f"[{extracted}]")
                    except Exception as e:
                        logger.error("AI JSON parsing failed (%s)", type(e).__name__)

            logger.error("AI returned invalid JSON.")
            return None

    def tts(self, text: str, lang: str = "zh") -> Optional[bytes]:
        global _last_tts_time

        if lang == "en":
            voice = "Aoede"
        else:
            voice = "Kore"

        payload = {
            "contents": [{
                "parts": [{
                    "text": (
                        f"Say naturally in English: {text}"
                        if lang == "en" else text
                    )
                }]
            }],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {"voiceName": voice}
                    }
                }
            }
        }
        if not GEMINI_KEY:
            return None
        url = TTS_URL
        with _tts_lock:
            elapsed = time.time() - _last_tts_time
            if elapsed < _MIN_TTS_INTERVAL:
                time.sleep(_MIN_TTS_INTERVAL - elapsed)
            _last_tts_time = time.time()
            try:
                r = self._session.post(url, json=payload, headers={"x-goog-api-key": GEMINI_KEY}, timeout=12)
            except Exception as e:
                logger.debug("TTS request failed (%s)", type(e).__name__)
                return None
        if r.status_code == 429:
            logger.debug("TTS 429 — gTTS will handle it")
            return None
        if r.status_code != 200:
            return None
        try:
            resp  = r.json()
            parts = resp["candidates"][0]["content"]["parts"]
            for part in parts:
                key = ("inlineData" if "inlineData" in part
                       else "inline_data" if "inline_data" in part else None)
                if key:
                    pcm = base64.b64decode(part[key]["data"])
                    buf = io.BytesIO()
                    with wave.open(buf, "wb") as wf:
                        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(24000)
                        wf.writeframes(pcm)
                    return buf.getvalue()
            logger.debug(f"TTS: no audio in parts")
            return None
        except Exception as e:
            logger.debug(f"TTS parse error: {e}")
            return None

    # ISPRAVKA: Pooštren prompt da AI ne bi dodavao konverzacijski tekst
    def extract_words(self, text: str = "", image_bytes: bytes = None,
                      mime: str = "image/png") -> Optional[list[dict]]:
        prompt = (
            "You are a strict data extractor. DO NOT output any conversational text, greetings, or explanations. "
            "Extract Chinese words. Return STRICTLY a JSON array. "
            "Keys: 'hanzi', 'pinyin', 'meaning_sr' (Serbian), 'meaning_en' (English), 'xp' (10-50). "
            "Example: [{\"hanzi\":\"你好\",\"pinyin\":\"nǐ hǎo\","
            "\"meaning_sr\":\"zdravo\",\"meaning_en\":\"hello\",\"xp\":10}]"
        )
        parts: list[dict] = [{"text": prompt}]
        if image_bytes:
            parts.append({"inline_data": {"mime_type": mime,
                                          "data": base64.b64encode(image_bytes).decode()}})
        if text:
            parts.append({"text": text})
        result = self.call_json({"contents": [{"parts": parts}]}, timeout=30)
        return result if isinstance(result, list) else None

    def translate_meaning(self, meaning: str) -> tuple[str, str]:
        prompt = (
            f"Meaning of a Chinese word: '{meaning}'. "
            "Detect language. Return STRICTLY JSON: "
            "{\"meaning_sr\": \"Serbian translation\", \"meaning_en\": \"English translation\"}"
        )
        data = self.call_json(
            {"contents": [{"parts": [{"text": prompt}]}],
             "generationConfig": {"temperature": 0.2}},
            cache=True)
        if isinstance(data, dict):
            return data.get("meaning_sr", meaning), data.get("meaning_en", meaning)
        return meaning, meaning

    def evaluate_drawing(self, png_bytes: bytes, hanzi: str,
                         pinyin: str, meaning: str) -> Optional[dict]:
        prompt = (
            f"Expert in Chinese characters. User tried to draw '{hanzi}' "
            f"(pinyin: {pinyin}, meaning: {meaning}). "
            "Evaluate. Return STRICTLY JSON: "
            "{\"correct\": true/false, \"score\": 0-100, \"feedback\": \"short message\"}"
        )
        return self.call_json({"contents": [{"parts": [
            {"text": prompt},
            {"inline_data": {"mime_type": "image/png",
                             "data": base64.b64encode(png_bytes).decode()}}
        ]}]}, timeout=20)

    def evaluate_speaking(self, wav_bytes: bytes, hanzi: str, pinyin: str) -> Optional[dict]:
        """Evaluira govor — sopstveni lock, ne blokira ostale AI pozive."""
        global _last_speak_time

        if not wav_bytes or len(wav_bytes) < 2000:
            logger.debug("Speaking: audio prekratak, preskačem")
            return None

        # Ograniči veličinu audio fajla — max 500KB (oko 15s)
        max_size = 500 * 1024
        if len(wav_bytes) > max_size:
            wav_bytes = wav_bytes[:max_size]
            logger.debug(f"Speaking: audio skraćen na {max_size} bytes")

        prompt = (
            f"You are a strict Chinese pronunciation evaluator.\n"
            f"The student is supposed to say: '{hanzi}' (pinyin: {pinyin}).\n"
            f"Listen to the audio VERY carefully.\n\n"
            f"CRITICAL RULES:\n"
            f"1. If the audio contains silence, noise, or words in a completely different language "
            f"(e.g. English, Serbian, etc.) — score MUST be 0, correct MUST be false.\n"
            f"2. If you hear something that does NOT sound like Chinese at all — score MUST be 0.\n"
            f"3. If you hear Chinese but it clearly does NOT match '{pinyin}' — score must be below 30.\n"
            f"4. Only give a high score (70+) if the audio clearly contains a good attempt at '{pinyin}'.\n"
            f"5. 'heard' field must contain what you ACTUALLY heard, even if it's English or noise.\n\n"
            f"Return STRICTLY valid JSON only, no markdown:\n"
            f"{{\"correct\": true/false, \"score\": 0-100, "
            f"\"feedback\": \"one sentence\", \"heard\": \"exactly what you heard\"}}"
        )
        payload = {"contents": [{"parts": [
            {"text": prompt},
            {"inline_data": {"mime_type": "audio/wav",
                             "data": base64.b64encode(wav_bytes).decode()}}
        ]}]}

        with _speak_lock:
            elapsed = time.time() - _last_speak_time
            if elapsed < _MIN_SPEAK_INTERVAL:
                wait = _MIN_SPEAK_INTERVAL - elapsed
                logger.debug(f"Speaking: čekam {wait:.1f}s na interval")
                time.sleep(wait)
            # Provjeri speaking-specifični RPM slot
            _wait_for_rpm_slot(speaking=True)
            _last_speak_time = time.time()
            if not GEMINI_KEY:
                return None
            url = BASE_URL
            try:
                r = self._session.post(url, json=payload, headers={"x-goog-api-key": GEMINI_KEY}, timeout=35)
            except Exception as e:
                logger.warning("Speaking request failed (%s)", type(e).__name__)
                return None

        if r.status_code == 429:
            logger.warning("Speaking 429 — preskačem ovu evaluaciju")
            return None
        if r.status_code != 200:
            logger.warning(f"Speaking HTTP {r.status_code}")
            return None
        try:
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            text = text.replace("```json", "").replace("```", "").strip()
            import json as _json
            result = _json.loads(text)

            # Sigurnosna provjera: ako "heard" nema nikakve sličnosti sa ciljem,
            # forcuj score na 0 — Gemini ponekad halucinira da je čuo tačnu reč.
            #
            # VAŽNO: Gemini može vratiti "heard" kao hanzi (npr. "现在") ILI kao pinyin
            # (npr. "xianzai"). Oba slučaja moraju biti prihvaćena kao tačna.
            heard_raw = (result.get("heard") or "").strip()
            heard_lower = heard_raw.lower().replace(" ", "")

            def _strip_tones(s: str) -> str:
                return s.replace("ā","a").replace("á","a").replace("ǎ","a").replace("à","a") \
                    .replace("ē","e").replace("é","e").replace("ě","e").replace("è","e") \
                    .replace("ī","i").replace("í","i").replace("ǐ","i").replace("ì","i") \
                    .replace("ō","o").replace("ó","o").replace("ǒ","o").replace("ò","o") \
                    .replace("ū","u").replace("ú","u").replace("ǔ","u").replace("ù","u") \
                    .replace("ǖ","v").replace("ǘ","v").replace("ǚ","v").replace("ǜ","v")

            target_pinyin = _strip_tones(pinyin.lower().replace(" ", ""))
            heard_pinyin  = _strip_tones(heard_lower)

            # 1. Direktno poklapanje hanzi — ako heard sadrži bilo koji karakter
            #    iz ciljnog hanzi stringa, to je validan odgovor
            hanzi_chars_matched = any(ch in heard_raw for ch in hanzi if ch.strip())

            # 2. Poklapanje pinyin karaktera (bez tonova)
            common = sum(1 for c in target_pinyin if c in heard_pinyin)
            overlap_ratio = common / max(len(target_pinyin), 1)

            is_valid = hanzi_chars_matched or overlap_ratio >= 0.3

            if not is_valid and result.get("score", 0) > 20:
                logger.warning("Speaking response did not match the target; score reset.")
                result["score"] = 0
                result["correct"] = False
                result["feedback"] = "What was heard does not match the target word. Please try again."

            return result
        except Exception as e:
            logger.warning(f"Speaking parse error: {e}")
            return None


    def generate_writing_sentence(self, vocab_words: list, weak_hanzi: list, lang: str = "en") -> Optional[dict]:
        """Generate a writing exercise sentence from user vocab. Returns None on failure."""
        if not vocab_words:
            return None
        word_info = []
        for w in vocab_words[:25]:
            hanzi  = w.get("hanzi", "")
            en     = w.get("meaning_en", "")
            pinyin = w.get("pinyin", "")
            tag    = "[WEAK]" if hanzi in weak_hanzi else ""
            word_info.append(f"{tag}{hanzi}({pinyin})={en}")
        words_str = ", ".join(word_info)

        prompt = (
            "You are a strict JSON data generator. DO NOT output conversational text or markdown formatting like ```json. "
            "You are a Chinese teacher creating a personalized writing exercise. "
            f"Student vocabulary: {words_str}. "
            "Words marked [WEAK] MUST be included. "
            "Create ONE grammatically correct natural Chinese sentence using ONLY words from this list. "
            "Respond ONLY with this JSON:\n"
            '{"chinese":"sentence","pinyin":"full pinyin","answer_en":"English translation",'
            '"answer_sr":"Serbian translation",'
            '"words_used":[{"hanzi":"word","en":"meaning","sr":"meaning"}],"difficulty":"medium","focus":["weak1"]}'
        )

        # NOVO: Koristimo bezbedni call_json umesto ručnog parsiranja!
        data = self.call_json(
            {"contents": [{"parts": [{"text": prompt}]}],
             "generationConfig": {"temperature": 0.7, "maxOutputTokens": 350}},
            timeout=25, cache=False)

        if not data or not isinstance(data, dict):
            return None

        chinese = data.get("chinese", "").replace(" ", "")
        if not chinese:
            return None

        def _exp(meaning):
            parts = [p.strip() for p in str(meaning).split(";")]
            result = []
            for p in parts:
                result.extend([p, p.lower()])
                if p.lower().startswith("to "): result.extend([p[3:], p[3:].lower()])
            result.extend([meaning, str(meaning).lower()])
            return list(dict.fromkeys(result))

        words_dict = {}
        for w in data.get("words_used", []):
            h = w.get("hanzi", "")
            if h and h in chinese:
                words_dict[h] = {"en": w.get("en", ""), "sr": w.get("sr", "")}

        return {
            "id":            f"ai_{hashlib.md5(chinese.encode()).hexdigest()[:8]}",
            "chinese":       chinese,
            "pinyin":        data.get("pinyin", ""),
            "answers":       {"en": _exp(data.get("answer_en", "")),
                              "sr": _exp(data.get("answer_sr", ""))},
            "words":         words_dict,
            "difficulty":    data.get("difficulty", "medium"),
            "focus":         data.get("focus", []),
            "_ai_generated": True,
        }

    def generate_sentence(self, known_words: list[str], performance: str,
                          lang: str = "en") -> Optional[dict]:
        words_str = ", ".join(known_words[:30])
        prompt = (
            f"You are a Chinese teacher. The student knows these words: {words_str}. "
            f"{performance} "
            "Create ONE simple Chinese sentence using words the student knows. "
            "Respond with EXACTLY these 5 lines, no extra text, no markdown:\n"
            "RECENICA: [sentence in hanzi]\n"
            "IZMESANO: [same hanzi words comma-separated, shuffled order]\n"
            "ZNACENJE_SR: [Serbian translation]\n"
            "ZNACENJE_EN: [English translation]\n"
            "XP: [number 10-40]\n"
        )
        text = self.call({"contents": [{"parts": [{"text": prompt}]}],
                          "generationConfig": {"temperature": 0.3}}, timeout=25)
        if not text:
            logger.error("generate_sentence: API returned None")
            return None

        logger.debug("Sentence response received.")

        result: dict = {}
        clean = re.sub(r'[*_`#]', '', text)

        for line in clean.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            for key, prefix in [
                ("correct",    "RECENICA"),
                ("scrambled",  "IZMESANO"),
                ("meaning_sr", "ZNACENJE_SR"),
                ("meaning_en", "ZNACENJE_EN"),
                ("xp",         "XP"),
            ]:
                m = re.match(rf'^{prefix}\s*:\s*(.+)$', line, re.IGNORECASE)
                if m:
                    val = m.group(1).strip()
                    if key == "xp":
                        nums = re.findall(r'\d+', val)
                        result[key] = int(nums[0]) if nums else 30
                    else:
                        result[key] = val
                    break

        if "correct" in result and "scrambled" in result:
            result["correct"] = result["correct"].replace(" ", "")
            result.setdefault("meaning_sr", "")
            result.setdefault("meaning_en", "")
            result.setdefault("xp", 30)
            return result

        logger.warning("Sentence response parsing failed.")
        return None

    def ai_coach(self, goal: int, history: dict[str, int],
                 performance_summary: str = "") -> Optional[dict]:
        # Cache po danu — ne pozivaj Gemini više od jednom dnevno za isti cilj
        import datetime as _dt
        today = _dt.date.today().isoformat()
        cache_key = f"ai_coach:{today}:{goal}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            logger.debug("ai_coach: vraćam cached odgovor")
            try:
                return json.loads(cached)
            except Exception:
                pass

        hist_str = ", ".join(f"{k}: {v}XP" for k, v in sorted(history.items()))
        prompt = (
            f"AI language coach. Daily goal: {goal} XP. "
            f"Learning history: {hist_str}. {performance_summary} "
            "Analyze and suggest goal change. Return STRICTLY JSON: "
            "{\"action\": \"increase|decrease|keep\", \"suggested_goal\": number, "
            "\"message\": \"short encouraging message in English\"}"
        )
        result = self.call_json({"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
        if result:
            self._cache_set(cache_key, json.dumps(result))
        return result

    def arena_commentator(self, score: int, combo: int, correct: int,
                          total: int, time_left: int, lang: str = "en") -> Optional[str]:
        """
        AI komentator za Word Arena — brzi komentar na osnovu performansi.
        Koristimo cache agresivno da izbjegnemo API pozive.
        """
        # Bucketing — svrstavamo u kategorije da koristimo cache
        acc    = round((correct / max(total, 1)) * 100 / 20) * 20  # 0,20,40,60,80,100
        combo_bucket = min(combo // 3, 5)  # 0,1,2,3,4,5+
        score_bucket = min(score // 100, 10)
        time_bucket  = "low" if time_left < 15 else "mid" if time_left < 35 else "high"

        lang_instr = "in Serbian, short (max 12 words)" if lang == "sr" else "in English, short (max 12 words)"
        prompt = (
            f"You are an exciting sports commentator for a Chinese word game. "
            f"Player stats: score={score_bucket*100}+, combo={combo_bucket*3}+, "
            f"accuracy={acc}%, time_left={time_bucket}. "
            f"Give ONE short exciting comment {lang_instr}. "
            "Be dynamic, encouraging or dramatic depending on performance. No emojis."
        )
        return self.call(
            {"contents": [{"parts": [{"text": prompt}]}],
             "generationConfig": {"temperature": 0.9, "maxOutputTokens": 60}},
            timeout=8, cache=True)  # cache=True — isti bucket = isti odgovor

    def session_feedback(self, stats_summary: str, weak_words: list[str],
                         lang: str = "en") -> Optional[str]:
        lang_instr = "in Serbian" if lang == "sr" else "in English"
        prompt = (
            "You are a Chinese language tutor giving brief feedback after a practice session. "
            f"Session stats: {stats_summary}. "
            f"Words the student struggles with: {', '.join(weak_words[:5]) if weak_words else 'none'}. "
            f"Give 2-3 sentences of encouraging, specific feedback {lang_instr}. "
            "Be direct and helpful, like a real teacher."
        )
        return self.call({"contents": [{"parts": [{"text": prompt}]}],
                          "generationConfig": {"temperature": 0.7}}, timeout=15)



    def generate_personal_achievements(self, profile) -> list[dict]:
        """
        Generiše personalizovane hidden achievements na osnovu korisnikovog profila.
        Poziva se async iz achievements.py — ne blokira UI.
        """
        import json as _json
        try:
            stats = {
                "level": getattr(profile, "level", 1),
                "streak": getattr(profile, "streak", 0),
                "vocab_size": len(getattr(profile, "vocab", [])),
                "total_correct": getattr(profile, "total_correct", 0),
                "total_answered": getattr(profile, "total_answered", 0),
                "grammar_completed": getattr(profile, "grammar_completed", 0),
                "arena_score": getattr(profile, "arena_score", 0),
                "completed_days": len(getattr(profile, "completed_days", [])),
            }
            vocab = getattr(profile, "vocab", [])
            weak = sorted(
                [w for w in vocab if w.get("total_seen", 0) > 0],
                key=lambda w: w.get("total_correct", 0) / max(w.get("total_seen", 1), 1)
            )[:5]
            weak_hanzi = [w.get("hanzi", "") for w in weak]
            prompt = (
                "You are a gamification expert for a Chinese language learning app. "
                f"Generate 2-3 personalized hidden achievements for this learner: "
                f"{_json.dumps(stats)}. Weakest words: {weak_hanzi}. "
                "Return ONLY a JSON array (no markdown): "
                '[{"id":"gemini_unique","name":"Name","desc":"Cryptic hint","icon":"emoji","xp":50}]. '
                "IDs must start with gemini_. XP 30-150. Single emoji icons."
            )
            raw = self.call(
                {"contents": [{"parts": [{"text": prompt}]}],
                 "generationConfig": {"temperature": 0.9, "maxOutputTokens": 400}},
                timeout=20, cache=False)
            if not raw:
                return []
            clean = raw.strip().replace("```json", "").replace("```", "").strip()
            data  = _json.loads(clean)
            if isinstance(data, list):
                return [a for a in data if isinstance(a, dict) and "id" in a and str(a.get("id","")).startswith("gemini_")]
        except Exception as e:
            import logging
            logging.getLogger("HanziFlow.Gemini").debug(f"generate_personal_achievements: {e}")
        return []


    def check_writing_answer(self, chinese: str, user_answer: str,
                             reference_answers: list, lang: str = "en") -> dict:
        """
        AI provjerava prevod rečenice. Prihvata parafrazirane/sinonimne odgovore.
        Vraća: {"correct": bool, "score": 0-100, "feedback": str, "suggestion": str}
        """
        import json as _json
        ref_str = " | ".join(reference_answers[:4]) if reference_answers else ""
        lang_name = "Serbian" if lang == "sr" else "English"
        respond_lang = "in Serbian" if lang == "sr" else "in English"
        parts = [
            "You are a lenient Chinese language teacher checking a student's translation.",
            f"Chinese sentence: {chinese}",
            f"Reference translations: {ref_str}",
            f"Student's answer: {user_answer}",
            "",
            "SCORING RULES - be generous with synonyms and paraphrases:",
            "- score 90-100: Perfect or near-perfect match",
            "- score 75-89: Same meaning, different words (e.g. 'like'='enjoy'='love', 'chat'='talk'='converse')",
            "- score 60-74: Mostly correct, minor omissions or style differences",
            "- score 40-59: Partially correct, some key meaning preserved",
            "- score 0-39: Wrong meaning or major errors",
            "",
            "ALWAYS ACCEPT (score >= 75):",
            "- Synonyms: like/love/enjoy, chat/talk/converse, eat/have a meal, family/relatives",
            "- Different tense if meaning same: 'I like to eat' = 'I love eating'",
            "- Dropped articles or minor grammar if meaning is clear",
            "- Different word order if meaning preserved",
            "",
            "REJECT (score < 40): Wrong subject, wrong action, missing core meaning",
            "",
            f"Respond ONLY with valid JSON, feedback {respond_lang}:",
            '{"correct": true/false, "score": 0-100, "feedback": "one short sentence", "suggestion": "better translation if score<60, else empty string"}',
        ]
        prompt = "\n".join(parts)
        try:
            raw = self.call(
                {"contents": [{"parts": [{"text": prompt}]}],
                 "generationConfig": {"temperature": 0.2, "maxOutputTokens": 200}},
                timeout=12, cache=False)
            if not raw:
                return {"correct": False, "score": 0, "feedback": "AI unavailable", "suggestion": ""}
            clean = raw.strip().replace("```json", "").replace("```", "").strip()
            data  = _json.loads(clean)
            return {
                "correct":    bool(data.get("correct", False)),
                "score":      int(data.get("score", 0)),
                "feedback":   str(data.get("feedback", "")),
                "suggestion": str(data.get("suggestion", "")),
            }
        except Exception as e:
            import logging
            logging.getLogger("HanziFlow.Gemini").debug(f"check_writing_answer: {e}")
            return {"correct": False, "score": 0, "feedback": "AI check failed", "suggestion": ""}

gemini = GeminiClient()
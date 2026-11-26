import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone, timedelta

import requests

ANGLES = [
    "One-Shot / Kebiasaan Harian: buka dengan hook kredibel 'Tips [tujuan] dari yang pernah...' + 'Gue nggak pakai cara aneh. Cuma X kebiasaan ini...' + urgensi mulai sekarang.",
    "Pola Simpel Anti-Ribet: buka dengan hook 'Cara [tujuan] tanpa ribet...' + patahkan mitos harus belajar/kerja keras tanpa arah + X langkah simpel tiap hari.",
    "Ubah Nilai/Hasil yang Mentok: buka dengan hook 'Yang bikin hasil gue/orang naik dari mentok jadi tembus...' + X perubahan kecil yang dijalanin konsisten.",
    "Trik Hemat Waktu: buka dengan hook 'Jangan buang waktu lagi, cukup X trik ini buat...' + cerita kenapa trik kecil lebih ngaruh daripada teori numpuk.",
    "Persiapan dari Nol: buka dengan hook 'Kalau mulai dari nol buat [tujuan], gue bakal lakuin X hal ini dulu...' + langkah harian yang realistis dijalani.",
    "Pengalaman Pribadi + Sistem Rapi: buka dengan hook 'Dulu gue juga keteteran, sampai akhirnya nemu X cara ini...' + sistem harian yang bikin progres kerasa.",
]

THREADS_API_BASE = "https://graph.threads.net/v1.0"
MAX_THREADS_CHARS = 500


def get_env(name: str, default: str = "", required: bool = False) -> str:
    val = os.getenv(name, default).strip()
    if required and not val:
        raise RuntimeError(f"Environment variable '{name}' wajib diisi.")
    return val


def fetch_products(webhook_url: str, secret: str) -> list[dict]:
    resp = requests.get(webhook_url, params={"key": secret}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Gagal membaca Google Sheet: {data}")
    items = data.get("items", [])
    active = [
        item for item in items
        if str(item.get("Aktif", "")).strip().upper() in {"YA", "YES", "TRUE", "1"}
        and str(item.get("Produk", "")).strip()
        and str(item.get("Link_Produk", "")).strip()
    ]
    if not active:
        raise RuntimeError("Tidak ada produk aktif (Aktif=YA) yang punya Produk & Link_Produk.")
    return active


def pick_product(products: list[dict]) -> dict:
    def post_count(item: dict) -> int:
        try:
            return int(item.get("Total_Post") or 0)
        except (TypeError, ValueError):
            return 0

    min_count = min(post_count(p) for p in products)
    candidates = [p for p in products if post_count(p) == min_count]
    return random.choice(candidates)


def pick_angle(last_angle: str) -> str:
    last_clean = (last_angle or "").strip()
    available = [a for a in ANGLES if a.split(":")[0] != last_clean.split(":")[0]]
    return random.choice(available or ANGLES)


def extract_json_object(raw_text: str) -> dict:
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def trim_post(text: str, limit: int = MAX_THREADS_CHARS) -> str:
    text = text.replace("\ufffc", "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def extract_links(raw_links: str) -> list[str]:
    urls = re.findall(r"https?://[^\s,]+", raw_links)
    if urls:
        return urls
    cleaned = raw_links.strip()
    return [cleaned] if cleaned else []


def ensure_links_in_post(post_text: str, links: list[str]) -> str:
    missing = [u for u in links if u not in post_text]
    if not missing:
        return trim_post(post_text)
    links_block = "\n".join(missing)
    max_body = MAX_THREADS_CHARS - len(links_block) - 2
    if max_body <= 20:
        return trim_post(links_block)
    return trim_post(post_text, max_body) + f"\n\n{links_block}"


def sanitize_topic_tag(raw_tag: str, max_words: int = 2) -> str:
    tag = (raw_tag or "").strip().lstrip("#")
    tag = tag.replace("&", " ").replace(".", "")
    words = re.sub(r"\s+", " ", tag).strip().split()
    if max_words > 0:
        words = words[:max_words]
    tag = " ".join(words)
    if len(tag) > 50:
        tag = tag[:50].strip()
    return tag


def generate_thread_posts(
    gemini_api_key: str,
    gemini_model: str,
    product: dict,
    angle: str,
) -> tuple[list[str], str]:
    produk = str(product.get("Produk", "")).strip()
    keunggulan = str(product.get("Keunggulan", "")).strip()
    kekurangan = str(product.get("Kekurangan", "")).strip()
    niche = str(product.get("Niche", "") or product.get("Topik", "")).strip()
    manual_topic = sanitize_topic_tag(str(product.get("Topic", "") or product.get("Topic_Tag", "")))
    current_year = datetime.now(timezone(timedelta(hours=7))).year
    raw_link = str(product.get("Link_Produk", "")).strip()
    links = extract_links(raw_link)
    links_display = "\n".join(links) if links else raw_link

    extra_info = ""
    if niche:
        extra_info += f"- Topik / Niche: {niche}\n"
    if kekurangan:
        extra_info += f"- Kekurangan / Catatan Jujur: {kekurangan}\n"

    prompt = f"""Kamu adalah kreator Threads Indonesia yang gaya penulisannya santai, jujur, padat, membumi, pakai sapaan "gue" dan "lo" (bukan bahasa iklan kaku, bukan gaya motivator klise), dan selalu memberi value/tips berguna dulu sebelum menyebut produk.

CONTOH GAYA, EMOJI, SPASI BARIS, & ALUR UTAS YANG DIINGINKAN (ikuti persis ritme paragraf pendek dengan baris kosong, kekuatan hook, dan penempatan emoji seperti ini, tapi sesuaikan topiknya dengan produk di bawah):
- Utas 1 (Hook kuat — WAJIB 3 paragraf pendek dipisah baris kosong):
  Tips lolos CPNS dari yang pernah one shot 🙏

  Gue nggak belajar pakai cara aneh. Cuma 6 kebiasaan ini, dijalanin tiap hari sampai hari H.

  CPNS 2026 dibuka November, jadi mulai dari sekarang.
- Utas 2 (Relatable check + 3 bullet "•" berupa kondisi nyata, bukan pertanyaan):
  Lo sekarang lagi di fase mana? 🤔

  • Niat belajar, tapi gampang kegoda main
  • Udah baca banyak materi, tapi lupa lagi
  • Udah latihan soal, tapi nilainya mentok

  Kalau salah satunya, 6 tips ini buat lo 👇
- Utas 3 (Tip/Value 1 + 1 emoji relevan + baris kosong):
  📌 Tip 1: Kurangin keluar main.
  Bukan berarti nggak boleh sama sekali. Sesekali boleh, tapi kalau nggak penting, tahan dulu.

  Waktu belajar lo sempit, jadi jaga baik-baik.
- Utas 4 (Tip/Value 2-3 + 1 emoji relevan + baris kosong):
  ✍️ Tip 2 & 3: Rangkum pakai tulisan tangan.
  Baca dari buku, ebook, atau YouTube, lalu rangkum di satu buku khusus.

  Pakai bahasa semudah mungkin supaya gampang diingat. Kalau bahasanya masih ribet, berarti lo belum paham.
- Utas 5 (Tip/Value 4-5 + 1 emoji relevan + baris kosong):
  ⚡ Tip 4 & 5: Latihan soal dan materi baru tiap hari.
  Banyakin latihan soal. Setiap soal baru yang lo tahu, wajib dicatat di buku tadi.

  Tiap hari juga harus ada minimal 1 materi baru yang belum pernah lo pelajari.
- Utas 6 (Kenalkan produk + emoji ikon produk + alasan pakai + kekurangan jujur):
  Soal sumber belajar, gue dulu cuma pakai 2 buku:

  📘 [SANG TUTOR] untuk TIU
  📗 [AL FAIZ] untuk all rounded

  Alasannya: kita nggak butuh teori ribet, cuma butuh trik kecil buat dapat waktu pengerjaan tercepat.
  Kekurangannya: tetap harus luangin waktu buat paham konsep dasarnya.
- Utas 7 (Link produk + soft CTA tanpa memaksa):
  Ini link bukunya 👇
  https://example.com/produk

  Kalau udah punya yang serupa, pakai aja. Yang penting mulai sekarang, bukan nunggu nanti.
- Utas 8 (Closing interaksi + penyemangat + emoji, TANPA link):
  Kalau ada yang mau ditanyain soal cara atur jadwal atau latihan soal, tanya di komen. Gue jawab satu-satu.

  Semangat, semoga lo yang berhasil tahun ini 🤞

TUGAS SEKARANG:
Buatkan 1 utas baru yang terdiri dari **8 postingan berantai** untuk produk berikut:
- Tahun saat ini: {current_year} (kalau menyebut tahun/periode, WAJIB pakai {current_year} atau setelahnya — JANGAN pernah pakai tahun lampau seperti 2024/2025!)
- Nama Produk: {produk}
- Keunggulan / Info Produk: {keunggulan}
{extra_info}- Link Produk (wajib masuk persis di Utas ke-7 / postingan kedua terakhir):
{links_display}
- Angle variasi kali ini: {angle}

Aturan ketat (WAJIB DIPATUHI):
1. **HOOK UTAS 1 HARUS NENDANG:**
   - DILARANG membuka dengan kalimat klise/menggurui seperti "Sering banget lihat orang gagal...", "Banyak orang...", atau "Tahukah kamu...".
   - Baris 1 WAJIB berupa judul hook singkat + kredibilitas/janji hasil + **1 emoji** di akhir baris (pilih: 🙏, 🔥, 📌, 💡).
   - Paragraf 2 WAJIB mematahkan cara ribet + menyebut angka konkret (misal: "Gue nggak pakai cara aneh. Cuma 5 kebiasaan/langkah ini...").
   - Paragraf 3 WAJIB 1 kalimat urgensi kenapa harus mulai sekarang.
   - Pisahkan ke-3 paragraf itu dengan baris kosong (`\\n\\n`).
2. **EMOJI HARUS TERASA HIDUP (TAPI NATURAL):**
   - Utas 1: wajib 1 emoji di akhir judul baris pertama.
   - Utas 2: wajib 1 emoji di kalimat pembuka/penutup (`🤔`, `👇`).
   - Utas 3–5: setiap postingan WAJIB punya **1–2 emoji relevan** di awal judul tip atau di akhir paragraf (misal `📌`, `✍️`, `⚡`, `🎯`, `🧠`, `⏰`).
   - Utas 6: wajib pakai emoji ikon di depan nama produk (misal `📊`, `📘`, `💻`, `✅`) + tulis jelas `Alasannya:` dan `Kekurangannya:`.
   - Utas 7: wajib 1 emoji penunjuk di baris pengantar link (`👇`) + Link Produk persis aslinya + soft-selling santai.
   - Utas 8: wajib 1 emoji penyemangat di akhir (`🤞`, `💪`, `🙏`).
3. **UTAS 2 (FASE MASALAH):**
   - Buka dengan pertanyaan singkat (`Lo sekarang lagi di fase mana?` atau sejenisnya), lalu 3 bullet `•` berisi **kondisi nyata** (bukan kalimat tanya semua), lalu 1 kalimat pengantar masuk ke tips.
4. **UTAS 3–5 (TIPS KONKRET):**
   - Pakai label seperti `Tip 1:`, `Tip 2 & 3:`, `Tip 4 & 5:` (atau `Langkah 1:`, dst.) yang konsisten dengan angka di Hook Utas 1!
   - Gunakan paragraf pendek dipisah baris kosong (`\\n\\n`), bahasa ngobrol nyata, JANGAN pakai kalimat klise/robot.
5. **UTAS 8 (TERAKHIR):**
   - Murni ajakan tanya/diskusi di kolom komentar ("tanya di komen. Gue jawab satu-satu.") + penyemangat. JANGAN taruh link di utas ke-8.
6. JANGAN beri nomor kartu di awal postingan ("1.", "2.", "3.") dan JANGAN pakai hashtag (#).
7. Setiap postingan MAKSIMAL 450 karakter (termasuk spasi, baris baru, emoji, dan link).
8. Sertakan juga `"topic_tag"` untuk topik biru Threads (MAKSIMAL 2 KATA yang padat & relevan, misal "CPNS 2026" atau "Tips Belajar", TANPA simbol `#`, `.`, `&`, maks 50 karakter).

Kembalikan HANYA JSON valid dengan format:
{{
  "topic_tag": "CPNS 2026",
  "posts": [
    "isi utas 1 (hook 3 paragraf + emoji)",
    "isi utas 2 (fase masalah 3 bullet + emoji)",
    "isi utas 3 (tip/value + emoji)",
    "isi utas 4 (tip/value + emoji)",
    "isi utas 5 (tip/value + emoji)",
    "isi utas 6 (produk berikon emoji + alasan + kekurangan)",
    "isi utas 7 (pengantar emoji + link produk + soft CTA)",
    "isi utas 8 (ajakan komen + semangat + emoji, tanpa link)"
  ]
}}"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": gemini_api_key,
    }
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.9,
            "responseMimeType": "application/json",
        },
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=45)
    if not resp.ok:
        raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text}")

    data = resp.json()
    try:
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        parsed = extract_json_object(raw_text)
        posts = [
            str(p).replace("\ufffc", "").strip()
            for p in parsed["posts"]
            if str(p).replace("\ufffc", "").strip()
        ]
        ai_topic = sanitize_topic_tag(str(parsed.get("topic_tag", "")))
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Format output Gemini tidak sesuai: {data}") from exc

    if len(posts) < 3:
        raise RuntimeError(f"Jumlah utas terlalu sedikit: {posts}")

    # Pastikan link produk ada di utas kedua terakhir (sebelum utas closing interaksi)
    if links:
        link_idx = -2
        posts[link_idx] = ensure_links_in_post(posts[link_idx], links)

    topic_tag = manual_topic or ai_topic
    return [trim_post(p) for p in posts], topic_tag


def wait_container_ready(container_id: str, access_token: str, max_attempts: int = 10) -> None:
    for attempt in range(1, max_attempts + 1):
        resp = requests.get(
            f"{THREADS_API_BASE}/{container_id}",
            params={"fields": "status,error_message", "access_token": access_token},
            timeout=30,
        )
        resp.raise_for_status()
        info = resp.json()
        status = info.get("status", "")
        if status == "FINISHED":
            return
        if status in {"ERROR", "EXPIRED"}:
            raise RuntimeError(f"Container {container_id} gagal ({status}): {info.get('error_message')}")
        if status == "PUBLISHED":
            return
        print(f"Menunggu media container {container_id} (percobaan {attempt}/{max_attempts}, status={status})...")
        time.sleep(5)
    raise RuntimeError(f"Timeout menunggu container {container_id} siap.")


def create_and_publish_single(
    user_id: str,
    access_token: str,
    text: str,
    reply_to_id: str | None = None,
    image_url: str | None = None,
    topic_tag: str | None = None,
) -> str:
    payload: dict[str, str] = {
        "text": text,
        "access_token": access_token,
    }
    if image_url:
        payload["media_type"] = "IMAGE"
        payload["image_url"] = image_url
    else:
        payload["media_type"] = "TEXT"

    if reply_to_id:
        payload["reply_to_id"] = reply_to_id
    if topic_tag:
        payload["topic_tag"] = topic_tag

    create_resp = requests.post(
        f"{THREADS_API_BASE}/{user_id}/threads",
        json=payload,
        timeout=30,
    )
    if not create_resp.ok:
        raise RuntimeError(f"Gagal buat container Threads ({create_resp.status_code}): {create_resp.text}")

    container_id = create_resp.json().get("id")
    if not container_id:
        raise RuntimeError(f"Response container tidak memiliki 'id': {create_resp.text}")

    # Wajib tunggu status FINISHED terutama kalau ada gambar
    time.sleep(3 if image_url else 1)
    wait_container_ready(container_id, access_token)

    pub_resp = requests.post(
        f"{THREADS_API_BASE}/{user_id}/threads_publish",
        json={"creation_id": container_id, "access_token": access_token},
        timeout=30,
    )
    if not pub_resp.ok:
        raise RuntimeError(f"Gagal publish Threads ({pub_resp.status_code}): {pub_resp.text}")

    post_id = pub_resp.json().get("id")
    if not post_id:
        raise RuntimeError(f"Response publish tidak memiliki 'id': {pub_resp.text}")
    return str(post_id)


def publish_thread_chain(
    user_id: str,
    access_token: str,
    posts: list[str],
    image_url: str = "",
    topic_tag: str = "",
    dry_run: bool = False,
) -> list[str]:
    if dry_run:
        print("=== DRY RUN MODE (tidak benar-benar memposting ke Threads) ===")
        for idx, text in enumerate(posts, start=1):
            extra = ""
            if idx == 1:
                if topic_tag:
                    extra += f" [TOPIC: {topic_tag}]"
                if image_url:
                    extra += f" [IMAGE: {image_url}]"
            print(f"\n--- Utas {idx}/{len(posts)}{extra} ({len(text)} karakter) ---\n{text}")
        return [f"dry-run-{i}" for i in range(1, len(posts) + 1)]

    published_ids: list[str] = []
    prev_id: str | None = None

    for idx, text in enumerate(posts, start=1):
        img = image_url if (idx == 1 and image_url) else None
        tag = topic_tag if (idx == 1 and topic_tag) else None
        post_id = create_and_publish_single(
            user_id=user_id,
            access_token=access_token,
            text=text,
            reply_to_id=prev_id,
            image_url=img,
            topic_tag=tag,
        )
        published_ids.append(post_id)
        prev_id = post_id
        print(f"Berhasil publish Utas {idx}/{len(posts)} -> ID: {post_id}")
        if idx < len(posts):
            time.sleep(4)

    return published_ids


def update_sheet_status(webhook_url: str, secret: str, row_number: int, angle_label: str) -> None:
    wib = timezone(timedelta(hours=7))
    now_str = datetime.now(wib).strftime("%Y-%m-%d %H:%M WIB")
    resp = requests.post(
        webhook_url,
        json={
            "key": secret,
            "row_number": row_number,
            "terakhir_post": now_str,
            "catatan_angle": angle_label,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Gagal update Google Sheet: {data}")


def main() -> int:
    dry_run = get_env("DRY_RUN", "false").lower() in {"1", "true", "yes"}
    webhook_url = get_env("SHEET_WEBHOOK_URL", required=True)
    sheet_secret = get_env("SHEET_SECRET", required=True)
    gemini_api_key = get_env("GEMINI_API_KEY", required=True)
    gemini_model = get_env("GEMINI_MODEL", "gemini-2.5-flash")

    threads_user_id = get_env("THREADS_USER_ID", required=not dry_run)
    threads_access_token = get_env("THREADS_ACCESS_TOKEN", required=not dry_run)

    products = fetch_products(webhook_url, sheet_secret)
    product = pick_product(products)
    angle = pick_angle(str(product.get("Catatan_Angle", "")))
    angle_label = angle.split(":")[0].strip()

    print(f"Produk terpilih (baris {product['row_number']}): {product['Produk']}")
    print(f"Angle terpilih: {angle_label}")

    posts, topic_tag = generate_thread_posts(gemini_api_key, gemini_model, product, angle)
    image_url = str(product.get("Image_URL", "")).strip()
    if topic_tag:
        print(f"Topic biru terpilih: {topic_tag}")

    published_ids = publish_thread_chain(
        user_id=threads_user_id,
        access_token=threads_access_token,
        posts=posts,
        image_url=image_url,
        topic_tag=topic_tag,
        dry_run=dry_run,
    )

    if not dry_run:
        update_sheet_status(webhook_url, sheet_secret, int(product["row_number"]), angle_label)
        print(f"Google Sheet baris {product['row_number']} berhasil diupdate.")

    print(f"Selesai! Post IDs: {published_ids}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

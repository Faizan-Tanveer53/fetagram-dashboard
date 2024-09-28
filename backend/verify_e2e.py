import urllib.request
import urllib.error
import json
import uuid
import zlib
import struct

API = "http://127.0.0.1:8000"

def generate_vibrant_png(width=240, height=160) -> bytes:
    """Generates a vibrant RGB sunset skyline PNG image in pure Python (no 1x1 black pixel)."""
    raw_rows = bytearray()
    for y in range(height):
        raw_rows.append(0)  # Filter type 0 (None)
        t = y / max(1, height - 1)
        for x in range(width):
            s = x / max(1, width - 1)
            # Vibrant neon purple -> magenta -> sunset coral gradient with a glowing sun orb
            dx = x - int(width * 0.72)
            dy = y - int(height * 0.34)
            dist_sq = dx * dx + dy * dy
            if dist_sq < 28 * 28:
                r, g, b = 253, 224, 71  # Warm golden sun
            elif y > int(height * 0.75) and ((x // 18) % 2 == 0 or y > int(height * 0.84)):
                r, g, b = 18, 21, 35    # Architectural skyline silhouette
            else:
                r = int(139 * (1 - t) + 244 * t)
                g = int(92 * (1 - t) + 63 * t * (0.6 + 0.4 * s))
                b = int(246 * (1 - t) + 140 * t)
            raw_rows.extend((max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))))

    def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
        return struct.pack("!I", len(data)) + chunk_type + data + struct.pack("!I", crc)

    ihdr = struct.pack("!IIBBBBB", width, height, 8, 2, 0, 0, 0)
    compressed = zlib.compress(bytes(raw_rows), 6)
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", ihdr)
        + png_chunk(b"IDAT", compressed)
        + png_chunk(b"IEND", b"")
    )

PNG_BYTES = generate_vibrant_png(240, 160)

def req(method, path, data=None, token=None, headers_extra=None):
    headers = dict(headers_extra or {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None
    if isinstance(data, dict):
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode("utf-8")
    elif isinstance(data, bytes):
        body = data
    r = urllib.request.Request(f"{API}{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        return e.code, json.loads(raw) if raw else {}

def upload_multipart(path, fields, file_field, filename, file_bytes, content_type, token):
    boundary = f"----FetagramBoundary{uuid.uuid4().hex}"
    lines = []
    for k, v in fields.items():
        lines.append(f"--{boundary}".encode())
        lines.append(f'Content-Disposition: form-data; name="{k}"'.encode())
        lines.append(b"")
        lines.append(str(v).encode())
    lines.append(f"--{boundary}".encode())
    lines.append(f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"'.encode())
    lines.append(f"Content-Type: {content_type}".encode())
    lines.append(b"")
    lines.append(file_bytes)
    lines.append(f"--{boundary}--".encode())
    lines.append(b"")
    body = b"\r\n".join(lines)
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Authorization": f"Bearer {token}",
    }
    return req("POST", path, data=body, headers_extra=headers)

def run_suite():
    print("=== FETAGRAM PHASE 6: AUTOMATED E2E & HTTP 206 MEDIA VERIFICATION ===")

    # 1. Clean Boot & Admin Auth
    code, admin_login = req("POST", "/api/auth/login", {"username": "admin@fetagram.internal", "password": "Admin@Fetagram2026!"})
    assert code == 200, f"Admin login failed: {code} {admin_login}"
    admin_token = admin_login["access_token"]
    code, stats0 = req("GET", "/api/admin/stats", token=admin_token)
    print(f"[PASS 1] Admin Authenticated | Initial DB Stats: Users={stats0['total_users']}, Posts={stats0['total_posts']}")

    # 2. Register User A
    code, reg_a = req("POST", "/api/auth/register", {
        "username": "elena_vance",
        "email": "elena@fetagram.io",
        "password": "Password123!",
        "full_name": "Elena Vance",
        "bio": "Architectural lighting & computational design"
    })
    assert code == 200, f"User A registration failed: {code} {reg_a}"
    token_a = reg_a["access_token"]
    id_a = reg_a["user"]["id"]
    print(f"[PASS 2] User A Registered: @{reg_a['user']['username']} (ID={id_a})")

    # 3. Upload Real Vibrant PNG Post + Verify HTTP 200 & HTTP 206 Partial Content Range Delivery
    code, post_a = upload_multipart(
        "/api/posts",
        {"caption": "Twilight glass pavilion reflections #architecture #obsidian", "location": "Zurich, Switzerland"},
        "file",
        "pavilion_twilight.png",
        PNG_BYTES,
        "image/png",
        token_a,
    )
    assert code == 200, f"Multipart upload failed: {code} {post_a}"
    post_id = post_a["id"]
    media_url = post_a["media_url"]
    assert media_url.startswith("http://127.0.0.1:8000/uploads/"), f"Unexpected media_url: {media_url}"

    # Verify HTTP 200 Full Fetch + CORP header
    with urllib.request.urlopen(media_url) as mresp:
        assert mresp.status == 200
        assert mresp.headers.get("Content-Type") == "image/png"
        assert mresp.headers.get("Cross-Origin-Resource-Policy") == "cross-origin"
        assert mresp.headers.get("Accept-Ranges") == "bytes"
        full_data = mresp.read()
        assert len(full_data) == len(PNG_BYTES)

    # Verify HTTP 206 Partial Content Range Fetch
    range_req = urllib.request.Request(media_url, headers={"Range": "bytes=0-63"})
    with urllib.request.urlopen(range_req) as rresp:
        assert rresp.status == 206, f"Expected HTTP 206 Partial Content, got {rresp.status}"
        assert rresp.headers.get("Content-Range", "").startswith("bytes 0-63/")
        chunk = rresp.read()
        assert len(chunk) == 64

    print(f"[PASS 3] Multipart Upload & HTTP 206 Range Delivery Verified: {media_url} ({len(PNG_BYTES)} bytes)")

    # 4. Register User B & Follow User A
    code, reg_b = req("POST", "/api/auth/register", {
        "username": "marcus_chen",
        "email": "marcus@fetagram.io",
        "password": "Password123!",
        "full_name": "Marcus Chen",
        "bio": "Visual director & kinetic typography"
    })
    assert code == 200, f"User B registration failed: {code} {reg_b}"
    token_b = reg_b["access_token"]
    id_b = reg_b["user"]["id"]
    code, follow_res = req("POST", f"/api/users/{id_a}/follow", token=token_b)
    assert code == 200 and follow_res["following"] is True
    print(f"[PASS 4] User B (@{reg_b['user']['username']}) Registered & Followed User A")

    # 5. User B Likes, Comments, Bookmarks, and Reports User A's Post
    code, like_res = req("POST", f"/api/posts/{post_id}/like", token=token_b)
    assert code == 200 and like_res["liked"] is True and like_res["likes_count"] == 1
    code, comm_res = req("POST", f"/api/posts/{post_id}/comments", {"content": "Phenomenal color grading and composition!"}, token=token_b)
    assert code == 200 and comm_res["author_username"] == "marcus_chen"
    code, save_res = req("POST", f"/api/posts/{post_id}/bookmark", token=token_b)
    assert code == 200 and save_res["bookmarked"] is True
    code, rep_res = req("POST", "/api/reports", {"target_post_id": post_id, "reason": "Automated E2E verification flag"}, token=token_b)
    assert code == 200
    report_id = rep_res["id"]
    print(f"[PASS 5] Engagement & Report Pipeline Verified: Likes=1, Comments=1, Saved=True, Report ID={report_id}")

    # 6. Direct Messaging
    code, dm_res = req("POST", "/api/messages", {"recipient_id": id_a, "content": "Hey Elena, loved the Zurich pavilion shot!"}, token=token_b)
    assert code == 200
    code, convs = req("GET", "/api/messages/conversations", token=token_a)
    assert code == 200 and len(convs) == 1 and convs[0]["unread_count"] == 1
    print(f"[PASS 6] Direct Messaging Verified: Unread badge count={convs[0]['unread_count']}")

    # 7. Notifications Verification
    code, notifs = req("GET", "/api/notifications", token=token_a)
    assert code == 200 and len(notifs) >= 3
    print(f"[PASS 7] Real-Time Notifications Verified for User A: {len(notifs)} events recorded")

    # 8. Admin Portal Live Stats & Report Resolution
    code, stats1 = req("GET", "/api/admin/stats", token=admin_token)
    assert code == 200 and stats1["total_users"] == 3 and stats1["total_posts"] == 1 and stats1["pending_reports"] == 1
    code, resolve_res = req("POST", f"/api/admin/reports/{report_id}/resolve", {"status": "DISMISSED", "delete_post": False}, token=admin_token)
    assert code == 200
    print(f"[PASS 8] Admin Telemetry & Report Dismissal Verified: Users={stats1['total_users']}, Posts={stats1['total_posts']}")

    # 9. Admin Suspension & Instant JWT Revocation
    code, ban_res = req("POST", f"/api/admin/users/{id_b}/ban", token=admin_token)
    assert code == 200 and ban_res["is_banned"] is True
    code, blocked_me = req("GET", "/api/auth/me", token=token_b)
    assert code == 403, f"Expected 403 for suspended user JWT, got {code}"
    code, unban_res = req("POST", f"/api/admin/users/{id_b}/ban", token=admin_token)
    assert code == 200 and unban_res["is_banned"] is False
    print("[PASS 9] Admin Account Suspension & Instant HTTP 403 JWT Revocation Verified")

    # 10. Multi-Format Media Verification (PNG, JPG, WebP, MP4) + Second Vibrant Post
    code, post_b = upload_multipart(
        "/api/posts",
        {"caption": "Neon synthwave studio session #design #motion", "location": "Tokyo, Japan"},
        "file",
        "tokyo_synth.png",
        PNG_BYTES,
        "image/png",
        token_b,
    )
    assert code == 200

    # Verify JPEG, WebP, and MP4 magic-byte uploads & HTTP 206 Partial Content streaming
    jpg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00" + os.urandom(256) + b"\xff\xd9"
    webp_bytes = b"RIFF\x24\x01\x00\x00WEBPVP8 \x18\x01\x00\x00" + os.urandom(256)
    mp4_bytes = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom\x00\x00\x01\x00mdat" + os.urandom(256)

    for fmt_label, fname, mime, raw_payload in [
        ("JPEG", "sample_test.jpg", "image/jpeg", jpg_bytes),
        ("WebP", "sample_test.webp", "image/webp", webp_bytes),
        ("MP4", "sample_reel.mp4", "video/mp4", mp4_bytes),
    ]:
        c_up, up_res = upload_multipart("/api/media/upload", {}, "file", fname, raw_payload, mime, token_b)
        assert c_up == 200 and up_res["mime_type"] == mime, f"{fmt_label} upload failed: {c_up} {up_res}"
        r_req = urllib.request.Request(up_res["url"], headers={"Range": "bytes=0-31"})
        with urllib.request.urlopen(r_req) as r_resp:
            assert r_resp.status == 206 and r_resp.headers.get("Content-Type") == mime
            assert r_resp.headers.get("Cross-Origin-Resource-Policy") == "cross-origin"

    print(f"[PASS 10] Multi-Format Media Verified (PNG, JPG, WebP, MP4 via HTTP 200 & 206) — E2E Suite Complete!")

if __name__ == "__main__":
    import os
    from cleanup_test_artifacts import run_targeted_cleanup
    try:
        run_suite()
    finally:
        print("=== EXECUTING AUTOMATIC POST-E2E CLEANUP (PROTECTING @faizan & @admin) ===")
        run_targeted_cleanup()

import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "fetagram.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

TEST_USERNAMES = ("marcus_chen", "elena_vance", "e2e_user_a", "e2e_user_b")

def extract_filename(url: str) -> str:
    if not url:
        return ""
    parts = url.strip().split("/uploads/")
    if len(parts) > 1:
        return parts[-1].split("?")[0].strip("/")
    return ""

def safe_exec(cursor, sql: str, params=()):
    try:
        cursor.execute(sql, params)
    except sqlite3.OperationalError as e:
        if "no such table" not in str(e).lower():
            raise

def run_targeted_cleanup():
    if not os.path.exists(DB_PATH):
        print("Database file not found; nothing to clean.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    c = conn.cursor()

    all_before = c.execute("SELECT id, username, role FROM users ORDER BY id ASC").fetchall()
    print("Users before cleanup:", [(r["id"], r["username"], r["role"]) for r in all_before])

    placeholders = ",".join("?" for _ in TEST_USERNAMES)
    target_rows = c.execute(
        f"SELECT id, username, avatar_url FROM users WHERE LOWER(username) IN ({placeholders})",
        tuple(u.lower() for u in TEST_USERNAMES),
    ).fetchall()

    if target_rows:
        target_ids = [r["id"] for r in target_rows]
        id_placeholders = ",".join("?" for _ in target_ids)

        post_ids = [
            r["id"]
            for r in c.execute(f"SELECT id FROM posts WHERE author_id IN ({id_placeholders})", target_ids).fetchall()
        ]
        if post_ids:
            p_ph = ",".join("?" for _ in post_ids)
            safe_exec(c, f"DELETE FROM comment_likes WHERE comment_id IN (SELECT id FROM comments WHERE post_id IN ({p_ph}))", post_ids)
            safe_exec(c, f"DELETE FROM comments WHERE post_id IN ({p_ph})", post_ids)
            safe_exec(c, f"DELETE FROM likes WHERE post_id IN ({p_ph})", post_ids)
            safe_exec(c, f"DELETE FROM saved_posts WHERE post_id IN ({p_ph})", post_ids)
            safe_exec(c, f"DELETE FROM post_hashtags WHERE post_id IN ({p_ph})", post_ids)
            safe_exec(c, f"DELETE FROM post_media WHERE post_id IN ({p_ph})", post_ids)
            safe_exec(c, f"DELETE FROM notifications WHERE post_id IN ({p_ph})", post_ids)
            safe_exec(c, f"DELETE FROM reports WHERE target_type = 'POST' AND target_id IN ({p_ph})", post_ids)
            safe_exec(c, f"DELETE FROM posts WHERE id IN ({p_ph})", post_ids)

        safe_exec(c, f"DELETE FROM comment_likes WHERE user_id IN ({id_placeholders})", target_ids)
        safe_exec(c, f"DELETE FROM comments WHERE user_id IN ({id_placeholders})", target_ids)
        safe_exec(c, f"DELETE FROM likes WHERE user_id IN ({id_placeholders})", target_ids)
        safe_exec(c, f"DELETE FROM saved_posts WHERE user_id IN ({id_placeholders})", target_ids)
        safe_exec(c, f"DELETE FROM story_views WHERE viewer_id IN ({id_placeholders}) OR story_id IN (SELECT id FROM stories WHERE user_id IN ({id_placeholders}))", target_ids + target_ids)
        safe_exec(c, f"DELETE FROM stories WHERE user_id IN ({id_placeholders})", target_ids)
        safe_exec(c, f"DELETE FROM reels WHERE author_id IN ({id_placeholders})", target_ids)
        safe_exec(c, f"DELETE FROM messages WHERE sender_id IN ({id_placeholders}) OR receiver_id IN ({id_placeholders})", target_ids + target_ids)
        safe_exec(c, f"DELETE FROM conversation_members WHERE user_id IN ({id_placeholders})", target_ids)
        safe_exec(c, "DELETE FROM conversations WHERE id NOT IN (SELECT DISTINCT conversation_id FROM conversation_members)")
        safe_exec(c, f"DELETE FROM notifications WHERE recipient_id IN ({id_placeholders}) OR actor_id IN ({id_placeholders})", target_ids + target_ids)
        safe_exec(c, f"DELETE FROM reports WHERE reporter_id IN ({id_placeholders}) OR (target_type = 'USER' AND target_id IN ({id_placeholders}))", target_ids + target_ids)
        safe_exec(c, f"DELETE FROM follows WHERE follower_id IN ({id_placeholders}) OR following_id IN ({id_placeholders})", target_ids + target_ids)
        safe_exec(c, f"DELETE FROM follow_requests WHERE requester_id IN ({id_placeholders}) OR target_id IN ({id_placeholders})", target_ids + target_ids)
        safe_exec(c, f"DELETE FROM blocks WHERE blocker_id IN ({id_placeholders}) OR blocked_id IN ({id_placeholders})", target_ids + target_ids)
        safe_exec(c, f"DELETE FROM mutes WHERE muter_id IN ({id_placeholders}) OR muted_id IN ({id_placeholders})", target_ids + target_ids)
        safe_exec(c, f"DELETE FROM admin_audit_logs WHERE target_type = 'USER' AND target_id IN ({id_placeholders})", [str(i) for i in target_ids])
        safe_exec(c, f"DELETE FROM users WHERE id IN ({id_placeholders})", target_ids)
        conn.commit()
        print("Deleted test user IDs:", target_ids)
    else:
        print("Zero E2E test users found.")

    # Collect all media filenames actively referenced by remaining real users (@faizan, @admin)
    referenced_files = set()
    for q in (
        "SELECT avatar_url AS url FROM users",
        "SELECT media_url AS url FROM posts",
        "SELECT media_url AS url FROM post_media",
        "SELECT media_url AS url FROM stories",
        "SELECT media_url AS url FROM reels",
        "SELECT video_url AS url FROM reels",
        "SELECT media_url AS url FROM messages",
    ):
        try:
            for row in c.execute(q).fetchall():
                fn = extract_filename(row["url"])
                if fn:
                    referenced_files.add(fn)
        except sqlite3.OperationalError:
            pass

    removed_files = []
    if os.path.exists(UPLOAD_DIR):
        for fn in os.listdir(UPLOAD_DIR):
            fpath = os.path.join(UPLOAD_DIR, fn)
            if os.path.isfile(fpath) and fn not in referenced_files:
                os.remove(fpath)
                removed_files.append(fn)

    all_after = c.execute("SELECT id, username, role FROM users ORDER BY id ASC").fetchall()
    remaining_posts = c.execute("SELECT id, author_id, caption, media_url FROM posts ORDER BY id ASC").fetchall()
    print("Removed orphaned test media files:", removed_files)
    print("Kept active media files:", sorted(referenced_files))
    print("Remaining users after cleanup:", [(r["id"], r["username"], r["role"]) for r in all_after])
    print("Remaining posts after cleanup:", [dict(p) for p in remaining_posts])
    conn.close()

if __name__ == "__main__":
    run_targeted_cleanup()

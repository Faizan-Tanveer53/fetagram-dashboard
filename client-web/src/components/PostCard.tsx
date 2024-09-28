import React, { useState } from "react";

export const PostCard: React.FC<{
  post: any;
  onToggleLike: (postId: number) => void;
  onAddComment: (postId: number, text: string) => void;
}> = ({ post, onToggleLike, onAddComment }) => {
  const [commentText, setCommentText] = useState("");
  const [burst, setBurst] = useState(false);

  const handleDoubleClick = () => {
    setBurst(true);
    onToggleLike(post.id);
    setTimeout(() => setBurst(false), 850);
  };

  const handleCommentSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!commentText.trim()) return;
    onAddComment(post.id, commentText.trim());
    setCommentText("");
  };

  return (
    <article style={{ background: "#121214", border: "1px solid #262626", borderRadius: 10, overflow: "hidden", marginBottom: 20 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 14px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <img src={post.author_avatar} alt={post.username} style={{ width: 36, height: 36, borderRadius: "50%", objectFit: "cover" }} />
          <div>
            <div style={{ fontWeight: 700, fontSize: 14, display: "flex", alignItems: "center", gap: 5 }}>
              {post.username}
              {post.author_verified && (
                <span title="Verified" style={{ color: "#0095f6", fontSize: 13 }}>✔</span>
              )}
            </div>
            <div style={{ fontSize: 12, color: "#a1a1aa" }}>{post.location}</div>
          </div>
        </div>
      </div>

      <div onDoubleClick={handleDoubleClick} style={{ position: "relative", cursor: "pointer", background: "#000" }}>
        <img src={post.media_url} alt={post.caption} style={{ width: "100%", maxHeight: 520, objectFit: "cover", display: "block" }} />
        {burst && (
          <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)", fontSize: 76, pointerEvents: "none" }}>
            ❤️
          </div>
        )}
      </div>

      <div style={{ padding: "12px 14px" }}>
        <div style={{ display: "flex", gap: 16, marginBottom: 8 }}>
          <button
            onClick={() => onToggleLike(post.id)}
            style={{ background: "transparent", border: "none", color: post.liked_by_me ? "#ff3040" : "#f5f5f5", fontSize: 20, cursor: "pointer" }}
          >
            {post.liked_by_me ? "❤️" : "🤍"}
          </button>
        </div>
        <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 6 }}>{post.likes_count.toLocaleString()} likes</div>
        <div style={{ fontSize: 14, marginBottom: 8 }}>
          <strong style={{ marginRight: 6 }}>{post.username}</strong>
          {post.caption}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: 10 }}>
          {(post.comments || []).map((c: any) => (
            <div key={c.id} style={{ fontSize: 13 }}>
              <strong style={{ marginRight: 6 }}>{c.username}</strong>
              {c.text}
            </div>
          ))}
        </div>
        <form onSubmit={handleCommentSubmit} style={{ display: "flex", gap: 8, borderTop: "1px solid #262626", paddingTop: 10 }}>
          <input
            value={commentText}
            onChange={(e) => setCommentText(e.target.value)}
            placeholder="Add a comment..."
            style={{ flex: 1, background: "transparent", border: "none", color: "#fff", outline: "none" }}
          />
          <button type="submit" style={{ background: "transparent", border: "none", color: "#0095f6", fontWeight: 700, cursor: "pointer" }}>
            Post
          </button>
        </form>
      </div>
    </article>
  );
};

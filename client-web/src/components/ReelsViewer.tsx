import React from "react";

export const ReelsViewer: React.FC<{ reels: any[] }> = ({ reels }) => (
  <div style={{ height: "calc(100vh - 56px)", maxWidth: 420, margin: "0 auto", overflowY: "scroll", scrollSnapType: "y mandatory" }}>
    {reels.map((r) => (
      <div
        key={r.id}
        style={{
          position: "relative",
          height: "calc(100vh - 56px)",
          scrollSnapAlign: "start",
          borderRadius: 14,
          overflow: "hidden",
          marginBottom: 16,
          border: "1px solid #27272a",
        }}
      >
        <img src={r.media_url} alt={r.caption} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        <div style={{ position: "absolute", bottom: 22, left: 18, right: 70, color: "#fff" }}>
          <div style={{ fontWeight: 700, marginBottom: 6 }}>@{r.username} {r.is_verified && "✔"}</div>
          <div style={{ fontSize: 14, marginBottom: 8 }}>{r.caption}</div>
          <div style={{ fontSize: 12, background: "rgba(0,0,0,0.5)", padding: "4px 10px", borderRadius: 999, display: "inline-block" }}>
            {r.audio_track}
          </div>
        </div>
      </div>
    ))}
  </div>
);

export const DirectMessenger: React.FC<{ messages: any[]; onSend: (text: string) => void }> = ({ messages, onSend }) => {
  const [text, setText] = React.useState("");
  return (
    <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", height: "calc(100vh - 64px)", background: "#18181b", borderRadius: 14, overflow: "hidden", border: "1px solid #27272e" }}>
      <div style={{ borderRight: "1px solid #27272e", padding: 16 }}>
        <h3 style={{ fontWeight: 700, marginBottom: 12 }}>Direct Messages</h3>
        <div style={{ padding: 12, background: "#27272e", borderRadius: 10, fontWeight: 600 }}>sara_designs ✔</div>
      </div>
      <div style={{ display: "flex", flexDirection: "column" }}>
        <div style={{ flex: 1, padding: 18, overflowY: "auto", display: "flex", flexDirection: "column", gap: 10 }}>
          {messages.map((m, idx) => (
            <div
              key={idx}
              style={{
                alignSelf: m.sender === "me" ? "flex-end" : "flex-start",
                background: m.sender === "me" ? "#0095f6" : "#27272e",
                padding: "10px 14px",
                borderRadius: 16,
                maxWidth: "70%",
              }}
            >
              {m.content}
            </div>
          ))}
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!text.trim()) return;
            onSend(text.trim());
            setText("");
          }}
          style={{ display: "flex", gap: 10, padding: 14, borderTop: "1px solid #27272e" }}
        >
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Message over WebSocket (/ws/chat)..."
            style={{ flex: 1, padding: 10, borderRadius: 999, background: "#121214", border: "1px solid #32323a", color: "#fff" }}
          />
          <button type="submit" style={{ padding: "10px 18px", borderRadius: 999, background: "#0095f6", color: "#fff", border: "none", fontWeight: 700 }}>
            Send
          </button>
        </form>
      </div>
    </div>
  );
};

export const ProfileTabs: React.FC<{ user: any; posts: any[] }> = ({ user, posts }) => (
  <div>
    <div style={{ display: "flex", alignItems: "center", gap: 36, paddingBottom: 24, borderBottom: "1px solid #27272e", marginBottom: 20 }}>
      <img src={user?.avatar_url} alt={user?.username} style={{ width: 120, height: 120, borderRadius: "50%", objectFit: "cover", border: "3px solid #dc2743" }} />
      <div>
        <h2 style={{ fontSize: 22, fontWeight: 700, marginBottom: 10 }}>
          {user?.username} {user?.is_verified && <span style={{ color: "#0095f6" }}>✔</span>}
        </h2>
        <div style={{ display: "flex", gap: 24, marginBottom: 12 }}>
          <span><strong>{posts.length}</strong> posts</span>
          <span><strong>14.8k</strong> followers</span>
          <span><strong>412</strong> following</span>
        </div>
        <p style={{ color: "#d4d4d8", fontSize: 14 }}>{user?.bio}</p>
      </div>
    </div>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 6 }}>
      {posts.map((p) => (
        <img key={p.id} src={p.media_url} alt={p.caption} style={{ width: "100%", aspectRatio: "1/1", objectFit: "cover", borderRadius: 4 }} />
      ))}
    </div>
  </div>
);

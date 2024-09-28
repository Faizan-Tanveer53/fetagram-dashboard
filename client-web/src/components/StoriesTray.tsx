import React, { useState } from "react";

export interface StoryItem {
  id: number;
  username: string;
  avatar_url: string;
  is_verified: boolean;
  media_url: string;
}

export const StoriesTray: React.FC<{ stories: StoryItem[] }> = ({ stories }) => {
  const [activeStory, setActiveStory] = useState<StoryItem | null>(null);

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 12, color: "#f5f5f5" }}>Stories</div>
      <div style={{ display: "flex", gap: 18, overflowX: "auto", paddingBottom: 8 }}>
        {stories.map((story) => (
          <div
            key={story.id}
            onClick={() => setActiveStory(story)}
            style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6, cursor: "pointer", flexShrink: 0 }}
          >
            <div
              style={{
                width: 74,
                height: 74,
                borderRadius: "50%",
                padding: 3,
                background: "linear-gradient(45deg, #f09433, #e6683c, #dc2743, #cc2366, #bc1888)",
              }}
            >
              <img
                src={story.avatar_url}
                alt={story.username}
                style={{ width: "100%", height: "100%", borderRadius: "50%", objectFit: "cover", border: "3px solid #000" }}
              />
            </div>
            <span style={{ fontSize: 12, color: "#e4e4e7", maxWidth: 76, overflow: "hidden", textOverflow: "ellipsis" }}>
              {story.username}
            </span>
          </div>
        ))}
      </div>

      {activeStory && (
        <div
          onClick={() => setActiveStory(null)}
          style={{
            position: "fixed",
            inset: 0,
            left: 245,
            background: "rgba(0,0,0,0.85)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 500,
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{ width: 360, height: 600, borderRadius: 16, overflow: "hidden", position: "relative", border: "1px solid #27272a" }}
          >
            <img src={activeStory.media_url} alt={activeStory.username} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            <div style={{ position: "absolute", top: 16, left: 16, display: "flex", alignItems: "center", gap: 10 }}>
              <img src={activeStory.avatar_url} alt="" style={{ width: 36, height: 36, borderRadius: "50%", border: "2px solid #fff" }} />
              <strong style={{ color: "#fff" }}>{activeStory.username}</strong>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

import React, { useState } from "react";

const FILTERS: Record<string, string> = {
  Normal: "none",
  Clarendon: "contrast(1.25) saturate(1.35) brightness(1.05)",
  Juno: "sepia(0.35) contrast(1.15) saturate(1.4)",
  Lark: "brightness(1.12) contrast(0.95) saturate(1.15)",
  Monochromatic: "grayscale(1) contrast(1.2)",
};

export const CreateModal: React.FC<{
  onPublish: (payload: { media_url: string; caption: string; filter_name: string; location: string }) => void;
}> = ({ onPublish }) => {
  const [mediaUrl, setMediaUrl] = useState("https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=1000&q=85");
  const [caption, setCaption] = useState("Golden hour across Karakoram peaks #Fetagram");
  const [location, setLocation] = useState("Passu Cones, Gilgit Baltistan");
  const [filterName, setFilterName] = useState("Normal");
  const [aspectRatio, setAspectRatio] = useState("1 / 1");

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      if (typeof ev.target?.result === "string") {
        setMediaUrl(ev.target.result);
      }
    };
    reader.readAsDataURL(file);
  };

  return (
    <div style={{ maxWidth: 580, margin: "0 auto", background: "#18181b", border: "1px solid #2c2c34", borderRadius: 14, padding: 24 }}>
      <h2 style={{ fontSize: 22, fontWeight: 700, marginBottom: 16 }}>Create New Post</h2>
      <div style={{ width: "100%", aspectRatio, overflow: "hidden", borderRadius: 12, marginBottom: 16, background: "#09090b" }}>
        <img
          src={mediaUrl}
          alt="Preview"
          style={{ width: "100%", height: "100%", objectFit: "cover", filter: FILTERS[filterName] || "none" }}
        />
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
        {Object.keys(FILTERS).map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilterName(f)}
            style={{
              padding: "8px 14px",
              borderRadius: 8,
              border: filterName === f ? "1px solid #0095f6" : "1px solid #32323a",
              background: filterName === f ? "rgba(0,149,246,0.2)" : "#222228",
              color: "#fff",
              cursor: "pointer",
            }}
          >
            {f}
          </button>
        ))}
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
        {["1 / 1", "4 / 5", "16 / 9"].map((ratio) => (
          <button
            key={ratio}
            type="button"
            onClick={() => setAspectRatio(ratio)}
            style={{ padding: "6px 12px", borderRadius: 6, background: "#27272e", color: "#fff", border: "1px solid #3f3f46", cursor: "pointer" }}
          >
            Crop {ratio}
          </button>
        ))}
      </div>

      <input type="file" accept="image/*" onChange={handleFileChange} style={{ marginBottom: 10, display: "block", color: "#fff" }} />
      <input
        value={mediaUrl}
        onChange={(e) => setMediaUrl(e.target.value)}
        placeholder="Or paste image URL..."
        style={{ width: "100%", padding: 12, borderRadius: 8, background: "#121214", border: "1px solid #32323a", color: "#fff", marginBottom: 10 }}
      />
      <input
        value={location}
        onChange={(e) => setLocation(e.target.value)}
        placeholder="Location"
        style={{ width: "100%", padding: 12, borderRadius: 8, background: "#121214", border: "1px solid #32323a", color: "#fff", marginBottom: 10 }}
      />
      <textarea
        value={caption}
        onChange={(e) => setCaption(e.target.value)}
        rows={3}
        style={{ width: "100%", padding: 12, borderRadius: 8, background: "#121214", border: "1px solid #32323a", color: "#fff", marginBottom: 14 }}
      />
      <button
        onClick={() => onPublish({ media_url: mediaUrl, caption, filter_name: filterName, location })}
        style={{ width: "100%", padding: 13, background: "#0095f6", color: "#fff", fontWeight: 700, borderRadius: 10, border: "none", cursor: "pointer" }}
      >
        Share to Fetagram
      </button>
    </div>
  );
};

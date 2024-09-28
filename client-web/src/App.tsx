import React, { useEffect, useState } from "react";
import { FetagramApiClient, setAuthToken, getAuthToken } from "./api/client";
import { StoriesTray } from "./components/StoriesTray";
import { PostCard } from "./components/PostCard";
import { CreateModal } from "./components/CreateModal";
import { ReelsViewer } from "./components/ReelsViewer";
import { DirectMessenger } from "./components/DirectMessenger";
import { ProfileTabs } from "./components/ProfileTabs";
import { BroadcastBanner } from "./components/BroadcastBanner";
import { AccountGuard } from "./components/AccountGuard";

export const App: React.FC = () => {
  const [view, setView] = useState<string>("home");
  const [currentUser, setCurrentUser] = useState<any>(null);
  const [posts, setPosts] = useState<any[]>([]);
  const [stories, setStories] = useState<any[]>([]);
  const [reels, setReels] = useState<any[]>([]);
  const [announcement, setAnnouncement] = useState<any>(null);
  const [messages, setMessages] = useState<any[]>([]);

  const refreshAll = async () => {
    if (!getAuthToken()) return;
    try {
      const me = await FetagramApiClient.getMe();
      setCurrentUser(me);
      const [feedData, storiesList, reelsList] = await Promise.all([
        FetagramApiClient.getFeed(1, me?.id),
        FetagramApiClient.getStories(),
        FetagramApiClient.getReels(),
      ]);
      setPosts(Array.isArray(feedData) ? feedData : feedData.posts || []);
      setStories(storiesList || []);
      setReels(reelsList || []);
    } catch (err) {
      console.error("Sync error:", err);
    }
  };

  useEffect(() => {
    refreshAll();
  }, []);

  const unreadMessages = currentUser?.unread_messages_count || 0;
  const unreadNotifs = currentUser?.unread_notifications_count || 0;

  return (
    <div style={{ display: "flex", height: "100vh", width: "100vw", overflow: "hidden", background: "#000", color: "#f5f5f5" }}>
      <AccountGuard isBanned={Boolean(currentUser?.is_banned)} onSwitchAccount={() => setAuthToken(null)} />
      <aside style={{ width: 245, flexShrink: 0, borderRight: "1px solid #262626", padding: "24px 16px", background: "#09090b" }}>
        <div style={{ fontSize: 32, fontWeight: 700, marginBottom: 24, fontFamily: "cursive" }}>Fetagram</div>
        {["home", "search", "explore", "reels", "messages", "notifications", "create", "profile"].map((nav) => (
          <button
            key={nav}
            onClick={() => setView(nav)}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              width: "100%",
              textAlign: "left",
              padding: "12px 14px",
              borderRadius: 10,
              border: "none",
              background: view === nav ? "#27272c" : "transparent",
              color: "#fff",
              fontWeight: 700,
              textTransform: "capitalize",
              marginBottom: 4,
              cursor: "pointer",
            }}
          >
            <span>{nav}</span>
            {nav === "messages" && unreadMessages > 0 && (
              <span style={{ background: "#ff3040", borderRadius: 999, padding: "2px 7px", fontSize: 11 }}>{unreadMessages}</span>
            )}
            {nav === "notifications" && unreadNotifs > 0 && (
              <span style={{ background: "#ff3040", borderRadius: 999, padding: "2px 7px", fontSize: 11 }}>{unreadNotifs}</span>
            )}
          </button>
        ))}
      </aside>
      <main style={{ flex: 1, height: "100vh", overflowY: "auto", padding: 28 }}>
        <div style={{ maxWidth: 600, margin: "0 auto" }}>
          <BroadcastBanner announcement={announcement} />
          {view === "home" && (
            <>
              {stories.length > 0 && <StoriesTray stories={stories} />}
              {posts.length === 0 ? (
                <div style={{ padding: 40, textAlign: "center", background: "#18181b", borderRadius: 12 }}>
                  Your feed is empty. Follow users or share your first post!
                </div>
              ) : (
                posts.map((p) => (
                  <PostCard
                    key={p.id}
                    post={p}
                    onToggleLike={(id) => FetagramApiClient.toggleLike(id).then(refreshAll)}
                    onAddComment={(id, text) => FetagramApiClient.addComment(id, text).then(refreshAll)}
                  />
                ))
              )}
            </>
          )}
          {view === "create" && (
            <CreateModal
              onPublish={(payload) =>
                FetagramApiClient.createPost(payload).then(() => {
                  refreshAll();
                  setView("home");
                })
              }
            />
          )}
          {view === "reels" && <ReelsViewer reels={reels} />}
          {view === "messages" && (
            <DirectMessenger
              messages={messages}
              onSend={(txt) => {
                setMessages((prev) => [...prev, { sender: "me", content: txt }]);
              }}
            />
          )}
          {view === "profile" && <ProfileTabs user={currentUser} posts={currentUser?.posts || []} />}
        </div>
      </main>
    </div>
  );
};

export default App;

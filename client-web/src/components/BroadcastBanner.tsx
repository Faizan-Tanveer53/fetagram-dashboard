import React from "react";

export const BroadcastBanner: React.FC<{ announcement: { message: string } | null }> = ({ announcement }) => {
  if (!announcement || !announcement.message) return null;
  return (
    <div
      style={{
        background: "linear-gradient(90deg, #1e1b4b, #312e81, #4338ca)",
        border: "1px solid #6366f1",
        color: "#ffffff",
        padding: "12px 18px",
        borderRadius: 12,
        marginBottom: 20,
        display: "flex",
        alignItems: "center",
        gap: 12,
        fontSize: 14,
        fontWeight: 600,
      }}
    >
      <span style={{ background: "#ef4444", padding: "3px 8px", borderRadius: 6, fontSize: 11, fontWeight: 800 }}>
        SYSTEM BROADCAST
      </span>
      <span>{announcement.message}</span>
    </div>
  );
};

export const AccountGuard: React.FC<{ isBanned: boolean; onSwitchAccount: () => void }> = ({ isBanned, onSwitchAccount }) => {
  if (!isBanned) return null;
  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        left: 245,
        background: "rgba(9, 9, 11, 0.96)",
        zIndex: 1000,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
    >
      <div
        style={{
          maxWidth: 460,
          background: "#18181b",
          border: "1px solid #ef4444",
          borderRadius: 16,
          padding: 32,
          textAlign: "center",
        }}
      >
        <div style={{ fontSize: 44, marginBottom: 12 }}>🚫</div>
        <h2 style={{ fontSize: 22, fontWeight: 800, color: "#f87171", marginBottom: 10 }}>
          Account Suspended
        </h2>
        <p style={{ fontSize: 14, color: "#d4d4d8", lineHeight: 1.5, marginBottom: 20 }}>
          Your Fetagram account has been restricted (`is_banned: true`) by the Trust &amp; Safety Admin Portal.
        </p>
        <button
          onClick={onSwitchAccount}
          style={{
            padding: "11px 22px",
            borderRadius: 10,
            background: "#ef4444",
            color: "#ffffff",
            border: "none",
            fontWeight: 700,
            cursor: "pointer",
          }}
        >
          Sign Out / Switch Account
        </button>
      </div>
    </div>
  );
};

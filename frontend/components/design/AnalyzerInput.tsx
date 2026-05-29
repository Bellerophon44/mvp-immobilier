"use client";
import { useState, CSSProperties } from "react";
import { ArrowRight, LinkIcon } from "./Icons";

export interface AnalyzerMode {
  mode: "url" | "text";
  value: string;
}

interface AnalyzerInputProps {
  onAnalyze: (params: AnalyzerMode) => void;
  busy?: boolean;
}

export default function AnalyzerInput({ onAnalyze, busy = false }: AnalyzerInputProps) {
  const [mode, setMode] = useState<"url" | "text">("url");
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  const [focused, setFocused] = useState(false);

  const value = mode === "url" ? url : text;
  const canAnalyze = value.trim().length >= (mode === "url" ? 8 : 40) && !busy;

  function submit() {
    if (!canAnalyze) return;
    onAnalyze({ mode, value });
  }

  function tabStyle(active: boolean): CSSProperties {
    return {
      fontFamily: "var(--font-sans)",
      fontSize: 13,
      fontWeight: 500,
      padding: "8px 12px",
      background: "transparent",
      border: "none",
      color: active ? "var(--ink)" : "var(--stone)",
      cursor: "pointer",
      borderBottom: active ? "1.5px solid var(--brick)" : "1.5px solid transparent",
      marginBottom: -1,
      whiteSpace: "nowrap",
    };
  }

  return (
    <div style={{ width: "100%", maxWidth: 640 }}>
      <div style={{ display: "flex", borderBottom: "1px solid var(--stone-line)", marginBottom: 16 }}>
        <button style={tabStyle(mode === "url")} onClick={() => setMode("url")}>
          URL de l&apos;annonce
        </button>
        <button style={tabStyle(mode === "text")} onClick={() => setMode("text")}>
          Texte brut
        </button>
      </div>

      {mode === "url" ? (
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "14px 16px",
          background: "var(--paper)",
          border: `1px solid ${focused ? "var(--brick)" : "var(--stone-line)"}`,
          boxShadow: focused ? "0 0 0 3px var(--brick-soft)" : "none",
          borderRadius: 2,
          transition: "all var(--dur-state) var(--ease-paper)",
        }}>
          <LinkIcon size={18} style={{ color: "var(--stone)", flexShrink: 0 }} />
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            placeholder="https://laveine.immo/annonce/…"
            style={{
              flex: 1,
              border: "none",
              outline: "none",
              background: "transparent",
              fontFamily: "var(--font-sans)",
              fontSize: 15,
              color: "var(--ink)",
            }}
          />
        </div>
      ) : (
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder="Collez ici le texte brut de l'annonce : titre, description, prix, surface, charges…"
          rows={6}
          style={{
            width: "100%",
            padding: "14px 16px",
            background: "var(--paper)",
            border: `1px solid ${focused ? "var(--brick)" : "var(--stone-line)"}`,
            boxShadow: focused ? "0 0 0 3px var(--brick-soft)" : "none",
            borderRadius: 2,
            fontFamily: "var(--font-sans)",
            fontSize: 15,
            lineHeight: 1.5,
            color: "var(--ink)",
            resize: "vertical",
            outline: "none",
            transition: "all var(--dur-state) var(--ease-paper)",
            boxSizing: "border-box",
          }}
        />
      )}

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 18 }}>
        <span style={{ fontFamily: "var(--font-sans)", fontSize: 12, color: "var(--stone)" }}>
          Aucune donnée n&apos;est conservée après l&apos;analyse.
        </span>
        <button
          onClick={submit}
          disabled={!canAnalyze}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            padding: "12px 20px",
            background: "var(--brick)",
            color: "var(--parchment)",
            border: "none",
            borderRadius: 4,
            fontFamily: "var(--font-sans)",
            fontSize: 14,
            fontWeight: 500,
            lineHeight: 1,
            cursor: canAnalyze ? "pointer" : "not-allowed",
            opacity: canAnalyze ? 1 : 0.4,
            transition: "background var(--dur-hover) var(--ease-paper)",
          }}
          onMouseDown={(e) => { if (canAnalyze) (e.currentTarget as HTMLButtonElement).style.transform = "scale(0.99)"; }}
          onMouseUp={(e) => { (e.currentTarget as HTMLButtonElement).style.transform = ""; }}
          onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.transform = ""; (e.currentTarget as HTMLButtonElement).style.background = "var(--brick)"; }}
          onMouseOver={(e) => { if (canAnalyze) (e.currentTarget as HTMLButtonElement).style.background = "var(--brick-deep)"; }}
          onMouseOut={(e) => { (e.currentTarget as HTMLButtonElement).style.background = "var(--brick)"; }}
        >
          {busy ? "Analyse en cours…" : "Analyser l’annonce"}
          {!busy && <ArrowRight size={16} />}
        </button>
      </div>
    </div>
  );
}

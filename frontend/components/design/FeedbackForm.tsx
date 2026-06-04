"use client";

import { useState } from "react";

interface FeedbackFormProps {
  sent: boolean;
  onSubmit: (rating: number, comment: string) => void;
}

const RATINGS = [1, 2, 3, 4, 5];

export default function FeedbackForm({ sent, onSubmit }: FeedbackFormProps) {
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");

  if (sent) {
    return (
      <div style={{
        background: "var(--paper)",
        border: "1px solid var(--stone-line)",
        borderRadius: 4,
        padding: "20px 22px",
        fontFamily: "var(--font-serif)",
        fontStyle: "italic",
        fontSize: 18,
        color: "var(--ink-2)",
        lineHeight: 1.4,
      }}>
        Merci, votre retour a bien ete enregistre.
      </div>
    );
  }

  return (
    <div style={{
      background: "var(--paper)",
      border: "1px solid var(--stone-line)",
      borderRadius: 4,
      padding: "20px 22px",
    }}>
      <div className="t-eyebrow" style={{ marginBottom: 12 }}>
        Cette analyse vous a-t-elle ete utile&nbsp;?
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
        {RATINGS.map((r) => {
          const active = r === rating;
          return (
            <button
              key={r}
              type="button"
              onClick={() => setRating(r)}
              aria-pressed={active}
              style={{
                width: 40,
                height: 40,
                borderRadius: 4,
                border: "1px solid var(--stone-line)",
                background: active ? "var(--ink)" : "var(--parchment)",
                color: active ? "var(--parchment)" : "var(--ink-2)",
                fontFamily: "var(--font-sans)",
                fontSize: 15,
                fontWeight: 500,
                cursor: "pointer",
              }}
            >
              {r}
            </button>
          );
        })}
      </div>

      <textarea
        value={comment}
        maxLength={1000}
        onChange={(e) => setComment(e.target.value)}
        placeholder="Un commentaire (optionnel)"
        rows={3}
        style={{
          width: "100%",
          boxSizing: "border-box",
          padding: "10px 12px",
          background: "var(--parchment)",
          border: "1px solid var(--stone-line)",
          borderRadius: 4,
          fontFamily: "var(--font-sans)",
          fontSize: 14,
          color: "var(--ink)",
          lineHeight: 1.5,
          resize: "vertical",
        }}
      />
      <div style={{
        marginTop: 6,
        fontFamily: "var(--font-sans)",
        fontSize: 12,
        color: "var(--ink-3)",
        lineHeight: 1.5,
      }}>
        Ne saisissez pas de donnees personnelles.
      </div>

      <button
        type="button"
        disabled={rating === 0}
        onClick={() => onSubmit(rating, comment.trim())}
        style={{
          marginTop: 14,
          padding: "9px 16px",
          background: rating === 0 ? "var(--parchment)" : "var(--ink)",
          border: "1px solid var(--stone-line)",
          borderRadius: 4,
          color: rating === 0 ? "var(--ink-3)" : "var(--parchment)",
          fontFamily: "var(--font-sans)",
          fontSize: 13,
          fontWeight: 500,
          cursor: rating === 0 ? "not-allowed" : "pointer",
        }}
      >
        Envoyer
      </button>
    </div>
  );
}

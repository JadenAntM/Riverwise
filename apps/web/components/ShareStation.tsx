"use client";

import { useState } from "react";

export function ShareStation() {
  const [message, setMessage] = useState("");
  const [fallbackUrl, setFallbackUrl] = useState<string | null>(null);
  async function copy() {
    const url = `${window.location.origin}${window.location.pathname}`;
    try {
      await navigator.clipboard.writeText(url);
      setFallbackUrl(null);
      setMessage("Station link copied.");
    } catch {
      setFallbackUrl(url);
      setMessage("Select and copy the station link below.");
    }
  }
  return <div className="station-share">
    <button className="source-link" onClick={copy}>Copy station link</button>
    <span role="status">{message}</span>
    {fallbackUrl && <label>Station page link<input type="url" readOnly value={fallbackUrl} onFocus={(event) => event.target.select()} /></label>}
  </div>;
}

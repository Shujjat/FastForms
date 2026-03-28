import { useEffect, useRef } from "react";
import { api, setAuthToken, setRefreshToken } from "./api";

let gsiLoadPromise = null;

function loadGoogleScript() {
  if (typeof window !== "undefined" && window.google?.accounts?.id) {
    return Promise.resolve();
  }
  if (gsiLoadPromise) return gsiLoadPromise;
  gsiLoadPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector('script[src="https://accounts.google.com/gsi/client"]');
    if (existing) {
      existing.addEventListener("load", () => resolve());
      existing.addEventListener("error", () => reject(new Error("Google script error")));
      return;
    }
    const s = document.createElement("script");
    s.src = "https://accounts.google.com/gsi/client";
    s.async = true;
    s.defer = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("Google script failed to load"));
    document.body.appendChild(s);
  });
  return gsiLoadPromise;
}

/**
 * @param {object} props
 * @param {"creator"|"respondent"} props.role - New Google users get this role
 * @param {() => void} props.onSuccess - Called after tokens are stored
 * @param {"signin_with"|"signup_with"|"continue_with"} props.buttonText
 */
export function GoogleSignInButton({ role = "respondent", onSuccess, buttonText = "signin_with" }) {
  const divRef = useRef(null);
  const onSuccessRef = useRef(onSuccess);
  onSuccessRef.current = onSuccess;
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;

  useEffect(() => {
    if (!clientId || !divRef.current) return;
    let cancelled = false;
    const el = divRef.current;
    loadGoogleScript()
      .then(() => {
        if (cancelled || !window.google?.accounts?.id) return;
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: async (response) => {
            try {
              const { data } = await api.post("/api/auth/google", {
                credential: response.credential,
                role,
              });
              setAuthToken(data.access);
              setRefreshToken(data.refresh);
              onSuccessRef.current?.();
            } catch (e) {
              console.error(e);
            }
          },
        });
        el.innerHTML = "";
        window.google.accounts.id.renderButton(el, {
          type: "standard",
          theme: "outline",
          size: "large",
          text: buttonText,
          width: 280,
        });
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [clientId, role, buttonText]);

  if (!clientId) {
    return (
      <p style={{ fontSize: 12, color: "#9ca3af", margin: "8px 0 0" }}>
        Google Sign-In: set <code>VITE_GOOGLE_CLIENT_ID</code> in <code>frontend/.env</code> (see README).
      </p>
    );
  }

  return <div ref={divRef} style={{ marginTop: 12 }} />;
}

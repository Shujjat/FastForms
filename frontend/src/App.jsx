import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { Link, Navigate, Route, Routes, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { QRCodeSVG } from "qrcode.react";
import { api, downloadFormExport, formatApiError, setAuthToken, setRefreshToken } from "./api";

const ROLE_OPTIONS = [
  { value: "admin", label: "Admin" },
  { value: "creator", label: "Creator" },
  { value: "analyst", label: "Analyst" },
  { value: "respondent", label: "Respondent" },
];
import { GoogleSignInButton } from "./GoogleSignInButton";

/** Local datetime-local value from ISO string (browser timezone). */
function isoToDatetimeLocal(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** ISO string for API, or null if empty. */
function datetimeLocalToIso(local) {
  if (!local || !String(local).trim()) return null;
  const d = new Date(local);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString();
}

function getFormScheduleState(form) {
  if (!form) return { notYetOpen: false, closed: false };
  const now = Date.now();
  const opens = form.opens_at ? new Date(form.opens_at).getTime() : NaN;
  const closes = form.closes_at ? new Date(form.closes_at).getTime() : NaN;
  return {
    notYetOpen: !Number.isNaN(opens) && now < opens,
    closed: !Number.isNaN(closes) && now > closes,
  };
}

/** CSS variables + class name for motion (appearance JSON on Form). */
function appearanceToCssVars(appearance) {
  const a = appearance && typeof appearance === "object" ? appearance : {};
  const accent = a.accent || "#673ab7";
  const pageFill = a.pageGradient || a.pageBg || "#f3f3fb";
  const headerFill = a.headerGradient || accent;
  const borderTop =
    a.borderTop !== undefined && a.borderTop !== ""
      ? a.borderTop
      : `${a.headerBorderWidth !== undefined ? a.headerBorderWidth : "4px"} solid ${accent}`;
  const dark = a.darkMode === true;
  const bodyText = a.bodyText || (dark ? "#e2e8f0" : "#1f2937");
  const mutedText = a.mutedText || (dark ? "#94a3b8" : "#6b7280");
  return {
    "--ff-accent": accent,
    "--ff-accentText": a.accentText || "#ffffff",
    "--ff-pageBg": a.pageBg || "#f3f3fb",
    "--ff-pageFill": pageFill,
    "--ff-headerFill": headerFill,
    "--ff-cardBg": a.cardBg || "#ffffff",
    "--ff-radius": a.radius || "12px",
    "--ff-font": a.fontFamily || "'Google Sans', 'Segoe UI', Roboto, system-ui, sans-serif",
    "--ff-cardShadow": a.cardShadow || "0 2px 8px rgba(0, 0, 0, 0.06)",
    "--ff-borderTop": borderTop,
    "--ff-bodyBorder": a.bodyBorder !== undefined && a.bodyBorder !== "" ? a.bodyBorder : "none",
    "--ff-bodyText": bodyText,
    "--ff-mutedText": mutedText,
  };
}

function appearanceMotionClass(appearance) {
  const a = appearance && typeof appearance === "object" ? appearance : {};
  const m = a.animation;
  if (m === "rise") return "ff-anim-fill-rise";
  if (m === "fadeIn") return "ff-anim-fill-fadeIn";
  if (m === "pulse") return "ff-anim-fill-pulse";
  if (m === "glow") return "ff-anim-fill-glow";
  return "";
}

const THEME_PRESETS = [
  {
    id: "purple",
    label: "Purple (default)",
    appearance: { accent: "#673ab7", accentText: "#ffffff", pageBg: "#f3f3fb", cardBg: "#ffffff", radius: "12px", animation: "fadeIn" },
  },
  {
    id: "blue",
    label: "Blue",
    appearance: { accent: "#2563eb", accentText: "#ffffff", pageBg: "#f1f5f9", cardBg: "#ffffff", radius: "10px", animation: "rise" },
  },
  {
    id: "teal",
    label: "Teal",
    appearance: { accent: "#0d9488", accentText: "#ffffff", pageBg: "#f0fdfa", cardBg: "#ffffff", radius: "12px" },
  },
  {
    id: "rose",
    label: "Rose",
    appearance: { accent: "#db2777", accentText: "#ffffff", pageBg: "#fdf2f8", cardBg: "#ffffff", radius: "14px", animation: "fadeIn" },
  },
  {
    id: "slate",
    label: "Slate",
    appearance: { accent: "#1e293b", accentText: "#ffffff", pageBg: "#f8fafc", cardBg: "#ffffff", radius: "8px" },
  },
  {
    id: "aurora",
    label: "Aurora gradient",
    appearance: {
      accent: "#6366f1",
      accentText: "#ffffff",
      pageGradient: "linear-gradient(145deg, #e0e7ff 0%, #f5f3ff 40%, #fdf4ff 100%)",
      headerGradient: "linear-gradient(90deg, #6366f1, #a855f7)",
      cardBg: "rgba(255,255,255,0.92)",
      radius: "18px",
      fontFamily: "'Segoe UI', system-ui, sans-serif",
      cardShadow: "0 16px 48px rgba(99, 102, 241, 0.2)",
      animation: "rise",
      headerBorderWidth: "0px",
      borderTop: "none",
      bodyBorder: "1px solid rgba(99, 102, 241, 0.12)",
    },
  },
  {
    id: "sunset",
    label: "Sunset",
    appearance: {
      accent: "#ea580c",
      accentText: "#ffffff",
      pageGradient: "linear-gradient(180deg, #fff7ed 0%, #ffedd5 50%, #fef3c7 100%)",
      headerGradient: "linear-gradient(90deg, #ea580c, #f97316)",
      cardBg: "#ffffff",
      radius: "14px",
      cardShadow: "0 8px 24px rgba(234, 88, 12, 0.15)",
      animation: "pulse",
      borderTop: "none",
      headerBorderWidth: "0px",
    },
  },
  {
    id: "ocean",
    label: "Ocean glass",
    appearance: {
      accent: "#0284c7",
      accentText: "#ffffff",
      pageGradient: "linear-gradient(160deg, #e0f2fe 0%, #f0f9ff 50%, #ecfeff 100%)",
      headerGradient: "linear-gradient(135deg, #0369a1, #0ea5e9)",
      cardBg: "rgba(255,255,255,0.95)",
      radius: "16px",
      fontFamily: "system-ui, -apple-system, sans-serif",
      cardShadow: "0 12px 40px rgba(2, 132, 199, 0.18)",
      animation: "glow",
      borderTop: "none",
      bodyBorder: "1px solid rgba(14, 165, 233, 0.2)",
    },
  },
  {
    id: "midnight",
    label: "Midnight",
    appearance: {
      accent: "#a78bfa",
      accentText: "#f8fafc",
      darkMode: true,
      pageGradient: "linear-gradient(180deg, #0f172a 0%, #1e293b 100%)",
      pageBg: "#0f172a",
      headerGradient: "linear-gradient(90deg, #312e81, #5b21b6)",
      cardBg: "#1e293b",
      radius: "12px",
      cardShadow: "0 20px 50px rgba(0, 0, 0, 0.45)",
      animation: "fadeIn",
      bodyBorder: "1px solid rgba(148, 163, 184, 0.25)",
    },
  },
  {
    id: "forest",
    label: "Forest",
    appearance: {
      accent: "#15803d",
      accentText: "#ffffff",
      pageGradient: "linear-gradient(135deg, #ecfccb 0%, #d9f99d 35%, #f7fee7 100%)",
      headerGradient: "linear-gradient(90deg, #166534, #22c55e)",
      cardBg: "#ffffff",
      radius: "14px",
      cardShadow: "0 6px 20px rgba(21, 128, 61, 0.12)",
      animation: "rise",
    },
  },
  {
    id: "neon",
    label: "Neon edge",
    appearance: {
      accent: "#e879f9",
      accentText: "#fae8ff",
      darkMode: true,
      pageGradient: "linear-gradient(200deg, #1a1a2e 0%, #16213e 60%, #0f3460 100%)",
      pageBg: "#1a1a2e",
      headerGradient: "linear-gradient(90deg, #e879f9, #22d3ee)",
      cardBg: "#1e293b",
      radius: "16px",
      fontFamily: "'Segoe UI', system-ui, sans-serif",
      cardShadow: "0 0 32px rgba(232, 121, 249, 0.25)",
      animation: "glow",
      borderTop: "none",
      bodyBorder: "1px solid rgba(34, 211, 238, 0.35)",
    },
  },
];

const QUESTION_TYPES = [
  { value: "short_text", label: "Short Text" },
  { value: "paragraph", label: "Paragraph" },
  { value: "single_choice", label: "Single Choice" },
  { value: "multi_choice", label: "Multiple Choice" },
  { value: "dropdown", label: "Dropdown" },
  { value: "date", label: "Date" },
  { value: "rating", label: "Rating" },
  { value: "file_upload", label: "File Upload" },
];

const CHOICE_TYPES = ["single_choice", "multi_choice", "dropdown"];

/** Preset `format` values (must match backend `_ALLOWED_FORMATS`). */
const VALIDATION_FORMATS = [
  { value: "", label: "None" },
  { value: "email", label: "Email" },
  { value: "phone", label: "Phone" },
  { value: "url", label: "URL" },
  { value: "zip_us", label: "US ZIP code" },
  { value: "integer", label: "Whole number" },
  { value: "alphanumeric", label: "Letters & numbers (no spaces)" },
];

function mergeValidationPatch(prev, patch) {
  const next = { ...(prev || {}) };
  Object.entries(patch).forEach(([k, val]) => {
    if (val === "" || val === null || val === undefined) delete next[k];
    else next[k] = val;
  });
  return next;
}

// --- Auth Context ---

const AuthContext = createContext({
  isAuthed: false,
  userRole: null,
  user: null,
  isAdminUser: false,
  refreshAuth: async () => {},
});

function AuthProvider({ children }) {
  const [isAuthed, setIsAuthed] = useState(Boolean(localStorage.getItem("accessToken")));
  const [userRole, setUserRole] = useState(null);
  const [user, setUser] = useState(null);
  const refreshAuth = useCallback(async () => {
    const authed = Boolean(localStorage.getItem("accessToken"));
    setIsAuthed(authed);
    if (!authed) {
      setUserRole(null);
      setUser(null);
      return;
    }
    try {
      const { data } = await api.get("/api/auth/me");
      setUserRole(data.role || null);
      setUser(data);
    } catch {
      setUserRole(null);
      setUser(null);
    }
  }, []);
  useEffect(() => {
    const handler = () => refreshAuth();
    window.addEventListener("storage", handler);
    return () => window.removeEventListener("storage", handler);
  }, [refreshAuth]);
  useEffect(() => {
    refreshAuth();
  }, [refreshAuth]);
  const isAdminUser = userRole === "admin" || Boolean(user?.is_superuser);
  return (
    <AuthContext.Provider value={{ isAuthed, userRole, user, isAdminUser, refreshAuth }}>
      {children}
    </AuthContext.Provider>
  );
}

function useAuth() {
  return useContext(AuthContext);
}

function ProtectedRoute({ children, requireDesignerRole = false }) {
  const { isAuthed, userRole } = useAuth();
  if (!isAuthed) return <Navigate to="/login" replace />;
  if (requireDesignerRole && !["creator", "admin"].includes(userRole || "")) {
    return <Navigate to="/" replace />;
  }
  return children;
}

function AdminRoute({ children }) {
  const { isAuthed, isAdminUser } = useAuth();
  if (!isAuthed) return <Navigate to="/login" replace />;
  if (!isAdminUser) return <Navigate to="/" replace />;
  return children;
}

// --- Layout ---

function Layout({ children }) {
  const { isAuthed, isAdminUser, refreshAuth } = useAuth();
  const navigate = useNavigate();
  const logout = () => {
    setAuthToken(null);
    setRefreshToken(null);
    refreshAuth();
    navigate("/login");
  };
  return (
    <div className="container">
      <header className="topbar">
        <h1>FastForms</h1>
        <nav>
          <Link to="/">Forms</Link>
          <Link to="/templates">Templates</Link>
          {isAuthed && isAdminUser && <Link to="/admin/users">Users</Link>}
          {!isAuthed && <Link to="/register">Register</Link>}
          {!isAuthed && <Link to="/login">Login</Link>}
          {isAuthed && (
            <button className="btn-secondary btn-sm" onClick={logout}>
              Logout
            </button>
          )}
        </nav>
      </header>
      {children}
    </div>
  );
}

// --- Auth Pages ---

function RegisterPage() {
  const [form, setForm] = useState({
    username: "",
    email: "",
    password: "",
    role: "creator",
    first_name: "",
    last_name: "",
    phone: "",
    organization: "",
  });
  const [msg, setMsg] = useState("");
  const navigate = useNavigate();
  const { refreshAuth } = useAuth();
  const onGoogle = useCallback(() => {
    refreshAuth();
    navigate("/");
  }, [refreshAuth, navigate]);

  const submit = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        username: form.username.trim(),
        email: form.email.trim(),
        password: form.password,
        role: form.role,
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        phone: form.phone.trim(),
        organization: form.organization.trim(),
      };
      await api.post("/api/auth/register", payload);
      navigate("/login");
    } catch (err) {
      setMsg(JSON.stringify(err.response?.data || err.message));
    }
  };
  return (
    <Layout>
      <div style={{ maxWidth: 440, margin: "0 auto" }}>
        <h2>Register</h2>
        <p style={{ fontSize: 13, color: "#6b7280", marginBottom: 12 }}>Required fields are marked. Profile fields below are optional.</p>
        <GoogleSignInButton role={form.role} onSuccess={onGoogle} buttonText="signup_with" />
        <form onSubmit={submit} className="stack" style={{ marginTop: 16 }}>
          <label>
            Username <span style={{ color: "#c00" }}>*</span>
            <input
              required
              autoComplete="username"
              placeholder="Username"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
            />
          </label>
          <label>
            Email <span style={{ color: "#c00" }}>*</span>
            <input
              required
              type="email"
              autoComplete="email"
              placeholder="Email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </label>
          <label>
            Password <span style={{ color: "#c00" }}>*</span>
            <input
              required
              minLength={8}
              type="password"
              autoComplete="new-password"
              placeholder="Password (min 8 characters)"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
          </label>
          <label>
            Role <span style={{ color: "#c00" }}>*</span>
            <select required value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              <option value="creator">Creator</option>
              <option value="respondent">Respondent</option>
            </select>
          </label>
          <label>
            First name
            <input value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} placeholder="Optional" />
          </label>
          <label>
            Last name
            <input value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} placeholder="Optional" />
          </label>
          <label>
            Phone
            <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="Optional" />
          </label>
          <label>
            Organization
            <input value={form.organization} onChange={(e) => setForm({ ...form, organization: e.target.value })} placeholder="Optional" />
          </label>
          <button className="btn-primary">Register</button>
          {msg && <p className="msg msg-error">{msg}</p>}
        </form>
      </div>
    </Layout>
  );
}

function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [msg, setMsg] = useState("");
  const navigate = useNavigate();
  const { refreshAuth } = useAuth();
  const onGoogle = useCallback(() => {
    refreshAuth();
    navigate("/");
  }, [refreshAuth, navigate]);

  const submit = async (e) => {
    e.preventDefault();
    try {
      const { data } = await api.post("/api/auth/login", { username, password });
      setAuthToken(data.access);
      setRefreshToken(data.refresh);
      refreshAuth();
      navigate("/");
    } catch (err) {
      setMsg(JSON.stringify(err.response?.data || err.message));
    }
  };
  return (
    <Layout>
      <div style={{ maxWidth: 400, margin: "0 auto" }}>
        <h2>Login</h2>
        <GoogleSignInButton role="respondent" onSuccess={onGoogle} buttonText="signin_with" />
        <form onSubmit={submit} className="stack" style={{ marginTop: 16 }}>
          <label>
            Username <span style={{ color: "#c00" }}>*</span>
            <input required autoComplete="username" placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} />
          </label>
          <label>
            Password <span style={{ color: "#c00" }}>*</span>
            <input
              required
              autoComplete="current-password"
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <button className="btn-primary">Login</button>
          <p style={{ marginTop: 12, fontSize: 14 }}>
            <Link to="/forgot-password">Forgot password?</Link>
          </p>
          {msg && <p className="msg msg-error">{msg}</p>}
        </form>
      </div>
    </Layout>
  );
}

function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [msg, setMsg] = useState("");
  const [ok, setOk] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    setMsg("");
    try {
      await api.post("/api/auth/password-reset", { email });
      setOk(true);
    } catch (err) {
      setMsg(JSON.stringify(err.response?.data || err.message));
    }
  };
  return (
    <Layout>
      <div style={{ maxWidth: 400, margin: "0 auto" }}>
        <h2>Reset password</h2>
        {ok ? (
          <p>If an account exists for that email, instructions have been sent. Check the server console in development.</p>
        ) : (
          <form onSubmit={submit} className="stack">
            <input
              type="email"
              placeholder="Your account email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <button className="btn-primary">Send reset link</button>
            {msg && <p className="msg msg-error">{msg}</p>}
          </form>
        )}
        <p style={{ marginTop: 12 }}>
          <Link to="/login">Back to login</Link>
        </p>
      </div>
    </Layout>
  );
}

function ResetPasswordPage() {
  const [params] = useSearchParams();
  const uid = params.get("uid") || "";
  const token = params.get("token") || "";
  const [password, setPassword] = useState("");
  const [msg, setMsg] = useState("");
  const navigate = useNavigate();
  const submit = async (e) => {
    e.preventDefault();
    setMsg("");
    try {
      await api.post("/api/auth/password-reset/confirm", { uid, token, new_password: password });
      navigate("/login");
    } catch (err) {
      setMsg(JSON.stringify(err.response?.data || err.message));
    }
  };
  if (!uid || !token) {
    return (
      <Layout>
        <p className="msg msg-error">Invalid or missing reset link. Open the link from your email.</p>
        <Link to="/forgot-password">Request a new link</Link>
      </Layout>
    );
  }
  return (
    <Layout>
      <div style={{ maxWidth: 400, margin: "0 auto" }}>
        <h2>Set new password</h2>
        <form onSubmit={submit} className="stack">
          <input
            type="password"
            placeholder="New password (min 8 characters)"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            required
          />
          <button className="btn-primary">Update password</button>
          {msg && <p className="msg msg-error">{msg}</p>}
        </form>
      </div>
    </Layout>
  );
}

// --- Template gallery ---

function TemplatesPage() {
  const [items, setItems] = useState([]);
  const [msg, setMsg] = useState("");
  const navigate = useNavigate();
  const { isAuthed, userRole } = useAuth();
  const canDesign = ["creator", "admin"].includes(userRole || "");

  useEffect(() => {
    api.get("/api/form-templates").then(({ data }) => setItems(Array.isArray(data) ? data : [])).catch(() => setItems([]));
  }, []);

  const useTemplate = async (templateId) => {
    setMsg("");
    if (!isAuthed) {
      navigate("/login");
      return;
    }
    if (!canDesign) {
      setMsg("Use a creator or admin account to create forms from templates.");
      return;
    }
    try {
      const { data } = await api.post("/api/forms/from_template", { template_id: templateId });
      navigate(`/forms/${data.id}`);
    } catch (e) {
      setMsg(JSON.stringify(e.response?.data || e.message));
    }
  };

  return (
    <Layout>
      <h2>Form templates</h2>
      <p style={{ fontSize: 14, color: "#6b7280", marginTop: -8, marginBottom: 16 }}>
        Built-in layouts and sample questions. Each template sets a <strong>theme</strong> (colors, gradients, optional motion and fonts) you can change under Share. Bundled content is original to this project — add your own JSON files under{" "}
        <code style={{ fontSize: 12 }}>backend/apps/forms/form_template_catalog/</code> to extend the gallery.
      </p>
      {msg && <p className="msg msg-error">{msg}</p>}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
          gap: 16,
        }}
      >
        {items.map((t) => (
          <div key={t.id} className="card" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ fontSize: 11, color: "#6b7280", textTransform: "uppercase", letterSpacing: "0.04em" }}>{t.category}</div>
            <h3 style={{ margin: 0, fontSize: 17 }}>{t.title}</h3>
            <p style={{ margin: 0, fontSize: 13, color: "#4b5563", flex: 1 }}>{t.description}</p>
            <p style={{ margin: 0, fontSize: 12, color: "#9ca3af" }}>{t.question_count} questions</p>
            <button type="button" className="btn-primary btn-sm" style={{ alignSelf: "flex-start" }} onClick={() => useTemplate(t.id)}>
              Use template
            </button>
          </div>
        ))}
      </div>
      {items.length === 0 && <p style={{ color: "#9ca3af" }}>No templates loaded.</p>}
    </Layout>
  );
}

// --- Admin: user management ---

function UsersPage() {
  const { user: currentUser } = useAuth();
  const [rows, setRows] = useState([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [activeFilter, setActiveFilter] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [creating, setCreating] = useState(false);
  const [newUser, setNewUser] = useState({
    username: "",
    email: "",
    password: "",
    role: "respondent",
    first_name: "",
    last_name: "",
    phone: "",
    organization: "",
    is_active: true,
    is_staff: false,
  });
  const [editingId, setEditingId] = useState(null);
  const [editDraft, setEditDraft] = useState(null);

  const load = async (p = page) => {
    setErr("");
    try {
      const params = { page: p };
      if (search.trim()) params.search = search.trim();
      if (roleFilter) params.role = roleFilter;
      if (activeFilter === "true" || activeFilter === "false") params.is_active = activeFilter;
      const { data } = await api.get("/api/users/", { params });
      setRows(data.results || []);
      setCount(data.count ?? 0);
      setPage(p);
    } catch (e) {
      setErr(formatApiError(e));
      setRows([]);
    }
  };

  useEffect(() => {
    load(1);
  }, []);

  const totalPages = Math.max(1, Math.ceil(count / 20));

  const openEdit = (u) => {
    setEditingId(u.id);
    setEditDraft({
      username: u.username,
      email: u.email,
      role: u.role,
      first_name: u.first_name || "",
      last_name: u.last_name || "",
      phone: u.phone || "",
      organization: u.organization || "",
      is_active: u.is_active,
      is_staff: u.is_staff,
      password: "",
    });
    setMsg("");
    setErr("");
  };

  const saveEdit = async () => {
    if (!editDraft || editingId == null) return;
    setErr("");
    try {
      const payload = { ...editDraft };
      if (!payload.password || !payload.password.trim()) delete payload.password;
      await api.patch(`/api/users/${editingId}/`, payload);
      setEditingId(null);
      setEditDraft(null);
      setMsg("User updated.");
      await load(page);
    } catch (e) {
      setErr(formatApiError(e));
    }
  };

  const createUser = async (e) => {
    e.preventDefault();
    setErr("");
    try {
      const payload = { ...newUser };
      if (!currentUser?.is_superuser) delete payload.is_staff;
      await api.post("/api/users/", payload);
      setMsg("User created.");
      setCreating(false);
      setNewUser({
        username: "",
        email: "",
        password: "",
        role: "respondent",
        first_name: "",
        last_name: "",
        phone: "",
        organization: "",
        is_active: true,
        is_staff: false,
      });
      await load(1);
    } catch (e) {
      setErr(formatApiError(e));
    }
  };

  const deactivate = async (u) => {
    if (!window.confirm(`Deactivate ${u.username}? They will not be able to sign in.`)) return;
    setErr("");
    try {
      await api.delete(`/api/users/${u.id}/`);
      setMsg("User deactivated.");
      await load(page);
    } catch (e) {
      setErr(formatApiError(e));
    }
  };

  return (
    <Layout>
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>
        <div className="row" style={{ marginBottom: 16, alignItems: "center", flexWrap: "wrap", gap: 8 }}>
          <h2 style={{ margin: 0, flex: 1 }}>User management</h2>
          <button type="button" className="btn-primary btn-sm" onClick={() => { setCreating(!creating); setErr(""); }}>
            {creating ? "Close" : "Add user"}
          </button>
        </div>
        <p style={{ fontSize: 14, color: "#6b7280", marginTop: -8 }}>
          Search and filter accounts, assign roles, activate or deactivate users, and set passwords. Only application admins and superusers see this page.
        </p>
        {msg && <p className="msg">{msg}</p>}
        {err && <p className="msg msg-error">{err}</p>}

        {creating && (
          <div className="card" style={{ marginBottom: 20 }}>
            <h3 style={{ marginTop: 0 }}>New user</h3>
            <form onSubmit={createUser} className="stack" style={{ maxWidth: 480 }}>
              <input
                required
                placeholder="Username"
                value={newUser.username}
                onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
              />
              <input
                required
                type="email"
                placeholder="Email"
                value={newUser.email}
                onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
              />
              <input
                required
                type="password"
                minLength={8}
                placeholder="Password (min 8 characters)"
                value={newUser.password}
                onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
              />
              <label style={{ fontSize: 13 }}>
                Role
                <select
                  value={newUser.role}
                  onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}
                  style={{ display: "block", marginTop: 6, width: "100%", padding: "8px" }}
                >
                  {ROLE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
              <input
                placeholder="First name"
                value={newUser.first_name}
                onChange={(e) => setNewUser({ ...newUser, first_name: e.target.value })}
              />
              <input
                placeholder="Last name"
                value={newUser.last_name}
                onChange={(e) => setNewUser({ ...newUser, last_name: e.target.value })}
              />
              <input
                placeholder="Phone (optional)"
                value={newUser.phone}
                onChange={(e) => setNewUser({ ...newUser, phone: e.target.value })}
              />
              <input
                placeholder="Organization (optional)"
                value={newUser.organization}
                onChange={(e) => setNewUser({ ...newUser, organization: e.target.value })}
              />
              <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14 }}>
                <input
                  type="checkbox"
                  checked={newUser.is_active}
                  onChange={(e) => setNewUser({ ...newUser, is_active: e.target.checked })}
                />
                Active
              </label>
              {currentUser?.is_superuser && (
                <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14 }}>
                  <input
                    type="checkbox"
                    checked={newUser.is_staff}
                    onChange={(e) => setNewUser({ ...newUser, is_staff: e.target.checked })}
                  />
                  Django staff (can access /admin/)
                </label>
              )}
              <button type="submit" className="btn-primary">
                Create user
              </button>
            </form>
          </div>
        )}

        <div className="card" style={{ marginBottom: 16 }}>
          <div className="row" style={{ flexWrap: "wrap", gap: 12, alignItems: "flex-end" }}>
            <input
              placeholder="Search name, email, username…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ width: 220, padding: "8px 10px" }}
            />
            <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)} style={{ padding: "8px 10px" }}>
              <option value="">All roles</option>
              {ROLE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <select
              value={activeFilter}
              onChange={(e) => setActiveFilter(e.target.value)}
              style={{ padding: "8px 10px" }}
            >
              <option value="">Active + inactive</option>
              <option value="true">Active only</option>
              <option value="false">Inactive only</option>
            </select>
            <button type="button" className="btn-secondary btn-sm" onClick={() => load(1)}>
              Apply filters
            </button>
          </div>
        </div>

        <div style={{ overflowX: "auto" }}>
          <table className="admin-user-table">
            <thead>
              <tr>
                <th>User</th>
                <th>Role</th>
                <th>Status</th>
                <th>Joined</th>
                <th>Last login</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((u) => (
                <tr key={u.id}>
                  <td>
                    <strong>{u.username}</strong>
                    <div style={{ fontSize: 12, color: "#6b7280" }}>{u.email}</div>
                    {u.is_staff && (
                      <span style={{ fontSize: 11, color: "#7c3aed" }}>staff</span>
                    )}
                    {u.is_superuser && (
                      <span style={{ fontSize: 11, color: "#b45309" }}> superuser</span>
                    )}
                  </td>
                  <td>{u.role}</td>
                  <td>{u.is_active ? "Active" : "Inactive"}</td>
                  <td style={{ fontSize: 13, fontVariantNumeric: "tabular-nums" }}>
                    {u.date_joined ? new Date(u.date_joined).toLocaleString() : "—"}
                  </td>
                  <td style={{ fontSize: 13, fontVariantNumeric: "tabular-nums" }}>
                    {u.last_login ? new Date(u.last_login).toLocaleString() : "—"}
                  </td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    <button type="button" className="btn-secondary btn-sm" onClick={() => openEdit(u)}>
                      Edit
                    </button>
                    {u.id !== currentUser?.id && (
                      <button
                        type="button"
                        className="btn-secondary btn-sm"
                        style={{ marginLeft: 6 }}
                        onClick={() => deactivate(u)}
                      >
                        Deactivate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="row" style={{ marginTop: 16, gap: 8, alignItems: "center" }}>
            <button
              type="button"
              className="btn-secondary btn-sm"
              disabled={page <= 1}
              onClick={() => load(page - 1)}
            >
              Previous
            </button>
            <span style={{ fontSize: 14, color: "#6b7280" }}>
              Page {page} of {totalPages}
            </span>
            <button
              type="button"
              className="btn-secondary btn-sm"
              disabled={page >= totalPages}
              onClick={() => load(page + 1)}
            >
              Next
            </button>
          </div>
        )}

        {editingId != null && editDraft && (
          <div
            className="card"
            style={{
              marginTop: 24,
              position: "sticky",
              bottom: 0,
              border: "2px solid #6366f1",
            }}
          >
            <h3 style={{ marginTop: 0 }}>Edit user #{editingId}</h3>
            <div className="stack" style={{ maxWidth: 480 }}>
              <input
                required
                value={editDraft.username}
                onChange={(e) => setEditDraft({ ...editDraft, username: e.target.value })}
              />
              <input
                required
                type="email"
                value={editDraft.email}
                onChange={(e) => setEditDraft({ ...editDraft, email: e.target.value })}
              />
              <input
                type="password"
                placeholder="New password (leave blank to keep)"
                minLength={8}
                value={editDraft.password}
                onChange={(e) => setEditDraft({ ...editDraft, password: e.target.value })}
              />
              <select
                value={editDraft.role}
                onChange={(e) => setEditDraft({ ...editDraft, role: e.target.value })}
                style={{ padding: "8px 10px" }}
              >
                {ROLE_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
              <input
                placeholder="First name"
                value={editDraft.first_name}
                onChange={(e) => setEditDraft({ ...editDraft, first_name: e.target.value })}
              />
              <input
                placeholder="Last name"
                value={editDraft.last_name}
                onChange={(e) => setEditDraft({ ...editDraft, last_name: e.target.value })}
              />
              <input
                placeholder="Phone"
                value={editDraft.phone}
                onChange={(e) => setEditDraft({ ...editDraft, phone: e.target.value })}
              />
              <input
                placeholder="Organization"
                value={editDraft.organization}
                onChange={(e) => setEditDraft({ ...editDraft, organization: e.target.value })}
              />
              <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14 }}>
                <input
                  type="checkbox"
                  checked={editDraft.is_active}
                  onChange={(e) => setEditDraft({ ...editDraft, is_active: e.target.checked })}
                />
                Active
              </label>
              {currentUser?.is_superuser && (
                <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14 }}>
                  <input
                    type="checkbox"
                    checked={editDraft.is_staff}
                    onChange={(e) => setEditDraft({ ...editDraft, is_staff: e.target.checked })}
                  />
                  Django staff
                </label>
              )}
              <div className="row" style={{ gap: 8 }}>
                <button type="button" className="btn-primary" onClick={saveEdit}>
                  Save changes
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => {
                    setEditingId(null);
                    setEditDraft(null);
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
}

// --- Forms List ---

function FormsPage() {
  const { userRole } = useAuth();
  const canDesign = ["creator", "admin"].includes(userRole || "");
  const navigate = useNavigate();
  const [forms, setForms] = useState([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [msg, setMsg] = useState("");

  const load = async () => {
    try {
      const { data } = await api.get("/api/forms");
      setForms(data.results || data);
    } catch {
      setForms([]);
    }
  };

  useEffect(() => { load(); }, []);

  const createForm = async (e) => {
    e.preventDefault();
    try {
      await api.post("/api/forms", { title, description });
      setTitle("");
      setDescription("");
      await load();
      setMsg("Form created.");
    } catch (err) {
      setMsg(JSON.stringify(err.response?.data || err.message));
    }
  };

  const publish = async (id) => {
    await api.post(`/api/forms/${id}/publish`);
    await load();
  };

  const duplicateForm = async (id) => {
    try {
      const { data } = await api.post(`/api/forms/${id}/duplicate`);
      await load();
      setMsg(`Created a copy: ${data.title}`);
      navigate(`/forms/${data.id}`);
    } catch (err) {
      setMsg(JSON.stringify(err.response?.data || err.message));
    }
  };

  return (
    <Layout>
      <h2>My forms</h2>
      <p style={{ fontSize: 14, color: "#6b7280", marginTop: -8, marginBottom: 16 }}>
        Browse <Link to="/templates">Templates</Link> for ready-made forms and themes. Forms you created, were invited to, or have submitted to appear here. Open <strong>Share</strong> to change visibility (owners only), copy the link, and send invites.
      </p>
      {canDesign && (
        <form onSubmit={createForm} className="stack card" style={{ marginBottom: 20 }}>
          <input placeholder="Form title" value={title} onChange={(e) => setTitle(e.target.value)} />
          <textarea placeholder="Description (optional)" value={description} onChange={(e) => setDescription(e.target.value)} />
          <button className="btn-primary">Create Form</button>
        </form>
      )}
      {!canDesign && <p className="msg">You have respondent access. Form design is disabled.</p>}
      {msg && <p className="msg">{msg}</p>}
      <div className="stack">
        {forms.map((f) => {
          const role = f.my_role || "";
          const canOpenDesign = canDesign && ["owner", "editor"].includes(role);
          const canPublish = canDesign && ["owner", "editor"].includes(role) && f.status !== "published";
          const canSeeOwnerTools = role === "owner";
          return (
            <div key={f.id} className="form-list-card">
              <div className="form-list-info">
                <h3>{f.title}</h3>
                <p>
                  Status: <strong>{f.status}</strong> &middot; Visibility: <strong>{f.visibility || "—"}</strong> &middot;{" "}
                  {f.questions?.length || 0} questions
                  {role && (
                    <>
                      {" "}
                      &middot; <span style={{ color: "#6b7280" }}>You: {role}</span>
                    </>
                  )}
                </p>
              </div>
              <div className="row">
                {canOpenDesign && (
                  <>
                    <Link to={`/forms/${f.id}`}>
                      <button className="btn-primary btn-sm" type="button">Design</button>
                    </Link>
                    <button className="btn-secondary btn-sm" type="button" onClick={() => duplicateForm(f.id)}>
                      Duplicate
                    </button>
                  </>
                )}
                <Link to={`/fill/${f.id}`}>
                  <button className="btn-secondary btn-sm" type="button">Fill</button>
                </Link>
                <Link to={`/share/${f.id}`}>
                  <button className="btn-secondary btn-sm" type="button">Share &amp; visibility</button>
                </Link>
                {canSeeOwnerTools && (
                  <>
                    <Link to={`/analytics/${f.id}`}>
                      <button className="btn-secondary btn-sm" type="button">Analytics</button>
                    </Link>
                    <button
                      className="btn-secondary btn-sm"
                      type="button"
                      onClick={() =>
                        downloadFormExport(f.id, "csv").catch((e) => setMsg(e.message || "CSV export failed"))
                      }
                    >
                      CSV
                    </button>
                  </>
                )}
                {canPublish && (
                  <button className="btn-primary btn-sm" type="button" onClick={() => publish(f.id)}>
                    Publish
                  </button>
                )}
              </div>
            </div>
          );
        })}
        {forms.length === 0 && (
          <p style={{ color: "#9ca3af" }}>
            No forms yet. {canDesign ? "Create one above, or open a form someone shared with you after you submit." : "When you submit a form or are added as a collaborator, it will appear here."}
          </p>
        )}
      </div>
    </Layout>
  );
}

// --- Question Card (Designer) ---

function QuestionCard({ q, index, total, onUpdate, onDelete, onMove }) {
  const [options, setOptions] = useState(q.options || []);
  const isChoice = CHOICE_TYPES.includes(q.question_type);
  const v = q.validation || {};
  const isText = q.question_type === "short_text" || q.question_type === "paragraph";
  const isRating = q.question_type === "rating";
  const isDate = q.question_type === "date";

  const updateField = (field, value) => {
    onUpdate(q.id, { [field]: value });
  };

  const setValidation = (patch) => {
    onUpdate(q.id, { validation: mergeValidationPatch(q.validation, patch) });
  };

  const addOption = () => {
    const next = [...options, `Option ${options.length + 1}`];
    setOptions(next);
    onUpdate(q.id, { options: next });
  };

  const changeOption = (i, val) => {
    const next = [...options];
    next[i] = val;
    setOptions(next);
    onUpdate(q.id, { options: next });
  };

  const removeOption = (i) => {
    const next = options.filter((_, j) => j !== i);
    setOptions(next);
    onUpdate(q.id, { options: next });
  };

  const typeLabel = QUESTION_TYPES.find((t) => t.value === q.question_type)?.label || q.question_type;

  return (
    <div className="question-card google-card" style={{ opacity: q.disabled ? 0.72 : 1 }}>
      <div className="question-card-header google-question-header">
        <input
          defaultValue={q.text}
          placeholder="Untitled question"
          onBlur={(e) => updateField("text", e.target.value)}
          style={{ flex: 1, fontSize: 20 }}
        />
        <div className="question-card-actions">
          <button className="btn-icon" disabled={index === 0} onClick={() => onMove(q.id, "up")} title="Move up">
            &#9650;
          </button>
          <button className="btn-icon" disabled={index === total - 1} onClick={() => onMove(q.id, "down")} title="Move down">
            &#9660;
          </button>
          <button className="btn-icon" onClick={() => onDelete(q.id)} title="Delete" style={{ color: "#ef4444" }}>
            &#10005;
          </button>
        </div>
      </div>

      <div className="question-card-meta">
        <span className="badge badge-type">{typeLabel}</span>
        {q.required && <span className="badge badge-required">Required</span>}
        {q.disabled && (
          <span className="badge" style={{ background: "#fef3c7", color: "#92400e", border: "1px solid #fcd34d" }}>
            Disabled (hidden)
          </span>
        )}
        <label style={{ display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={q.required}
            onChange={(e) => updateField("required", e.target.checked)}
            style={{ width: "auto" }}
          />
          Required
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={!!q.disabled}
            onChange={(e) => updateField("disabled", e.target.checked)}
            style={{ width: "auto" }}
          />
          Disabled
        </label>
        <select
          value={q.question_type}
          onChange={(e) => updateField("question_type", e.target.value)}
          style={{ width: "auto", padding: "4px 8px", fontSize: 12 }}
        >
          {QUESTION_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
      </div>

      {isChoice && (
        <div className="options-editor google-options">
          {options.map((opt, i) => (
            <div key={i} className="option-row">
              <span style={{ color: "#9ca3af", fontSize: 12, width: 20 }}>◯</span>
              <input value={opt} onChange={(e) => changeOption(i, e.target.value)} placeholder={`Option ${i + 1}`} />
              <button className="btn-icon" onClick={() => removeOption(i)} title="Remove option" style={{ color: "#ef4444" }}>
                &#10005;
              </button>
            </div>
          ))}
          <button type="button" className="btn-secondary btn-sm" onClick={addOption} style={{ marginTop: 4 }}>
            + Add Option
          </button>
        </div>
      )}

      {(isText || isRating || isDate) && (
        <div className="question-validation-panel">
          <p className="question-validation-title">Response validation (optional)</p>
          <p className="question-validation-hint">
            Rules apply when the form is published. Presets use common patterns; you can add a custom regex for stricter checks.
          </p>

          {isText && (
            <div className="question-validation-grid">
              <label className="question-validation-field">
                Format preset
                <select
                  value={v.format || ""}
                  onChange={(e) => setValidation({ format: e.target.value || undefined })}
                >
                  {VALIDATION_FORMATS.map((o) => (
                    <option key={o.value || "none"} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </label>
              <label className="question-validation-field">
                Min length
                <input
                  type="number"
                  min={0}
                  placeholder="—"
                  value={v.min_length ?? ""}
                  onChange={(e) => {
                    const raw = e.target.value;
                    if (raw === "") {
                      setValidation({ min_length: undefined });
                      return;
                    }
                    const n = parseInt(raw, 10);
                    setValidation({ min_length: Number.isNaN(n) ? undefined : n });
                  }}
                />
              </label>
              <label className="question-validation-field">
                Max length
                <input
                  type="number"
                  min={0}
                  placeholder="—"
                  value={v.max_length ?? ""}
                  onChange={(e) => {
                    const raw = e.target.value;
                    if (raw === "") {
                      setValidation({ max_length: undefined });
                      return;
                    }
                    const n = parseInt(raw, 10);
                    setValidation({ max_length: Number.isNaN(n) ? undefined : n });
                  }}
                />
              </label>
              <label className="question-validation-field span-2">
                Custom regex (optional)
                <input
                  type="text"
                  placeholder="e.g. ^[A-Z]{2}-\\d+$"
                  value={v.pattern || ""}
                  onChange={(e) => setValidation({ pattern: e.target.value || undefined })}
                />
              </label>
            </div>
          )}

          {isRating && (
            <div className="question-validation-grid">
              <label className="question-validation-field">
                Minimum value
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={v.min ?? ""}
                  placeholder="1"
                  onChange={(e) => {
                    const raw = e.target.value;
                    if (raw === "") {
                      setValidation({ min: undefined });
                      return;
                    }
                    const n = parseInt(raw, 10);
                    setValidation({ min: Number.isNaN(n) ? undefined : n });
                  }}
                />
              </label>
              <label className="question-validation-field">
                Maximum value
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={v.max ?? ""}
                  placeholder="5"
                  onChange={(e) => {
                    const raw = e.target.value;
                    if (raw === "") {
                      setValidation({ max: undefined });
                      return;
                    }
                    const n = parseInt(raw, 10);
                    setValidation({ max: Number.isNaN(n) ? undefined : n });
                  }}
                />
              </label>
            </div>
          )}

          {isDate && (
            <div className="question-validation-grid">
              <label className="question-validation-field">
                Earliest date
                <input
                  type="date"
                  value={v.min_date || ""}
                  onChange={(e) => setValidation({ min_date: e.target.value || undefined })}
                />
              </label>
              <label className="question-validation-field">
                Latest date
                <input
                  type="date"
                  value={v.max_date || ""}
                  onChange={(e) => setValidation({ max_date: e.target.value || undefined })}
                />
              </label>
            </div>
          )}
        </div>
      )}

      <div className="google-bottom-actions">
        <button type="button" className="btn-icon" disabled={index === 0} onClick={() => onMove(q.id, "up")} title="Move up">
          ↑
        </button>
        <button type="button" className="btn-icon" disabled={index === total - 1} onClick={() => onMove(q.id, "down")} title="Move down">
          ↓
        </button>
        <button type="button" className="btn-icon" onClick={() => onDelete(q.id)} title="Delete question" style={{ color: "#ef4444" }}>
          🗑
        </button>
      </div>
    </div>
  );
}

// --- Visibility (owner-only edit; shown on Questions + Share) ---

function VisibilityEditor({ formId, form, onReload, onBanner, variant = "card" }) {
  const isOwner = form.my_role === "owner";
  const [visSaving, setVisSaving] = useState(false);

  const updateVisibility = async (e) => {
    const value = e.target.value;
    setVisSaving(true);
    try {
      await api.patch(`/api/forms/${formId}`, { visibility: value });
      await onReload();
      onBanner?.("Visibility saved.", false);
    } catch (err) {
      const d = err.response?.data;
      const msg =
        (d?.visibility && (Array.isArray(d.visibility) ? d.visibility[0] : d.visibility)) ||
        d?.detail ||
        JSON.stringify(d || err.message);
      onBanner?.(msg, true);
    } finally {
      setVisSaving(false);
    }
  };

  const v = form.visibility || "public";

  if (variant === "inline") {
    return (
      <span style={{ display: "inline-flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <span>
          Visibility: <strong>{v}</strong>
        </span>
        {isOwner ? (
          <label style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 13 }}>
            <select
              value={v}
              disabled={visSaving}
              onChange={updateVisibility}
              style={{ padding: "4px 8px", fontSize: 13, maxWidth: 200 }}
              aria-label="Form visibility"
            >
              <option value="public">Public</option>
              <option value="private">Private</option>
            </select>
          </label>
        ) : (
          <span style={{ fontSize: 12, color: "#6b7280" }}>(only the owner can change this)</span>
        )}
      </span>
    );
  }

  if (!isOwner) return null;

  return (
    <div className="card" style={{ borderColor: "#c4b5fd" }}>
      <p className="sidebar-title">Visibility</p>
      <p style={{ fontSize: 12, color: "#6b7280", margin: "0 0 8px" }}>
        <strong>Public</strong> — anyone with the link can open the form (when published).{" "}
        <strong>Private</strong> — only people you share the link with, collaborators, and respondents who already have access.
      </p>
      <label style={{ display: "block", fontSize: 13 }}>
        Who can access via link
        <select
          value={v}
          disabled={visSaving}
          onChange={updateVisibility}
          style={{ display: "block", marginTop: 6, maxWidth: 320, padding: "8px 10px", fontSize: 14 }}
          aria-label="Form visibility"
        >
          <option value="public">Public</option>
          <option value="private">Private</option>
        </select>
      </label>
    </div>
  );
}

function ThemeAppearanceControls({ formId, form, onReload, onBanner }) {
  const [presetId, setPresetId] = useState("custom");
  const [motion, setMotion] = useState("");
  const [fontFamily, setFontFamily] = useState("");
  const [darkMode, setDarkMode] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const a = form?.appearance && typeof form.appearance === "object" ? form.appearance : {};
    setMotion(a.animation ?? "");
    setFontFamily(a.fontFamily ?? "");
    setDarkMode(a.darkMode === true);
  }, [formId, form?.appearance]);

  const apply = async (appearance) => {
    setSaving(true);
    try {
      await api.patch(`/api/forms/${formId}`, { appearance });
      await onReload();
      onBanner?.("Theme updated.", false);
    } catch (err) {
      onBanner?.(err.response?.data?.detail || JSON.stringify(err.response?.data || err.message), true);
    } finally {
      setSaving(false);
    }
  };

  const saveMotionAndType = async () => {
    const prev = form?.appearance && typeof form.appearance === "object" ? { ...form.appearance } : {};
    const next = { ...prev };
    if (!motion || motion === "none") delete next.animation;
    else next.animation = motion;
    if (!fontFamily.trim()) delete next.fontFamily;
    else next.fontFamily = fontFamily.trim();
    if (darkMode) next.darkMode = true;
    else delete next.darkMode;
    setSaving(true);
    try {
      await api.patch(`/api/forms/${formId}`, { appearance: next });
      await onReload();
      onBanner?.("Look & motion saved.", false);
    } catch (err) {
      onBanner?.(err.response?.data?.detail || JSON.stringify(err.response?.data || err.message), true);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="stack" style={{ gap: 10 }}>
      <label style={{ fontSize: 13 }}>
        Preset
        <select
          value={presetId}
          onChange={(e) => setPresetId(e.target.value)}
          style={{ display: "block", marginTop: 4, maxWidth: 280, padding: "6px 8px" }}
        >
          <option value="custom">Custom (no change)</option>
          {THEME_PRESETS.map((p) => (
            <option key={p.id} value={p.id}>{p.label}</option>
          ))}
        </select>
      </label>
      <button
        type="button"
        className="btn-primary btn-sm"
        disabled={saving || presetId === "custom"}
        onClick={() => {
          const p = THEME_PRESETS.find((x) => x.id === presetId);
          if (p) apply(p.appearance);
        }}
      >
        {saving ? "Saving…" : "Apply theme"}
      </button>
      <label style={{ fontSize: 13 }}>
        Page animation
        <select
          value={motion || "none"}
          onChange={(e) => setMotion(e.target.value === "none" ? "" : e.target.value)}
          style={{ display: "block", marginTop: 4, maxWidth: 280, padding: "6px 8px" }}
        >
          <option value="none">None</option>
          <option value="fadeIn">Fade in</option>
          <option value="rise">Rise</option>
          <option value="pulse">Pulse shadow</option>
          <option value="glow">Glow (neon)</option>
        </select>
      </label>
      <label style={{ fontSize: 13 }}>
        Font stack (CSS)
        <input
          type="text"
          value={fontFamily}
          onChange={(e) => setFontFamily(e.target.value)}
          placeholder="'Segoe UI', system-ui, sans-serif"
          style={{ display: "block", marginTop: 4, width: "100%", maxWidth: 320, padding: "6px 8px", fontSize: 13 }}
        />
      </label>
      <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, cursor: "pointer" }}>
        <input type="checkbox" checked={darkMode} onChange={(e) => setDarkMode(e.target.checked)} />
        Dark card (light text on dark backgrounds)
      </label>
      <button type="button" className="btn-secondary btn-sm" disabled={saving} onClick={saveMotionAndType}>
        {saving ? "Saving…" : "Save motion & typography"}
      </button>
    </div>
  );
}

// --- Collaborators (owner): list users with checkboxes + role ---

function CollaboratorPicker({ formId, onReload, onBanner }) {
  const [list, setList] = useState([]);
  const [candidates, setCandidates] = useState([]);
  const [candidatesLoading, setCandidatesLoading] = useState(true);
  const [filterQ, setFilterQ] = useState("");
  const [selected, setSelected] = useState(() => new Map());
  const [role, setRole] = useState("viewer");
  const [adding, setAdding] = useState(false);

  const loadList = useCallback(async () => {
    try {
      const { data } = await api.get(`/api/forms/${formId}/collaborators`);
      setList(Array.isArray(data) ? data : []);
    } catch {
      setList([]);
    }
  }, [formId]);

  const loadCandidates = useCallback(async () => {
    setCandidatesLoading(true);
    try {
      const { data } = await api.get(`/api/forms/${formId}/collaborator_candidates`);
      setCandidates(Array.isArray(data?.results) ? data.results : []);
    } catch {
      setCandidates([]);
    } finally {
      setCandidatesLoading(false);
    }
  }, [formId]);

  useEffect(() => {
    loadList();
  }, [loadList]);

  useEffect(() => {
    loadCandidates();
  }, [loadCandidates]);

  const filteredCandidates = useMemo(() => {
    const q = filterQ.trim().toLowerCase();
    if (!q) return candidates;
    return candidates.filter((row) => {
      const hay = `${row.username} ${row.email || ""} ${row.display_name || ""} ${row.first_name || ""} ${row.last_name || ""}`.toLowerCase();
      return hay.includes(q);
    });
  }, [candidates, filterQ]);

  const toggleRow = (row) => {
    setSelected((prev) => {
      const next = new Map(prev);
      if (next.has(row.id)) next.delete(row.id);
      else next.set(row.id, row);
      return next;
    });
  };

  const addSelected = async () => {
    if (selected.size === 0) return;
    setAdding(true);
    try {
      for (const row of selected.values()) {
        await api.post(`/api/forms/${formId}/collaborators`, { username: row.username, role });
      }
      setSelected(new Map());
      setFilterQ("");
      await loadList();
      await loadCandidates();
      await onReload();
      onBanner?.("Collaborator(s) added.", false);
    } catch (err) {
      onBanner?.(formatApiError(err), true);
    } finally {
      setAdding(false);
    }
  };

  return (
    <div className="gf-collab-picker">
      {list.length > 0 && (
        <div className="gf-collab-current">
          <p style={{ fontSize: 12, color: "#6b7280", margin: "0 0 8px" }}>Current collaborators</p>
          <ul className="gf-collab-list">
            {list.map((c) => (
              <li key={c.id} className="gf-collab-list-item">
                <img className="gf-collab-avatar" src={c.avatar_url} alt="" width={36} height={36} />
                <div className="gf-collab-list-text">
                  <span className="gf-collab-name">{c.display_name || c.username}</span>
                  <span className="gf-collab-sub">{c.username}</span>
                </div>
                <span className={`gf-collab-role-badge gf-collab-role-${c.role}`}>{c.role}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <p style={{ fontSize: 12, color: "#6b7280", margin: "0 0 8px" }}>Assign collaborators</p>
      <p style={{ fontSize: 12, color: "#6b7280", margin: "0 0 8px" }}>
        Select users below. Use the filter to narrow the list. Up to 200 users are listed (excluding you and people already on this form).
      </p>

      <div className="gf-collab-candidate-wrap">
        <input
          className="gf-collab-search-input"
          type="search"
          autoComplete="off"
          placeholder="Filter list by name, username, or email…"
          value={filterQ}
          onChange={(e) => setFilterQ(e.target.value)}
          aria-label="Filter users"
        />
        {candidatesLoading && <div className="gf-collab-search-hint">Loading users…</div>}
        {!candidatesLoading && candidates.length === 0 && (
          <div className="gf-collab-search-hint">No other users to add. Register more accounts or check with your admin.</div>
        )}
        {!candidatesLoading && filteredCandidates.length > 0 && (
          <div className="gf-collab-candidate-list" role="list">
            {filteredCandidates.map((row) => {
              const checked = selected.has(row.id);
              return (
                <label key={row.id} className={`gf-collab-row${checked ? " is-selected" : ""}`}>
                  <input type="checkbox" checked={checked} onChange={() => toggleRow(row)} />
                  <img className="gf-collab-avatar" src={row.avatar_url} alt="" width={40} height={40} />
                  <div className="gf-collab-row-text">
                    <span className="gf-collab-name">{row.display_name || row.username}</span>
                    <span className="gf-collab-sub">{row.email || row.username}</span>
                  </div>
                </label>
              );
            })}
          </div>
        )}
        {!candidatesLoading && candidates.length > 0 && filteredCandidates.length === 0 && (
          <div className="gf-collab-search-hint">No users match this filter.</div>
        )}
      </div>

      <div className="gf-collab-actions row" style={{ marginTop: 10, alignItems: "center", flexWrap: "wrap", gap: 8 }}>
        <label style={{ fontSize: 13 }}>
          Role for selected
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            style={{ display: "block", marginTop: 4, padding: "6px 8px", fontSize: 13 }}
          >
            <option value="viewer">Viewer</option>
            <option value="editor">Editor</option>
          </select>
        </label>
        <button type="button" className="btn-primary btn-sm" disabled={adding || selected.size === 0} onClick={addSelected}>
          {adding ? "Adding…" : `Add selected (${selected.size})`}
        </button>
      </div>
    </div>
  );
}

// --- Share panel (used on form list route and designer Share tab) ---

function FormSharePanel({ formId, form, onReload, onBanner }) {
  const { userRole } = useAuth();
  const canDesign = ["creator", "admin"].includes(userRole || "");
  const myRole = form.my_role || "";
  const canEditInviteAndPublish = canDesign && ["owner", "editor"].includes(myRole);
  const canAddCollaborators = canDesign && myRole === "owner";

  const [inviteText, setInviteText] = useState("");
  const [inviteNote, setInviteNote] = useState("");
  const [inviteMsg, setInviteMsg] = useState("");
  const [inviteSending, setInviteSending] = useState(false);
  const [copyLinkMsg, setCopyLinkMsg] = useState("");
  const [scheduleDraft, setScheduleDraft] = useState({ opens: "", closes: "", thankYou: "" });
  const [scheduleSaving, setScheduleSaving] = useState(false);
  const [scheduleMsg, setScheduleMsg] = useState("");

  const fillUrl = `${window.location.origin}/fill/${formId}`;

  useEffect(() => {
    setScheduleDraft({
      opens: isoToDatetimeLocal(form.opens_at),
      closes: isoToDatetimeLocal(form.closes_at),
      thankYou: form.thank_you_message ?? "",
    });
  }, [formId, form.opens_at, form.closes_at, form.thank_you_message]);

  const parseInviteEmails = (text) => {
    const raw = text.split(/[\n,;]+/).map((s) => s.trim()).filter(Boolean);
    return [...new Set(raw)];
  };

  const publishForm = async () => {
    try {
      await api.post(`/api/forms/${formId}/publish`);
      await onReload();
      onBanner?.("Form published.", false);
    } catch (err) {
      onBanner?.(err.response?.data?.detail || JSON.stringify(err.response?.data || err.message), true);
    }
  };

  const copyFillLink = async () => {
    setCopyLinkMsg("");
    try {
      await navigator.clipboard.writeText(fillUrl);
      setCopyLinkMsg("Link copied to clipboard.");
      setTimeout(() => setCopyLinkMsg(""), 2500);
    } catch {
      setCopyLinkMsg("Could not copy automatically — select the link and copy manually.");
    }
  };

  const sendInvites = async (e) => {
    e.preventDefault();
    setInviteMsg("");
    const emails = parseInviteEmails(inviteText);
    if (emails.length === 0) {
      setInviteMsg("Add at least one email address.");
      return;
    }
    setInviteSending(true);
    try {
      const { data } = await api.post(`/api/forms/${formId}/invite`, {
        emails,
        message: inviteNote.trim(),
      });
      setInviteMsg(`Sent ${data.sent} of ${data.total} invitation(s).${data.failed ? ` ${data.failed} failed.` : ""}`);
      if (data.errors?.length) setInviteMsg((m) => `${m} Check server logs for details.`);
      setInviteText("");
      setInviteNote("");
    } catch (err) {
      setInviteMsg(err.response?.data?.detail || JSON.stringify(err.response?.data || err.message));
    } finally {
      setInviteSending(false);
    }
  };

  return (
    <div className="gf-share-panel">
      <VisibilityEditor formId={formId} form={form} onReload={onReload} onBanner={onBanner} variant="card" />

      {canEditInviteAndPublish && (
        <div className="card">
          <p className="sidebar-title">Schedule &amp; confirmation</p>
          <p style={{ fontSize: 12, color: "#6b7280", margin: "0 0 8px" }}>
            Optional window when responses are accepted. After submit, respondents see your thank-you message (or the default).
          </p>
          <div className="stack" style={{ gap: 10 }}>
            <label>
              Opens at (your browser&apos;s local time)
              <input
                type="datetime-local"
                value={scheduleDraft.opens}
                onChange={(e) => setScheduleDraft((s) => ({ ...s, opens: e.target.value }))}
                style={{ display: "block", marginTop: 4, width: "100%", maxWidth: 280 }}
              />
            </label>
            <label>
              Closes at (local time)
              <input
                type="datetime-local"
                value={scheduleDraft.closes}
                onChange={(e) => setScheduleDraft((s) => ({ ...s, closes: e.target.value }))}
                style={{ display: "block", marginTop: 4, width: "100%", maxWidth: 280 }}
              />
            </label>
            <label>
              Thank-you message (after submit)
              <textarea
                rows={3}
                placeholder="Thanks — your response has been received."
                value={scheduleDraft.thankYou}
                onChange={(e) => setScheduleDraft((s) => ({ ...s, thankYou: e.target.value }))}
                style={{ display: "block", marginTop: 4, width: "100%", fontFamily: "inherit", fontSize: 13 }}
              />
            </label>
            {scheduleMsg && <p className="msg msg-error" style={{ margin: 0 }}>{scheduleMsg}</p>}
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              <button
                type="button"
                className="btn-primary btn-sm"
                disabled={scheduleSaving}
                onClick={async () => {
                  setScheduleSaving(true);
                  setScheduleMsg("");
                  try {
                    await api.patch(`/api/forms/${formId}`, {
                      opens_at: datetimeLocalToIso(scheduleDraft.opens),
                      closes_at: datetimeLocalToIso(scheduleDraft.closes),
                      thank_you_message: scheduleDraft.thankYou,
                    });
                    await onReload();
                    onBanner?.("Schedule and confirmation message saved.", false);
                  } catch (err) {
                    setScheduleMsg(err.response?.data?.detail || JSON.stringify(err.response?.data || err.message));
                  } finally {
                    setScheduleSaving(false);
                  }
                }}
              >
                {scheduleSaving ? "Saving…" : "Save schedule & message"}
              </button>
              <button
                type="button"
                className="btn-secondary btn-sm"
                disabled={scheduleSaving}
                onClick={async () => {
                  setScheduleDraft((s) => ({ ...s, opens: "", closes: "" }));
                  setScheduleSaving(true);
                  setScheduleMsg("");
                  try {
                    await api.patch(`/api/forms/${formId}`, { opens_at: null, closes_at: null });
                    await onReload();
                    onBanner?.("Schedule dates cleared.", false);
                  } catch (err) {
                    setScheduleMsg(err.response?.data?.detail || JSON.stringify(err.response?.data || err.message));
                  } finally {
                    setScheduleSaving(false);
                  }
                }}
              >
                Clear schedule dates
              </button>
            </div>
          </div>
        </div>
      )}

      {canEditInviteAndPublish && (
        <div className="card">
          <p className="sidebar-title">Look &amp; theme</p>
          <p style={{ fontSize: 12, color: "#6b7280", margin: "0 0 8px" }}>
            Preset color schemes for the fill page (CSS variables). Templates set an initial theme; adjust here anytime.
          </p>
          <ThemeAppearanceControls formId={formId} form={form} onReload={onReload} onBanner={onBanner} />
        </div>
      )}

      <div className="card">
        <p className="sidebar-title">Publish &amp; link</p>
        <p style={{ fontSize: 13, color: "#6b7280", marginBottom: 12 }}>
          Your role: <strong>{myRole || "—"}</strong>
          <span style={{ display: "block", marginTop: 6 }}>
            Status: <strong>{form.status}</strong>
          </span>
          {form.status !== "published" && canEditInviteAndPublish && (
            <span style={{ display: "block", marginTop: 8 }}>
              Publishing makes the form available to respondents and enables email invitations.
            </span>
          )}
        </p>
        {canEditInviteAndPublish && form.status !== "published" && (
          <button type="button" className="btn-primary btn-sm" onClick={publishForm}>
            Publish form
          </button>
        )}
        <div style={{ marginTop: 8 }}>
          <label style={{ fontSize: 12, color: "#6b7280" }}>Shareable link (respondents fill this form)</label>
          <div className="row" style={{ marginTop: 6, alignItems: "center", flexWrap: "wrap", gap: 8 }}>
            <input readOnly value={fillUrl} style={{ flex: 1, minWidth: 200, fontSize: 13 }} />
            <button type="button" className="btn-secondary btn-sm" onClick={copyFillLink}>
              Copy link
            </button>
          </div>
          {copyLinkMsg && <p style={{ fontSize: 12, color: "#059669", marginTop: 6 }}>{copyLinkMsg}</p>}
          <div style={{ marginTop: 16 }}>
            <p style={{ fontSize: 12, color: "#6b7280", margin: "0 0 8px" }}>QR code (scan to open fill page)</p>
            <div style={{ background: "#fff", padding: 8, display: "inline-block", borderRadius: 8, border: "1px solid #e5e7eb" }}>
              <QRCodeSVG value={fillUrl} size={140} level="M" includeMargin />
            </div>
          </div>
        </div>
        {!canEditInviteAndPublish && myRole === "respondent" && (
          <p style={{ fontSize: 12, color: "#6b7280", marginTop: 12 }}>
            Copy the link above to share with others. Only editors can send email invitations from FastForms.
          </p>
        )}
      </div>

      {canEditInviteAndPublish && (
        <div className="card gf-collab-card">
          <p className="sidebar-title">Email invitations</p>
          <p style={{ fontSize: 11, color: "#6b7280", margin: "0 0 8px" }}>
            Send a link to this form by email. The form must be <strong>published</strong>. One address per line, or separate with commas or semicolons.
          </p>
          <form onSubmit={sendInvites} className="stack">
            <textarea
              rows={5}
              placeholder={"friend1@example.com\nfriend2@example.com"}
              value={inviteText}
              onChange={(e) => setInviteText(e.target.value)}
              style={{ fontSize: 13, fontFamily: "inherit" }}
            />
            <input
              placeholder="Optional note (shown in the email)"
              value={inviteNote}
              onChange={(e) => setInviteNote(e.target.value)}
            />
            <button className="btn-primary btn-sm" type="submit" disabled={inviteSending || form.status !== "published"}>
              {inviteSending ? "Sending…" : "Send invitations"}
            </button>
            {form.status !== "published" && (
              <p style={{ fontSize: 11, color: "#b45309" }}>Publish the form above to enable invitations.</p>
            )}
            {inviteMsg && (
              <p style={{ fontSize: 12, color: inviteMsg.startsWith("Sent") ? "#059669" : "#b91c1c" }}>{inviteMsg}</p>
            )}
          </form>
        </div>
      )}

      {canAddCollaborators && (
        <div className="card gf-collab-card">
          <p className="sidebar-title">Collaborators</p>
          <p style={{ fontSize: 11, color: "#6b7280", margin: "0 0 8px" }}>
            Search by name, username, or email. Tick one or more people, pick a role, then add.
          </p>
          <CollaboratorPicker formId={formId} onReload={onReload} onBanner={onBanner} />
        </div>
      )}
    </div>
  );
}

function FormSharePage() {
  const { formId } = useParams();
  const [form, setForm] = useState(null);
  const [err, setErr] = useState("");
  const navigate = useNavigate();

  const load = async () => {
    setErr("");
    try {
      const { data } = await api.get(`/api/forms/${formId}`);
      setForm(data);
    } catch (e) {
      setForm(null);
      setErr(e.response?.data?.detail || "Form not found or you do not have access.");
    }
  };

  useEffect(() => {
    load();
  }, [formId]);

  if (err) {
    return (
      <Layout>
        <p className="msg msg-error">{err}</p>
        <button type="button" className="btn-secondary btn-sm" onClick={() => navigate("/")}>Back to forms</button>
      </Layout>
    );
  }

  if (!form) return <Layout><p>Loading...</p></Layout>;

  return (
    <Layout>
      <div style={{ maxWidth: 680, margin: "0 auto" }}>
        <div className="row" style={{ marginBottom: 16, alignItems: "center", flexWrap: "wrap", gap: 8 }}>
          <button type="button" className="btn-secondary btn-sm" onClick={() => navigate("/")}>Back</button>
          <h2 style={{ margin: 0, fontSize: 20 }}>Share: {form.title}</h2>
        </div>
        <FormSharePanel formId={formId} form={form} onReload={load} />
      </div>
    </Layout>
  );
}

// --- Form Designer Page ---

function FormEditorPage() {
  const { formId } = useParams();
  const [searchParams] = useSearchParams();
  const { userRole } = useAuth();
  const canUseAi = ["creator", "admin"].includes(userRole || "");
  const [form, setForm] = useState(null);
  const [editorTab, setEditorTab] = useState(() => (searchParams.get("tab") === "share" ? "share" : "questions"));
  const [saving, setSaving] = useState(false);
  const [designerMsg, setDesignerMsg] = useState("");
  const [designerErr, setDesignerErr] = useState("");
  const [designerErrTimeout, setDesignerErrTimeout] = useState(false);
  const [aiEnabled, setAiEnabled] = useState(false);
  const [aiHealthLoading, setAiHealthLoading] = useState(true);
  const [aiOllamaModel, setAiOllamaModel] = useState("");
  const [aiOllamaTimeoutSec, setAiOllamaTimeoutSec] = useState(300);
  const [aiPrompt, setAiPrompt] = useState("");
  const [aiBusy, setAiBusy] = useState(false);
  const navigate = useNavigate();

  const shareBanner = (msg, isError) => {
    if (isError) {
      setDesignerErr(msg);
      setDesignerMsg("");
    } else {
      setDesignerMsg(msg);
      setDesignerErr("");
    }
  };

  const load = async () => {
    const { data } = await api.get(`/api/forms/${formId}`);
    setForm(data);
  };

  useEffect(() => { load(); }, [formId]);

  useEffect(() => {
    let cancelled = false;
    setAiHealthLoading(true);
    api
      .get("/api/ai/health")
      .then(({ data }) => {
        if (cancelled) return;
        setAiEnabled(!!data.llm_enabled);
        if (data.llm_enabled) {
          setAiOllamaModel(typeof data.ollama_model === "string" ? data.ollama_model : "");
          const t = data.ollama_timeout_sec;
          setAiOllamaTimeoutSec(typeof t === "number" && t > 0 ? t : 300);
        } else {
          setAiOllamaModel("");
          setAiOllamaTimeoutSec(300);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAiEnabled(false);
          setAiOllamaModel("");
          setAiOllamaTimeoutSec(300);
        }
      })
      .finally(() => {
        if (!cancelled) setAiHealthLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [formId]);

  const applyAiDraft = async () => {
    const p = aiPrompt.trim();
    if (!p) {
      setDesignerErr("Describe the form you want in the box below.");
      return;
    }
    setAiBusy(true);
    setDesignerErr("");
    setDesignerErrTimeout(false);
    const suggestTimeoutMs = (Math.max(Number(aiOllamaTimeoutSec) || 300, 60) + 30) * 1000;
    try {
      const { data } = await api.post("/api/ai/suggest_form", { prompt: p }, { timeout: suggestTimeoutMs });
      const qList = data.questions || [];
      await api.patch(`/api/forms/${formId}`, { title: data.title, description: data.description || "" });
      for (const q of qList) {
        const vRaw = q.validation;
        const validation =
          vRaw && typeof vRaw === "object" && !Array.isArray(vRaw) ? { ...vRaw } : {};
        await api.post(`/api/forms/${formId}/questions`, {
          text: q.text || "Question",
          question_type: q.question_type || "short_text",
          required: !!q.required,
          disabled: false,
          options: Array.isArray(q.options) ? q.options : [],
          validation,
        });
      }
      await load();
      setAiPrompt("");
      const n = qList.length;
      setDesignerMsg(
        n === 0
          ? "Updated title and description from AI. No questions were returned — add some manually or try again."
          : `Updated title and description · added ${n} question${n === 1 ? "" : "s"}. Review and edit below.`
      );
      setTimeout(() => setDesignerMsg(""), 8000);
    } catch (err) {
      const msg = formatApiError(err);
      setDesignerErr(msg);
      setDesignerErrTimeout(/timeout|did not respond in time|Read timed out|ETIMEDOUT|ECONNABORTED/i.test(msg));
    } finally {
      setAiBusy(false);
    }
  };

  const addQuestion = async (type) => {
    setSaving(true);
    setDesignerErr("");
    try {
      await api.post(`/api/forms/${formId}/questions`, {
        text: "Untitled question",
        question_type: type,
        required: false,
        disabled: false,
        order_index: (form?.questions?.length || 0),
        options: CHOICE_TYPES.includes(type) ? ["Option 1", "Option 2"] : [],
      });
      await load();
      setDesignerMsg("Question added.");
      setTimeout(() => setDesignerMsg(""), 1200);
    } catch (err) {
      setDesignerErr(err.response?.data?.detail || JSON.stringify(err.response?.data || err.message));
    } finally {
      setSaving(false);
    }
  };

  const updateQuestion = async (qId, patch) => {
    try {
      await api.put(`/api/questions/${qId}`, patch);
      await load();
    } catch (err) {
      setDesignerErr(err.response?.data?.detail || JSON.stringify(err.response?.data || err.message));
    }
  };

  const deleteQuestion = async (qId) => {
    try {
      await api.delete(`/api/questions/${qId}`);
      await load();
    } catch (err) {
      setDesignerErr(err.response?.data?.detail || JSON.stringify(err.response?.data || err.message));
    }
  };

  const moveQuestion = async (qId, direction) => {
    const questions = form.questions || [];
    const idx = questions.findIndex((q) => q.id === qId);
    if (idx < 0) return;
    const swapIdx = direction === "up" ? idx - 1 : idx + 1;
    if (swapIdx < 0 || swapIdx >= questions.length) return;
    const ids = questions.map((q) => q.id);
    [ids[idx], ids[swapIdx]] = [ids[swapIdx], ids[idx]];
    try {
      await api.put(`/api/forms/${formId}/reorder_questions`, { question_ids: ids });
      await load();
    } catch (err) {
      setDesignerErr(err.response?.data?.detail || JSON.stringify(err.response?.data || err.message));
    }
  };

  if (!form) return <Layout><p>Loading...</p></Layout>;

  const questions = form.questions || [];

  return (
    <Layout>
      <div className="gf-top-shell">
        <div className="gf-top-inner">
          <input
            className="gf-form-title-input"
            defaultValue={form.title}
            onBlur={(e) => api.put(`/api/forms/${formId}`, { title: e.target.value || "Untitled form" }).then(load)}
          />
          <div className="row">
            <button className="btn-secondary btn-sm" onClick={() => navigate("/")}>Back</button>
            <Link to={`/fill/${form.id}`}><button className="btn-secondary btn-sm">Preview</button></Link>
          </div>
        </div>
        <div className="gf-tabs">
          <button
            type="button"
            className={`gf-tab${editorTab === "questions" ? " active" : ""}`}
            onClick={() => setEditorTab("questions")}
          >
            Questions
          </button>
          <button
            type="button"
            className={`gf-tab${editorTab === "responses" ? " active" : ""}`}
            onClick={() => setEditorTab("responses")}
          >
            Responses
          </button>
          <button
            type="button"
            className={`gf-tab${editorTab === "share" ? " active" : ""}`}
            onClick={() => setEditorTab("share")}
          >
            Share &amp; visibility
          </button>
        </div>
      </div>

      <div
        className={`gf-canvas ${appearanceMotionClass(form.appearance)}`.trim()}
        style={appearanceToCssVars(form.appearance)}
      >
        {designerMsg && <p className="msg">{designerMsg}</p>}

        {editorTab === "questions" && (
          <>
            <div className="gf-title-card">
              <input
                className="gf-title-main"
                defaultValue={form.title}
                onBlur={(e) => api.put(`/api/forms/${formId}`, { title: e.target.value || "Untitled form" }).then(load)}
              />
              <textarea
                className="gf-title-desc"
                defaultValue={form.description || ""}
                placeholder="Form description"
                onBlur={(e) => api.put(`/api/forms/${formId}`, { description: e.target.value }).then(load)}
              />
              <div className="gf-status-row" style={{ display: "flex", flexWrap: "wrap", gap: "10px 16px", alignItems: "center" }}>
                <span>Status: <strong>{form.status}</strong></span>
                <VisibilityEditor formId={formId} form={form} onReload={load} onBanner={shareBanner} variant="inline" />
              </div>
              <label style={{ display: "block", marginTop: 12, fontSize: 13, color: "#4b5563" }}>
                Fill experience
                <select
                  value={form.fill_mode === "wizard" ? "wizard" : "all_at_once"}
                  onChange={(e) => {
                    api.patch(`/api/forms/${formId}`, { fill_mode: e.target.value }).then(load).catch((err) => {
                      setDesignerErr(err.response?.data?.detail || JSON.stringify(err.response?.data || err.message));
                    });
                  }}
                  style={{ display: "block", marginTop: 6, maxWidth: 340, padding: "6px 8px", fontSize: 14 }}
                >
                  <option value="all_at_once">All questions on one page</option>
                  <option value="wizard">Wizard — one question per step</option>
                </select>
              </label>
              {canUseAi && (
                <div className="gf-ai-draft" style={{ marginTop: 14 }}>
                  <p style={{ margin: "0 0 6px", fontSize: 13, fontWeight: 600, color: "#4c1d95" }}>AI form draft (Ollama)</p>
                  {aiEnabled && !aiHealthLoading && aiOllamaModel ? (
                    <p style={{ margin: "0 0 6px", fontSize: 12, color: "#5b21b6" }}>
                      Model: <strong>{aiOllamaModel}</strong>
                      {aiOllamaTimeoutSec > 0 ? (
                        <>
                          {" "}
                          · server allows up to {Math.max(1, Math.ceil(aiOllamaTimeoutSec / 60))} min per generation
                        </>
                      ) : null}
                    </p>
                  ) : null}
                  <p style={{ margin: "0 0 8px", fontSize: 12, color: "#6b7280" }}>
                    {aiHealthLoading
                      ? "Checking AI status on the server…"
                      : aiEnabled
                        ? "Describe the form; we append generated questions and update the title and description."
                        : "The server reports AI is off, or the health check failed (e.g. wrong API URL or session). You can still click Generate — errors show below. To enable: LLM_PROVIDER=ollama in backend .env, restart Django, and run Ollama."}
                  </p>
                  <textarea
                    rows={3}
                    placeholder="e.g. A registration form for a weekend workshop with name, email, dietary preferences, and session choice."
                    value={aiPrompt}
                    onChange={(e) => setAiPrompt(e.target.value)}
                    disabled={aiBusy}
                    aria-label="Describe the form for AI draft"
                    style={{ width: "100%", maxWidth: 560, fontSize: 13, padding: 8, borderRadius: 6, border: "1px solid #d1d5db" }}
                  />
                  <div style={{ marginTop: 8 }}>
                    <button
                      type="button"
                      className="btn-primary btn-sm"
                      disabled={aiBusy}
                      onClick={applyAiDraft}
                    >
                      {aiBusy ? "Generating…" : "Generate & append questions"}
                    </button>
                    {aiBusy ? (
                      <p style={{ margin: "8px 0 0", fontSize: 12, color: "#6b7280", maxWidth: 560 }}>
                        Running Ollama on your machine — often 1–3+ minutes on CPU, longer the first time while the model loads into memory. Keep this tab open. Exit an interactive <code style={{ fontSize: 11 }}>ollama run</code> window while generating — it competes for the same model.
                      </p>
                    ) : null}
                  </div>
                </div>
              )}
              {designerErr ? (
                <div
                  role="alert"
                  style={{
                    marginTop: 14,
                    padding: "12px 14px",
                    maxWidth: 560,
                    borderRadius: 8,
                    border: "1px solid #fecaca",
                    background: "#fef2f2",
                  }}
                >
                  <p style={{ margin: "0 0 6px", fontSize: 12, fontWeight: 700, color: "#991b1b" }}>Something went wrong</p>
                  <p className="msg msg-error" style={{ margin: 0, background: "transparent", border: "none", padding: 0, color: "#b91c1c" }}>
                    {designerErr}
                  </p>
                  {designerErrTimeout ? (
                    <ul
                      style={{
                        margin: "10px 0 0",
                        paddingLeft: 20,
                        fontSize: 13,
                        color: "#7f1d1d",
                        listStyleType: "disc",
                      }}
                    >
                      <li style={{ marginBottom: 6 }}>
                        Raise <code style={{ fontSize: 12 }}>OLLAMA_TIMEOUT</code> in backend <code style={{ fontSize: 12 }}>.env</code> (try 600), then restart Django.
                      </li>
                      <li style={{ marginBottom: 6 }}>
                        Use a smaller model: <code style={{ fontSize: 12 }}>OLLAMA_MODEL=phi3:latest</code>.
                      </li>
                      <li style={{ marginBottom: 6 }}>
                        Close any interactive <code style={{ fontSize: 12 }}>ollama run</code> session — it blocks or slows API calls.
                      </li>
                      <li>Warm the model once, then generate from the app: <code style={{ fontSize: 12 }}>ollama run your-model</code> then exit before clicking Generate.</li>
                    </ul>
                  ) : null}
                </div>
              ) : null}
            </div>

            <div className="designer-layout">
              <div>
                {questions.length === 0 && (
                  <div className="card" style={{ textAlign: "center", padding: 40, color: "#9ca3af" }}>
                    <p style={{ fontSize: 16 }}>No questions yet</p>
                    <p>Use the toolbar on the right to add one.</p>
                  </div>
                )}
                {questions.map((q, i) => (
                  <QuestionCard
                    key={q.id}
                    q={q}
                    index={i}
                    total={questions.length}
                    onUpdate={updateQuestion}
                    onDelete={deleteQuestion}
                    onMove={moveQuestion}
                  />
                ))}
              </div>

              <div className="gf-toolbar">
                <button className="gf-tool-btn" onClick={() => addQuestion("short_text")} disabled={saving} title="Add question">+</button>
                <button className="gf-tool-btn" onClick={() => addQuestion("single_choice")} disabled={saving} title="Multiple choice">◉</button>
                <button className="gf-tool-btn" onClick={() => addQuestion("paragraph")} disabled={saving} title="Paragraph">¶</button>
                <button className="gf-tool-btn" onClick={() => addQuestion("dropdown")} disabled={saving} title="Dropdown">▾</button>
                <button className="gf-tool-btn" onClick={() => addQuestion("date")} disabled={saving} title="Date">📅</button>
                <p style={{ fontSize: 11, color: "#6b7280", marginTop: 8, maxWidth: 120 }}>
                  <button type="button" className="btn-secondary btn-sm" style={{ width: "100%" }} onClick={() => setEditorTab("share")}>
                    Share &amp; visibility →
                  </button>
                </p>
              </div>
            </div>
          </>
        )}

        {editorTab === "responses" && (
          <div className="gf-share-panel">
            <div className="card">
              <p className="sidebar-title">Responses &amp; analytics</p>
              <p style={{ fontSize: 14, color: "#4b5563", marginBottom: 16 }}>
                View submission counts, per-question summaries, and recent responses for this form.
              </p>
              <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
                <Link to={`/analytics/${formId}`}>
                  <button type="button" className="btn-primary">Open analytics</button>
                </Link>
                <Link to={`/fill/${formId}`}>
                  <button type="button" className="btn-secondary">Preview as respondent</button>
                </Link>
              </div>
            </div>
          </div>
        )}

        {editorTab === "share" && (
          <FormSharePanel formId={formId} form={form} onReload={load} onBanner={shareBanner} />
        )}
      </div>
    </Layout>
  );
}

// --- Type-Aware Question Input (Fill Page) ---

function QuestionInput({ q, value, onChange }) {
  const opts = q.options || [];

  switch (q.question_type) {
    case "paragraph": {
      const pfmt = (q.validation || {}).format;
      return (
        <textarea
          placeholder="Your answer..."
          value={value || ""}
          onChange={(e) => onChange(e.target.value)}
          autoComplete={pfmt === "email" ? "email" : undefined}
          inputMode={pfmt === "email" ? "email" : undefined}
        />
      );
    }

    case "short_text": {
      const fmt = (q.validation || {}).format;
      const inputType = fmt === "email" ? "email" : fmt === "url" ? "url" : fmt === "phone" ? "tel" : "text";
      return (
        <input
          type={inputType}
          inputMode={fmt === "phone" ? "tel" : fmt === "integer" ? "numeric" : undefined}
          autoComplete={fmt === "email" ? "email" : fmt === "url" ? "url" : undefined}
          placeholder="Your answer..."
          value={value || ""}
          onChange={(e) => onChange(e.target.value)}
        />
      );
    }

    case "single_choice":
      return (
        <div className="radio-group">
          {opts.map((opt, i) => (
            <label key={i}>
              <input type="radio" name={`q_${q.id}`} value={opt} checked={value === opt} onChange={() => onChange(opt)} />
              {opt}
            </label>
          ))}
        </div>
      );

    case "multi_choice":
      return (
        <div className="checkbox-group">
          {opts.map((opt, i) => {
            const selected = Array.isArray(value) ? value : [];
            const checked = selected.includes(opt);
            return (
              <label key={i}>
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => {
                    const next = checked ? selected.filter((v) => v !== opt) : [...selected, opt];
                    onChange(next);
                  }}
                />
                {opt}
              </label>
            );
          })}
        </div>
      );

    case "dropdown":
      return (
        <select value={value || ""} onChange={(e) => onChange(e.target.value)}>
          <option value="">Select...</option>
          {opts.map((opt, i) => (
            <option key={i} value={opt}>{opt}</option>
          ))}
        </select>
      );

    case "date":
      return <input type="date" value={value || ""} onChange={(e) => onChange(e.target.value)} />;

    case "rating": {
      const rules = q.validation || {};
      let rMin = rules.min != null ? Number(rules.min) : 1;
      let rMax = rules.max != null ? Number(rules.max) : 5;
      if (!Number.isFinite(rMin)) rMin = 1;
      if (!Number.isFinite(rMax)) rMax = 5;
      rMin = Math.max(1, Math.floor(rMin));
      rMax = Math.min(10, Math.floor(rMax));
      if (rMax < rMin) {
        rMin = 1;
        rMax = 5;
      }
      const values = [];
      for (let v = rMin; v <= rMax; v += 1) values.push(v);
      const useStars = values.length <= 5;
      return (
        <div className="rating-group">
          {values.map((star) => (
            <button
              key={star}
              type="button"
              className={`rating-star ${value >= star ? "active" : ""}`}
              onClick={() => onChange(star)}
              title={String(star)}
            >
              {useStars ? "\u2605" : star}
            </button>
          ))}
        </div>
      );
    }

    case "file_upload":
      return <input type="file" onChange={(e) => onChange(e.target.files?.[0]?.name || "")} />;

    default:
      return <input type="text" placeholder="Your answer..." value={value || ""} onChange={(e) => onChange(e.target.value)} />;
  }
}

/** True if the respondent has not provided an answer (used for wizard step validation). */
function isFillAnswerEmpty(q, value) {
  if (value === undefined || value === null) return true;
  if (q.question_type === "multi_choice") return !Array.isArray(value) || value.length === 0;
  if (q.question_type === "rating") {
    const n = Number(value);
    return Number.isNaN(n);
  }
  if (typeof value === "string") return !value.trim();
  return false;
}

// --- Fill Form Page ---

function FillFormPage() {
  const { formId } = useParams();
  const [form, setForm] = useState(null);
  const [answers, setAnswers] = useState({});
  const [msg, setMsg] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [wizardStep, setWizardStep] = useState(0);

  useEffect(() => {
    setSubmitted(false);
    setWizardStep(0);
    setAnswers({});
    setMsg("");
    api.get(`/api/forms/${formId}`).then(({ data }) => setForm(data));
  }, [formId]);

  const activeQuestions = (form?.questions || []).filter((q) => !q.disabled);
  const isWizard = form?.fill_mode === "wizard" && activeQuestions.length > 0;

  useEffect(() => {
    if (isWizard && wizardStep >= activeQuestions.length) {
      setWizardStep(Math.max(0, activeQuestions.length - 1));
    }
  }, [isWizard, activeQuestions.length, wizardStep]);

  const buildSubmitPayload = () => {
    const out = {};
    for (const q of activeQuestions) {
      const v = answers[q.id];
      if (!isFillAnswerEmpty(q, v)) out[q.id] = v;
    }
    return out;
  };

  const submitAnswers = async () => {
    try {
      await api.post(`/api/forms/${formId}/submit`, { answers: buildSubmitPayload() });
      setSubmitted(true);
      setMsg("Your response has been recorded.");
    } catch (err) {
      setMsg(JSON.stringify(err.response?.data || err.message));
    }
  };

  const goWizardNext = () => {
    const q = activeQuestions[wizardStep];
    if (q && q.required && isFillAnswerEmpty(q, answers[q.id])) {
      setMsg("Please answer this question before continuing.");
      return;
    }
    setMsg("");
    setWizardStep((s) => Math.min(s + 1, activeQuestions.length - 1));
  };

  const goWizardBack = () => {
    setMsg("");
    setWizardStep((s) => Math.max(0, s - 1));
  };

  if (!form) return <Layout><p>Loading form...</p></Layout>;

  const sched = getFormScheduleState(form);
  const notPublished = form.status !== "published";
  const cannotSubmit = notPublished || sched.notYetOpen || sched.closed;
  const themeVars = appearanceToCssVars(form.appearance);
  const motionClass = appearanceMotionClass(form.appearance);
  const darkClass = form.appearance?.darkMode ? "fill-themed-dark" : "";
  const fillInnerClass = ["fill-container", "fill-themed-inner", motionClass, darkClass].filter(Boolean).join(" ");
  const lastWizardStep = isWizard && activeQuestions.length > 0 && wizardStep === activeQuestions.length - 1;

  const handleFillFormSubmit = (e) => {
    e.preventDefault();
    if (cannotSubmit) return;
    if (isWizard) {
      if (!lastWizardStep) {
        goWizardNext();
        return;
      }
      const q = activeQuestions[wizardStep];
      if (q && q.required && isFillAnswerEmpty(q, answers[q.id])) {
        setMsg("Please answer this question before submitting.");
        return;
      }
    }
    void submitAnswers();
  };

  if (submitted) {
    const thankYou = (form.thank_you_message || "").trim();
    return (
      <Layout>
        <div className="fill-themed-outer" style={themeVars}>
          <div className={fillInnerClass}>
            <div className="fill-header">
              <h2>{form.title}</h2>
            </div>
            <div className="fill-body" style={{ textAlign: "center", padding: 40 }}>
              <p style={{ fontSize: 18, whiteSpace: "pre-wrap" }}>{thankYou || msg}</p>
              <Link to={`/fill/${formId}`} onClick={() => { setSubmitted(false); setAnswers({}); setMsg(""); setWizardStep(0); }}>
                <button className="btn-primary fill-themed-btn" style={{ marginTop: 12 }}>Submit another response</button>
              </Link>
            </div>
          </div>
        </div>
      </Layout>
    );
  }

  const renderQuestionBlock = (q) => (
    <div key={q.id} className="fill-question">
      <label>
        {q.text || "Untitled question"}
        {q.required && <span className="required-star">*</span>}
      </label>
      <QuestionInput q={q} value={answers[q.id]} onChange={(val) => setAnswers((prev) => ({ ...prev, [q.id]: val }))} />
    </div>
  );

  return (
    <Layout>
      <div className="fill-themed-outer" style={themeVars}>
        <div className={fillInnerClass}>
          <div className="fill-header">
            <h2>{form.title}</h2>
            {form.description && <p>{form.description}</p>}
            {isWizard && (
              <p style={{ margin: "10px 0 0", fontSize: 13, opacity: 0.95 }}>
                Step {wizardStep + 1} of {activeQuestions.length}
              </p>
            )}
          </div>
        {cannotSubmit && (
          <p className="msg msg-error" style={{ marginBottom: 12 }}>
            {notPublished && "This form is not published yet."}
            {!notPublished && sched.notYetOpen && "This form is not open yet. Check back after the opening time."}
            {!notPublished && !sched.notYetOpen && sched.closed && "This form is closed and no longer accepts responses."}
          </p>
        )}
        <form onSubmit={handleFillFormSubmit} className="fill-body">
          <fieldset disabled={cannotSubmit} style={{ border: "none", margin: 0, padding: 0 }}>
            {activeQuestions.length === 0 && (
              <p style={{ color: "#9ca3af" }}>This form has no active questions yet.</p>
            )}
            {!isWizard && activeQuestions.map((q) => renderQuestionBlock(q))}
            {isWizard && activeQuestions[wizardStep] && renderQuestionBlock(activeQuestions[wizardStep])}
          </fieldset>
          {!isWizard && (
            <button className="btn-primary fill-themed-btn" style={{ marginTop: 8 }} type="submit" disabled={cannotSubmit}>
              Submit
            </button>
          )}
          {isWizard && activeQuestions.length > 0 && (
            <div className="fill-wizard-nav" style={{ marginTop: 16, display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
              <button type="button" className="btn-secondary fill-themed-btn" disabled={cannotSubmit || wizardStep === 0} onClick={goWizardBack}>
                Back
              </button>
              {!lastWizardStep && (
                <button type="button" className="btn-primary fill-themed-btn" disabled={cannotSubmit} onClick={() => goWizardNext()}>
                  Next
                </button>
              )}
              {lastWizardStep && (
                <button className="btn-primary fill-themed-btn" type="submit" disabled={cannotSubmit}>
                  Submit
                </button>
              )}
            </div>
          )}
          {msg && <p className="msg msg-error" style={{ marginTop: 8 }}>{msg}</p>}
        </form>
        </div>
      </div>
    </Layout>
  );
}

// --- Analytics Page ---

function AnalyticsPage() {
  const { formId } = useParams();
  const [data, setData] = useState(null);
  const [responses, setResponses] = useState([]);
  const [err, setErr] = useState("");
  const [searchDraft, setSearchDraft] = useState("");
  const [afterDraft, setAfterDraft] = useState("");
  const [beforeDraft, setBeforeDraft] = useState("");
  const [search, setSearch] = useState("");
  const [submittedAfter, setSubmittedAfter] = useState("");
  const [submittedBefore, setSubmittedBefore] = useState("");
  const [exportMsg, setExportMsg] = useState("");

  useEffect(() => {
    setSearchDraft("");
    setAfterDraft("");
    setBeforeDraft("");
    setSearch("");
    setSubmittedAfter("");
    setSubmittedBefore("");
  }, [formId]);

  useEffect(() => {
    setErr("");
    const params = new URLSearchParams();
    if (search.trim()) params.set("search", search.trim());
    if (submittedAfter.trim()) params.set("submitted_after", submittedAfter.trim());
    if (submittedBefore.trim()) params.set("submitted_before", submittedBefore.trim());
    const q = params.toString();
    const responsesUrl = `/api/forms/${formId}/responses${q ? `?${q}` : ""}`;
    let cancelled = false;
    Promise.all([api.get(`/api/forms/${formId}/analytics`), api.get(responsesUrl)])
      .then(([analyticsRes, responsesRes]) => {
        if (!cancelled) {
          setData(analyticsRes.data);
          setResponses(responsesRes.data || []);
        }
      })
      .catch((e) => {
        if (!cancelled) setErr(e.response?.data?.detail || "Failed to load analytics");
      });
    return () => {
      cancelled = true;
    };
  }, [formId, search, submittedAfter, submittedBefore]);

  const applyFilters = () => {
    setSearch(searchDraft);
    setSubmittedAfter(afterDraft);
    setSubmittedBefore(beforeDraft);
  };

  if (err) return <Layout><p className="msg msg-error">{err}</p></Layout>;
  if (!data) return <Layout><p>Loading analytics...</p></Layout>;

  return (
    <Layout>
      <h2>Analytics</h2>
      <div className="card stack" style={{ marginBottom: 16 }}>
        <p style={{ margin: 0, fontWeight: 500 }}>Filter responses</p>
        <div className="row" style={{ flexWrap: "wrap", gap: 8, alignItems: "flex-end" }}>
          <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12 }}>
            Search in answers
            <input value={searchDraft} onChange={(e) => setSearchDraft(e.target.value)} placeholder="Text…" style={{ minWidth: 160 }} />
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12 }}>
            Submitted after
            <input type="datetime-local" value={afterDraft} onChange={(e) => setAfterDraft(e.target.value)} />
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12 }}>
            Submitted before
            <input type="datetime-local" value={beforeDraft} onChange={(e) => setBeforeDraft(e.target.value)} />
          </label>
          <button type="button" className="btn-primary btn-sm" onClick={applyFilters}>
            Apply
          </button>
        </div>
      </div>
      <div className="row" style={{ marginBottom: 16 }}>
        <div className="card" style={{ flex: 1, minWidth: 240 }}>
          <p style={{ fontSize: 32, fontWeight: 700, margin: 0, color: "#673ab7" }}>{data.total_responses}</p>
          <p style={{ margin: 0, color: "#6b7280" }}>Total responses</p>
        </div>
        <div className="card" style={{ flex: 2, minWidth: 300 }}>
          <div className="row">
            <button
              type="button"
              className="btn-primary btn-sm"
              onClick={() => {
                setExportMsg("");
                downloadFormExport(formId, "csv").catch((e) => setExportMsg(e.message || "Download failed"));
              }}
            >
              Download CSV
            </button>
            <button
              type="button"
              className="btn-secondary btn-sm"
              onClick={() => {
                setExportMsg("");
                downloadFormExport(formId, "json").catch((e) => setExportMsg(e.message || "Download failed"));
              }}
            >
              Download JSON
            </button>
          </div>
          {exportMsg && <p className="msg msg-error" style={{ marginTop: 8, marginBottom: 0 }}>{exportMsg}</p>}
          <p style={{ margin: "8px 0 0", color: "#6b7280", fontSize: 12 }}>
            Latest submission: {data.latest_submitted_at ? new Date(data.latest_submitted_at).toLocaleString() : "No submissions yet"}
          </p>
        </div>
      </div>

      <div className="stack">
        {data.questions.map((q) => (
          <div key={q.id} className="card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <div>
                <p style={{ margin: 0, fontWeight: 500 }}>{q.text}</p>
                <p style={{ margin: "2px 0 0", fontSize: 12, color: "#9ca3af" }}>{q.question_type}</p>
              </div>
              <p style={{ margin: 0, fontSize: 24, fontWeight: 700, color: "#059669" }}>{q.answer_count}</p>
            </div>
            {q.average !== undefined && (
              <p style={{ margin: "6px 0 0", color: "#4b5563", fontSize: 13 }}>Average rating: {q.average}</p>
            )}
            {q.choice_counts && (
              <div style={{ marginTop: 8 }}>
                {Object.entries(q.choice_counts).map(([label, count]) => {
                  const pct = q.answer_count ? Math.round((count / q.answer_count) * 100) : 0;
                  return (
                    <div key={label} style={{ marginBottom: 8 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "#6b7280" }}>
                        <span>{label}</span>
                        <span>{count} ({pct}%)</span>
                      </div>
                      <div style={{ height: 8, background: "#ede9fe", borderRadius: 999 }}>
                        <div style={{ width: `${pct}%`, height: 8, background: "#7c3aed", borderRadius: 999 }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        ))}
      </div>

      <h3 style={{ marginTop: 20 }}>Recent Responses</h3>
      <div className="card" style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ background: "#f8fafc" }}>
              <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e5e7eb" }}>Response ID</th>
              <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e5e7eb" }}>Submitted</th>
              <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #e5e7eb" }}>Answers</th>
            </tr>
          </thead>
          <tbody>
            {responses.slice(0, 20).map((r) => (
              <tr key={r.id}>
                <td style={{ padding: 8, borderBottom: "1px solid #f3f4f6" }}>{r.id}</td>
                <td style={{ padding: 8, borderBottom: "1px solid #f3f4f6" }}>{new Date(r.submitted_at).toLocaleString()}</td>
                <td style={{ padding: 8, borderBottom: "1px solid #f3f4f6" }}>{r.answers?.length || 0}</td>
              </tr>
            ))}
            {responses.length === 0 && (
              <tr>
                <td colSpan={3} style={{ padding: 12, color: "#9ca3af" }}>No responses yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Layout>
  );
}

// --- App Routes ---

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<ProtectedRoute><FormsPage /></ProtectedRoute>} />
        <Route path="/templates" element={<TemplatesPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/forms/:formId" element={<ProtectedRoute requireDesignerRole={true}><FormEditorPage /></ProtectedRoute>} />
        <Route path="/share/:formId" element={<ProtectedRoute><FormSharePage /></ProtectedRoute>} />
        <Route path="/fill/:formId" element={<ProtectedRoute><FillFormPage /></ProtectedRoute>} />
        <Route path="/analytics/:formId" element={<ProtectedRoute><AnalyticsPage /></ProtectedRoute>} />
        <Route path="/admin/users" element={<AdminRoute><UsersPage /></AdminRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}

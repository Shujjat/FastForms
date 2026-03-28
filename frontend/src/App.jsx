import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { Link, Navigate, Route, Routes, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, setAuthToken, setRefreshToken } from "./api";
import { GoogleSignInButton } from "./GoogleSignInButton";

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

// --- Auth Context ---

const AuthContext = createContext({ isAuthed: false, userRole: null, refreshAuth: async () => {} });

function AuthProvider({ children }) {
  const [isAuthed, setIsAuthed] = useState(Boolean(localStorage.getItem("accessToken")));
  const [userRole, setUserRole] = useState(null);
  const refreshAuth = useCallback(async () => {
    const authed = Boolean(localStorage.getItem("accessToken"));
    setIsAuthed(authed);
    if (!authed) {
      setUserRole(null);
      return;
    }
    try {
      const { data } = await api.get("/api/auth/me");
      setUserRole(data.role || null);
    } catch {
      setUserRole(null);
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
  return <AuthContext.Provider value={{ isAuthed, userRole, refreshAuth }}>{children}</AuthContext.Provider>;
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

// --- Layout ---

function Layout({ children }) {
  const { isAuthed, refreshAuth } = useAuth();
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

// --- Forms List ---

function FormsPage() {
  const { userRole } = useAuth();
  const canDesign = ["creator", "admin"].includes(userRole || "");
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

  return (
    <Layout>
      <h2>Your Forms</h2>
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
        {forms.map((f) => (
          <div key={f.id} className="form-list-card">
            <div className="form-list-info">
              <h3>{f.title}</h3>
              <p>
                Status: <strong>{f.status}</strong> &middot; {f.questions?.length || 0} questions
              </p>
            </div>
            <div className="row">
              {canDesign && <Link to={`/forms/${f.id}`}><button className="btn-primary btn-sm">Design</button></Link>}
              <Link to={`/fill/${f.id}`}><button className="btn-secondary btn-sm">Fill</button></Link>
              <Link to={`/analytics/${f.id}`}><button className="btn-secondary btn-sm">Analytics</button></Link>
              <a
                href={`${import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"}/api/forms/${f.id}/export?export_format=csv`}
                target="_blank"
                rel="noreferrer"
              >
                <button className="btn-secondary btn-sm">CSV</button>
              </a>
              {canDesign && f.status !== "published" && (
                <button className="btn-primary btn-sm" onClick={() => publish(f.id)}>
                  Publish
                </button>
              )}
            </div>
          </div>
        ))}
        {forms.length === 0 && <p style={{ color: "#9ca3af" }}>No forms yet. Create one above.</p>}
      </div>
    </Layout>
  );
}

// --- Question Card (Designer) ---

function QuestionCard({ q, index, total, onUpdate, onDelete, onMove }) {
  const [options, setOptions] = useState(q.options || []);
  const isChoice = CHOICE_TYPES.includes(q.question_type);

  const updateField = (field, value) => {
    onUpdate(q.id, { [field]: value });
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
    <div className="question-card google-card">
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
        <label style={{ display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={q.required}
            onChange={(e) => updateField("required", e.target.checked)}
            style={{ width: "auto" }}
          />
          Required
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

// --- Form Designer Page ---

function FormEditorPage() {
  const { formId } = useParams();
  const [form, setForm] = useState(null);
  const [collaborator, setCollaborator] = useState({ username: "", role: "viewer" });
  const [collabMsg, setCollabMsg] = useState("");
  const [inviteText, setInviteText] = useState("");
  const [inviteNote, setInviteNote] = useState("");
  const [inviteMsg, setInviteMsg] = useState("");
  const [inviteSending, setInviteSending] = useState(false);
  const [saving, setSaving] = useState(false);
  const [designerMsg, setDesignerMsg] = useState("");
  const [designerErr, setDesignerErr] = useState("");
  const navigate = useNavigate();

  const load = async () => {
    const { data } = await api.get(`/api/forms/${formId}`);
    setForm(data);
  };

  useEffect(() => { load(); }, [formId]);

  const addQuestion = async (type) => {
    setSaving(true);
    setDesignerErr("");
    try {
      await api.post(`/api/forms/${formId}/questions`, {
        text: "Untitled question",
        question_type: type,
        required: false,
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

  const addCollaborator = async (e) => {
    e.preventDefault();
    try {
      await api.post(`/api/forms/${formId}/collaborators`, collaborator);
      setCollabMsg("Collaborator added.");
      setCollaborator({ username: "", role: "viewer" });
    } catch (err) {
      setCollabMsg(JSON.stringify(err.response?.data || err.message));
    }
  };

  const parseInviteEmails = (text) => {
    const raw = text.split(/[\n,;]+/).map((s) => s.trim()).filter(Boolean);
    return [...new Set(raw)];
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
          <span className="gf-tab active">Questions</span>
          <span className="gf-tab">Responses</span>
          <span className="gf-tab">Settings</span>
        </div>
      </div>

      <div className="gf-canvas">
        {designerMsg && <p className="msg">{designerMsg}</p>}
        {designerErr && <p className="msg msg-error">{designerErr}</p>}
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
          <div className="gf-status-row">Status: <strong>{form.status}</strong></div>
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

            <div className="card gf-collab-card">
              <p className="sidebar-title">Collaborators</p>
              <form onSubmit={addCollaborator} className="stack">
                <input
                  placeholder="Username"
                  value={collaborator.username}
                  onChange={(e) => setCollaborator({ ...collaborator, username: e.target.value })}
                />
                <select value={collaborator.role} onChange={(e) => setCollaborator({ ...collaborator, role: e.target.value })}>
                  <option value="viewer">Viewer</option>
                  <option value="editor">Editor</option>
                </select>
                <button className="btn-primary btn-sm">Add</button>
                {collabMsg && <p style={{ fontSize: 12, color: "#059669" }}>{collabMsg}</p>}
              </form>
            </div>

            <div className="card gf-collab-card">
              <p className="sidebar-title">Email invitations</p>
              <p style={{ fontSize: 11, color: "#6b7280", margin: "0 0 8px" }}>
                Send a link to this form. The form must be <strong>published</strong>. One address per line, or separate with commas or semicolons.
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
                  <p style={{ fontSize: 11, color: "#b45309" }}>Publish the form first to enable invitations.</p>
                )}
                {inviteMsg && (
                  <p style={{ fontSize: 12, color: inviteMsg.startsWith("Sent") ? "#059669" : "#b91c1c" }}>{inviteMsg}</p>
                )}
              </form>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}

// --- Type-Aware Question Input (Fill Page) ---

function QuestionInput({ q, value, onChange }) {
  const opts = q.options || [];

  switch (q.question_type) {
    case "paragraph":
      return <textarea placeholder="Your answer..." value={value || ""} onChange={(e) => onChange(e.target.value)} />;

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

    case "rating":
      return (
        <div className="rating-group">
          {[1, 2, 3, 4, 5].map((star) => (
            <button
              key={star}
              type="button"
              className={`rating-star ${value >= star ? "active" : ""}`}
              onClick={() => onChange(star)}
            >
              &#9733;
            </button>
          ))}
        </div>
      );

    case "file_upload":
      return <input type="file" onChange={(e) => onChange(e.target.files?.[0]?.name || "")} />;

    default:
      return <input type="text" placeholder="Your answer..." value={value || ""} onChange={(e) => onChange(e.target.value)} />;
  }
}

// --- Fill Form Page ---

function FillFormPage() {
  const { formId } = useParams();
  const [form, setForm] = useState(null);
  const [answers, setAnswers] = useState({});
  const [msg, setMsg] = useState("");
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    api.get(`/api/forms/${formId}`).then(({ data }) => setForm(data));
  }, [formId]);

  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.post(`/api/forms/${formId}/submit`, { answers });
      setSubmitted(true);
      setMsg("Your response has been recorded.");
    } catch (err) {
      setMsg(JSON.stringify(err.response?.data || err.message));
    }
  };

  if (!form) return <Layout><p>Loading form...</p></Layout>;

  if (submitted) {
    return (
      <Layout>
        <div className="fill-container">
          <div className="fill-header">
            <h2>{form.title}</h2>
          </div>
          <div className="fill-body" style={{ textAlign: "center", padding: 40 }}>
            <p style={{ fontSize: 18 }}>{msg}</p>
            <Link to={`/fill/${formId}`} onClick={() => { setSubmitted(false); setAnswers({}); setMsg(""); }}>
              <button className="btn-primary" style={{ marginTop: 12 }}>Submit another response</button>
            </Link>
          </div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="fill-container">
        <div className="fill-header">
          <h2>{form.title}</h2>
          {form.description && <p>{form.description}</p>}
        </div>
        <form onSubmit={submit} className="fill-body">
          {(form.questions || []).map((q) => (
            <div key={q.id} className="fill-question">
              <label>
                {q.text || "Untitled question"}
                {q.required && <span className="required-star">*</span>}
              </label>
              <QuestionInput q={q} value={answers[q.id]} onChange={(val) => setAnswers((prev) => ({ ...prev, [q.id]: val }))} />
            </div>
          ))}
          {(form.questions || []).length === 0 && (
            <p style={{ color: "#9ca3af" }}>This form has no questions yet.</p>
          )}
          <button className="btn-primary" style={{ marginTop: 8 }}>Submit</button>
          {msg && <p className="msg msg-error" style={{ marginTop: 8 }}>{msg}</p>}
        </form>
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
  const apiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

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
            <a href={`${apiBase}/api/forms/${formId}/export?export_format=csv`} target="_blank" rel="noreferrer">
              <button className="btn-primary btn-sm">Download CSV</button>
            </a>
            <a href={`${apiBase}/api/forms/${formId}/export?export_format=json`} target="_blank" rel="noreferrer">
              <button className="btn-secondary btn-sm">Download JSON</button>
            </a>
          </div>
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
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/forms/:formId" element={<ProtectedRoute requireDesignerRole={true}><FormEditorPage /></ProtectedRoute>} />
        <Route path="/fill/:formId" element={<ProtectedRoute><FillFormPage /></ProtectedRoute>} />
        <Route path="/analytics/:formId" element={<ProtectedRoute><AnalyticsPage /></ProtectedRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}

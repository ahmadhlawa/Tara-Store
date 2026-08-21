import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { LOGO_URL, STORE_NAME_AR } from "../../brand.js";
import sx from "../../sx.js";
import { useAdminAuth } from "../AdminAuth.jsx";
import { Button, Field, Notice, input } from "../ui.jsx";

/** Standalone page: no storefront chrome, no navigation. */
export default function LoginPage() {
  const { signIn } = useAdminAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    if (!email.trim() || !password) {
      setError("أدخل البريد الإلكتروني وكلمة المرور.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await signIn(email.trim(), password);
      navigate(location.state?.from || "/admin", { replace: true });
    } catch (cause) {
      setError(cause.message || "تعذّر تسجيل الدخول.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={sx`direction:rtl;min-height:100vh;background:#FFFFFF;display:flex;align-items:center;justify-content:center;padding:20px`}>
      {/* One gold hairline across the top of the card and the logo above the
          heading: enough for the page to belong to Tara without turning a
          credentials form into a brand showcase. */}
      <form onSubmit={submit} style={sx`background:#fff;border:1px solid #E7DCF2;border-top:2px solid var(--brand-secondary);border-radius:16px;padding:28px;width:min(420px,100%);display:flex;flex-direction:column;gap:16px;box-shadow:0 20px 50px var(--brand-primary-16)`}>
        <div style={sx`display:flex;flex-direction:column;align-items:center;gap:6px;text-align:center`}>
          <img
            src={LOGO_URL}
            alt={STORE_NAME_AR}
            style={sx`width:104px;height:104px;object-fit:contain;display:block`}
          />
          <h1 style={sx`margin:0;font-size:22px;font-weight:800;color:var(--admin-primary)`}>تسجيل دخول الإدارة</h1>
          <p style={sx`margin:0;font-size:13.5px;color:#766669`}>هذه الصفحة مخصّصة لمدراء المتجر فقط.</p>
        </div>
        {error && <Notice kind="error">{error}</Notice>}
        <Field title="البريد الإلكتروني">
          <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} dir="ltr" autoComplete="username" style={input} />
        </Field>
        <Field title="كلمة المرور">
          <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" style={input} />
        </Field>
        <Button type="submit" onClick={submit} disabled={busy} style={sx`width:100%;height:48px`}>
          {busy ? "جارٍ التحقق…" : "دخول"}
        </Button>
        <a
          href="/"
          target="_blank"
          rel="noopener noreferrer"
          style={sx`align-self:center;display:flex;align-items:center;gap:6px;font-size:13.5px;font-weight:700;color:var(--link-color);text-decoration:none`}
        >
          <span aria-hidden="true">🛍</span>
          العودة إلى الموقع
        </a>
      </form>
    </div>
  );
}

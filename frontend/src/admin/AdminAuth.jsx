import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { setAuthToken, setUnauthorizedHandler } from "../api/client.js";
import { adminApi } from "../api/adminApi.js";
import { authStorage } from "../storage/authStorage.js";

const AdminAuthContext = createContext(null);

export function useAdminAuth() {
  const context = useContext(AdminAuthContext);
  if (!context) throw new Error("useAdminAuth must be used inside <AdminAuthProvider>");
  return context;
}

export function AdminAuthProvider({ children }) {
  const [admin, setAdmin] = useState(null);
  const [restoring, setRestoring] = useState(true);

  const signOut = useCallback(() => {
    authStorage.clear();
    setAuthToken(null);
    setAdmin(null);
  }, []);

  // A rejected token must not linger: the API client tells us the moment the
  // server refuses our credentials.
  useEffect(() => {
    setUnauthorizedHandler(signOut);
    return () => setUnauthorizedHandler(null);
  }, [signOut]);

  useEffect(() => {
    const saved = authStorage.load();
    if (!saved) {
      setRestoring(false);
      return;
    }
    setAuthToken(saved.token);
    adminApi
      .me()
      .then((profile) => {
        setAdmin(profile);
        authStorage.save(saved.token, profile);
      })
      .catch(() => signOut())
      .finally(() => setRestoring(false));
  }, [signOut]);

  const signIn = useCallback(async (email, password) => {
    const { access_token: token } = await adminApi.login(email, password);
    setAuthToken(token);
    const profile = await adminApi.me();
    authStorage.save(token, profile);
    setAdmin(profile);
    return profile;
  }, []);

  const value = useMemo(
    () => ({
      admin,
      restoring,
      signIn,
      signOut,
      isAuthenticated: !!admin,
      isSuperAdmin: admin?.role === "super_admin",
    }),
    [admin, restoring, signIn, signOut],
  );

  return <AdminAuthContext.Provider value={value}>{children}</AdminAuthContext.Provider>;
}

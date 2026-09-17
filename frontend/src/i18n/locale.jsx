import { createContext, useCallback, useContext, useLayoutEffect } from "react";
import { useLocation, useParams, Navigate } from "react-router-dom";
import { ar, en } from "./dictionaries.js";

const LocaleContext = createContext("ar");
let currentLocale = "ar";
export const getLocale = () => currentLocale;
export function t(key, values = [], locale = currentLocale) {
  if (typeof key !== "string") return key;
  const copy = (locale === "en" ? en : ar)[key] ?? key;
  return copy.replace(/\{(\d+)\}/g, (match, index) => values[index] ?? match);
}
export function localePath(path, locale = currentLocale) {
  if (typeof path !== "string" || !path.startsWith("/") || path.startsWith("//")
      || /^\/(admin|api|media)(\/|$)/.test(path)) return path;
  return `/${locale}${path.replace(/^\/(ar|en)(?=\/|$|[?#])/, "") || "/"}`;
}
export function LocaleProvider({ children }) {
  const location = useLocation();
  const params = useParams();
  const locale = /^\/en(?:\/|$)/.test(location.pathname) ? "en" : "ar";
  currentLocale = locale;
  useLayoutEffect(() => {
    currentLocale = locale;
    document.documentElement.lang = locale;
    document.documentElement.dir = locale === "ar" ? "rtl" : "ltr";
    return () => {
      currentLocale = "ar";
      document.documentElement.lang = "ar";
      document.documentElement.dir = "rtl";
    };
  }, [locale]);
  if (!["ar", "en"].includes(params.locale)) return <LegacyRedirect />;
  return <LocaleContext.Provider value={locale}>{children}</LocaleContext.Provider>;
}
export function useLocale() {
  const locale = useContext(LocaleContext);
  const translate = useCallback((key, values) => t(key, values, locale), [locale]);
  return { locale, t: translate };
}
export function LegacyRedirect() {
  const location = useLocation();
  return <Navigate replace to={{ pathname: localePath(location.pathname, "ar"), search: location.search, hash: location.hash }} />;
}

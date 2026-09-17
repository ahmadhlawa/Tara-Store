import { Link as RouterLink, NavLink as RouterNavLink, useNavigate as useRouterNavigate } from "react-router-dom";
import { forwardRef, useCallback } from "react";
import { localePath, useLocale } from "./locale.jsx";

function destination(to, locale) {
  return typeof to === "string" ? localePath(to, locale) :
    to?.pathname ? { ...to, pathname: localePath(to.pathname, locale) } : to;
}
export const Link = forwardRef(function Link({ to, ...props }, ref) {
  const { locale } = useLocale();
  return <RouterLink ref={ref} {...props} to={destination(to, locale)} />;
});
export const NavLink = forwardRef(function NavLink({ to, ...props }, ref) {
  const { locale } = useLocale();
  return <RouterNavLink ref={ref} {...props} to={destination(to, locale)} />;
});
export function useNavigate() {
  const navigate = useRouterNavigate();
  const { locale } = useLocale();
  return useCallback((to, options) => navigate(destination(to, locale), options), [navigate, locale]);
}

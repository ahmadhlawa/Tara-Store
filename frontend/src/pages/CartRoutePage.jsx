import { Navigate, useLocation } from "react-router-dom";
import { localePath, useLocale } from "../i18n/locale.jsx";

export default function CartRoutePage() {
  const { locale } = useLocale();
  const { search, hash } = useLocation();
  return <Navigate replace to={{ pathname: localePath("/checkout", locale), search, hash }} />;
}

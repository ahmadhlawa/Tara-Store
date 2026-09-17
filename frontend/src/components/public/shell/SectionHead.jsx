import { useLocale } from "../../../i18n/locale.jsx";
import { Link } from "../../../i18n/routing.jsx";
import { ArrowForward } from "./icons.jsx";
import { useViewportReveal } from "../../../hooks/useViewportReveal.js";

/** Shared section heading: eyebrow, title, optional description, optional link. */
export default function SectionHead({ eyebrow, title, description, moreHref, moreLabel, level = 2 }) {
  const { t } = useLocale();
  const Heading = `h${level}`;
  const revealProps = useViewportReveal();
  return (
    <div className="vs-sec-head" {...revealProps}>
      <div className="vs-sec-head__text">
        {eyebrow && <span className="vs-sec-head__eyebrow">{eyebrow}</span>}
        <Heading className="vs-sec-head__title">{title}</Heading>
        {description && <p className="vs-sec-head__desc">{description}</p>}
      </div>
      {moreHref && (
        <Link to={moreHref} className="vs-sec-head__more">
          {moreLabel || t("عرض الكل")}
          <ArrowForward size={15} />
        </Link>
      )}
    </div>
  );
}

import { Link } from "react-router-dom";
import Media from "../shell/Media.jsx";
import { ArrowForward } from "../shell/icons.jsx";

/**
 * Full-width editorial band between two product sections.
 *
 * This is now the only banner form the homepage renders. The compact tile that
 * used to sit in a column beside the hero is gone: the hero is one advertising
 * image across the full width, with nothing competing beside it. Banner records
 * are untouched — every placement simply queues up for these bands instead.
 */
export function StripBanner({ banner }) {
  if (!banner) return null;
  return (
    <Link to={banner.href} className="vs-strip">
      <Media className="vs-strip__media" src={banner.imageUrl} fallback={banner.fallback} alt="" />
      <span className="vs-strip__veil" />
      <span className="vs-strip__body">
        <span className="vs-strip__title">{banner.title}</span>
        {banner.desc && <span className="vs-strip__desc">{banner.desc}</span>}
        <span className="vs-promo__cta">
          {banner.cta} <ArrowForward size={15} />
        </span>
      </span>
    </Link>
  );
}

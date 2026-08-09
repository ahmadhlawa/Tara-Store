import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { storefrontService } from "../services/storefront.js";
import NotFoundRoutePage from "./NotFoundRoutePage.jsx";

/** Renders a published StaticPage. `slug` may come from the route or be fixed. */
export default function StaticContentPage({ slug: fixedSlug }) {
  const params = useParams();
  const slug = fixedSlug || params.slug;

  const [page, setPage] = useState(null);
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    storefrontService
      .page(slug)
      .then((value) => {
        if (cancelled) return;
        setPage(value);
        setStatus("ready");
      })
      .catch(() => !cancelled && setStatus("missing"));
    return () => {
      cancelled = true;
    };
  }, [slug]);

  if (status === "loading") {
    return (
      <div className="vs-container vs-container--narrow vs-section">
        <div className="vs-skel" style={{ height: 28, width: "38%" }} />
        <div className="vs-skel" style={{ height: 200, marginTop: 20 }} />
      </div>
    );
  }

  if (status === "missing" || !page) return <NotFoundRoutePage />;

  return (
    <article className="vs-container vs-container--narrow vs-section">
      <nav className="vs-crumbs" aria-label="مسار التصفح">
        <Link to="/">الرئيسية</Link>
        <span aria-hidden="true">›</span>
        <span className="vs-crumbs__here">{page.title}</span>
      </nav>
      <h1 className="vs-page__title">{page.title}</h1>
      {page.lead && <p className="vs-page__lead">{page.lead}</p>}
      <div className="vs-page__body">
        {page.body.length ? (
          page.body.map((paragraph, index) => (
            <p key={index} className="vs-prose">
              {paragraph}
            </p>
          ))
        ) : (
          <p className="vs-prose vs-prose--muted">لا يوجد محتوى منشور لهذه الصفحة بعد.</p>
        )}
      </div>
    </article>
  );
}

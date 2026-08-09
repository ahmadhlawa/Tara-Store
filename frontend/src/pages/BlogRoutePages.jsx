import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { storefrontService } from "../services/storefront.js";
import Media from "../components/public/shell/Media.jsx";
import NotFoundRoutePage from "./NotFoundRoutePage.jsx";

export function BlogListPage() {
  const [articles, setArticles] = useState([]);
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    let cancelled = false;
    storefrontService
      .articles({ page_size: 24 })
      .then((result) => {
        if (cancelled) return;
        setArticles(result.items);
        setStatus("ready");
      })
      .catch(() => !cancelled && setStatus("error"));
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="vs-container vs-section">
      <h1 className="vs-page__title">المدونة</h1>
      <p className="vs-page__lead">أدلة عملية ونصائح حول الطباعة والتصميم.</p>

      {status === "loading" && (
        <div className="vs-grid vs-grid--cats" aria-hidden="true">
          {[0, 1, 2, 3].map((index) => (
            <div key={index} className="vs-skel" style={{ height: 260, borderRadius: 16 }} />
          ))}
        </div>
      )}

      {status === "error" && (
        <div className="vs-state vs-state--error" role="alert">
          <p className="vs-state__body">تعذّر تحميل المقالات الآن.</p>
        </div>
      )}

      {status === "ready" && articles.length === 0 && (
        <div className="vs-state">
          <h2 className="vs-state__title">لا توجد مقالات منشورة بعد</h2>
          <p className="vs-state__body">سننشر هنا أدلة وأفكاراً حول منتجات المتجر.</p>
          <Link to="/shop" className="vs-btn vs-btn--primary">
            تصفّح المنتجات
          </Link>
        </div>
      )}

      {articles.length > 0 && (
        <div className="vs-grid vs-grid--cats">
          {articles.map((article) => (
            <Link key={article.slug} to={`/blog/${article.slug}`} className="vs-artcard">
              <Media
                ratio="16 / 10"
                src={article.imageUrl}
                fallback={article.bg}
                alt=""
                imgClass="vs-card__img"
              />
              <span className="vs-artcard__body">
                {article.cat && <span className="vs-artcard__cat">{article.cat}</span>}
                <span className="vs-artcard__title vs-clamp-2">{article.title}</span>
                <span className="vs-artcard__meta">
                  {article.date} · {article.read}
                </span>
              </span>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}

export function ArticleDetailPage() {
  const { slug } = useParams();
  const [article, setArticle] = useState(null);
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    storefrontService
      .article(slug)
      .then((value) => {
        if (cancelled) return;
        setArticle(value);
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
        <div className="vs-skel" style={{ height: 28, width: "60%" }} />
        <div className="vs-skel" style={{ height: 240, marginTop: 20 }} />
      </div>
    );
  }

  if (status === "missing" || !article) return <NotFoundRoutePage />;

  const paragraphs = String(article.content || "")
    .split(/\n{2,}/)
    .map((text) => text.trim())
    .filter(Boolean);

  return (
    <article className="vs-container vs-container--narrow vs-section">
      <nav className="vs-crumbs" aria-label="مسار التصفح">
        <Link to="/">الرئيسية</Link>
        <span aria-hidden="true">›</span>
        <Link to="/blog">المدونة</Link>
        <span aria-hidden="true">›</span>
        <span className="vs-crumbs__here">{article.title}</span>
      </nav>
      <h1 className="vs-page__title">{article.title}</h1>
      <p className="vs-page__lead">
        {[article.author, article.date, article.read].filter(Boolean).join(" · ")}
      </p>
      <Media
        ratio="16 / 9"
        src={article.imageUrl}
        fallback={article.bg}
        alt=""
        className="vs-page__hero"
        eager
      />
      <div className="vs-page__body">
        {paragraphs.length ? (
          paragraphs.map((text, index) => (
            <p key={index} className="vs-prose">
              {text}
            </p>
          ))
        ) : (
          <p className="vs-prose vs-prose--muted">{article.excerpt}</p>
        )}
      </div>
    </article>
  );
}

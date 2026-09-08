import { useEffect } from "react";

export function absoluteUrl(base, value) {
  if (!value) return "";
  try {
    return new URL(value, base || window.location.origin).toString();
  } catch {
    return "";
  }
}

function appendMeta(attribute, key, content) {
  if (!content) return;
  const node = document.createElement("meta");
  node.setAttribute(attribute, key);
  node.content = content;
  node.dataset.taraSeo = "true";
  document.head.appendChild(node);
}

/** Synchronizes route metadata with the document head without a runtime dependency. */
export default function useSeo(config) {
  const serialized = JSON.stringify(config);
  useEffect(() => {
    const value = JSON.parse(serialized);
    document.head.querySelectorAll("[data-tara-seo]").forEach((node) => node.remove());
    if (value.title) document.title = value.title;

    const canonical = value.baseUrl && value.path ? absoluteUrl(value.baseUrl, value.path) : "";
    if (canonical) {
      const link = document.createElement("link");
      link.rel = "canonical";
      link.href = canonical;
      link.dataset.taraSeo = "true";
      document.head.appendChild(link);
    }

    appendMeta("name", "description", value.description);
    appendMeta("name", "robots", value.noindex ? "noindex, nofollow" : "index, follow");
    appendMeta("property", "og:title", value.title);
    appendMeta("property", "og:description", value.description);
    appendMeta("property", "og:type", value.type || "website");
    appendMeta("property", "og:url", canonical);
    appendMeta("property", "og:image", absoluteUrl(value.baseUrl, value.image));
    appendMeta("name", "twitter:card", value.image ? "summary_large_image" : "summary");
    appendMeta("name", "twitter:title", value.title);
    appendMeta("name", "twitter:description", value.description);

    (Array.isArray(value.jsonLd) ? value.jsonLd : value.jsonLd ? [value.jsonLd] : []).forEach((data) => {
      const script = document.createElement("script");
      script.type = "application/ld+json";
      script.dataset.taraSeo = "true";
      script.textContent = JSON.stringify(data);
      document.head.appendChild(script);
    });
  }, [serialized]);
}

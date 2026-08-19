const textOnly = (value) => {
  const element = document.createElement("div");
  element.innerHTML = String(value || "");
  return (element.textContent || "").replace(/\s+/g, " ").trim();
};

export function automaticSeo({ title, summary, description, existing = {} }) {
  const fallbackDescription = textOnly(summary || description || title).slice(0, 160) || null;
  return {
    seo_title: textOnly(existing.seo_title || title).slice(0, 200) || null,
    seo_description: textOnly(existing.seo_description) || fallbackDescription,
  };
}

// sx — converts the design's inline CSS strings into React style objects.
// Styles are transcribed verbatim from the Claude Design source, so visual
// parity is kept; parsed objects are memoized by the full CSS string.
const cache = new Map();

function toCamel(prop) {
  return prop.replace(/-(\w)/g, (_, c) => c.toUpperCase());
}

function parse(css) {
  const out = {};
  for (const decl of css.split(";")) {
    const i = decl.indexOf(":");
    if (i === -1) continue;
    const prop = decl.slice(0, i).trim();
    const value = decl.slice(i + 1).trim();
    if (prop) out[toCamel(prop)] = value;
  }
  return out;
}

export default function sx(strings, ...values) {
  const css =
    typeof strings === "string"
      ? strings
      : strings.reduce((acc, s, i) => acc + s + (i < values.length ? values[i] : ""), "");
  let style = cache.get(css);
  if (!style) {
    if (cache.size > 800) cache.clear();
    style = parse(css);
    cache.set(css, style);
  }
  return style;
}

import { useEffect, useMemo, useRef, useState } from "react";
import sx from "../sx.js";
import { input } from "./ui.jsx";

export function CategoryPicker({ categories, value, onChange, emptyLabel = "بدون قسم", excludedId = null }) {
  const rootRef = useRef(null);
  const triggerRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState(() => new Set());
  const byId = useMemo(() => new Map(categories.map((category) => [String(category.id), category])), [categories]);
  const childrenByParent = useMemo(() => {
    const grouped = new Map();
    categories.forEach((category) => {
      const key = category.parent_id == null ? "root" : String(category.parent_id);
      grouped.set(key, [...(grouped.get(key) || []), category]);
    });
    grouped.forEach((siblings) => siblings.sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0)));
    return grouped;
  }, [categories]);
  const selected = value === "" || value == null ? null : byId.get(String(value));

  useEffect(() => {
    if (!open) return undefined;
    const next = new Set();
    let current = selected;
    while (current?.parent_id != null) {
      next.add(String(current.parent_id));
      current = byId.get(String(current.parent_id));
    }
    setExpanded((existing) => new Set([...existing, ...next]));
    const close = (event) => {
      if (!rootRef.current?.contains(event.target)) setOpen(false);
    };
    document.addEventListener("pointerdown", close);
    return () => document.removeEventListener("pointerdown", close);
  }, [byId, open, selected]);

  const choose = (category) => {
    onChange(category ? String(category.id) : "");
    setOpen(false);
  };
  const toggle = (id) => setExpanded((existing) => {
    const next = new Set(existing);
    next.has(id) ? next.delete(id) : next.add(id);
    return next;
  });
  const renderRows = (parentKey = "root", depth = 0) => (childrenByParent.get(parentKey) || []).map((category) => {
    const id = String(category.id);
    if (id === String(excludedId)) return null;
    const children = childrenByParent.get(id) || [];
    const isExpanded = expanded.has(id);
    const isSelected = String(value) === id;
    return (
      <div key={id}>
        <div style={sx`display:flex;align-items:center;min-height:38px;padding-inline-start:${depth * 18}px;background:${isSelected ? "#F1E8F8" : "transparent"};border-radius:7px`}>
          {children.length ? (
            <button type="button" aria-label={`${isExpanded ? "طي" : "توسيع"} ${category.name}`} aria-expanded={isExpanded} onClick={() => toggle(id)} style={sx`width:34px;height:34px;border:0;background:transparent;color:#5B4D67;cursor:pointer;font-size:15px`}>
              {isExpanded ? "▾" : "▸"}
            </button>
          ) : <span aria-hidden="true" style={sx`width:34px`} />}
          <button type="button" role="option" aria-selected={isSelected} onClick={() => choose(category)} style={sx`flex:1;min-height:36px;border:0;background:transparent;text-align:start;font-family:inherit;font-size:14px;font-weight:${isSelected ? 800 : 500};color:#3B3243;cursor:pointer;padding:6px`}>
            {category.name}
          </button>
        </div>
        {children.length > 0 && isExpanded && renderRows(id, depth + 1)}
      </div>
    );
  });

  return (
    <div ref={rootRef} style={sx`position:relative`} onKeyDown={(event) => {
      if (event.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    }}>
      <button ref={triggerRef} type="button" aria-haspopup="listbox" aria-expanded={open} onClick={() => setOpen((current) => !current)} style={{ ...input, ...sx`display:flex;align-items:center;justify-content:space-between;cursor:pointer;text-align:start;color:#3B3243` }}>
        <span>{selected?.name || emptyLabel}</span><span aria-hidden="true">⌄</span>
      </button>
      {open && (
        <div role="listbox" aria-label="القسم" style={sx`position:absolute;z-index:20;inset-inline:0;top:calc(100% + 6px);max-height:280px;overflow:auto;padding:6px;background:#fff;border:1px solid #DFD2EC;border-radius:10px;box-shadow:0 12px 28px rgba(59,50,67,.16)`}>
          <button type="button" role="option" aria-selected={value === "" || value == null} onClick={() => choose(null)} style={sx`width:100%;min-height:38px;padding:6px 40px 6px 6px;border:0;border-radius:7px;background:${value === "" || value == null ? "#F1E8F8" : "transparent"};text-align:start;font-family:inherit;font-size:14px;font-weight:${value === "" || value == null ? 800 : 500};color:#3B3243;cursor:pointer`}>
            {emptyLabel}
          </button>
          {renderRows()}
        </div>
      )}
    </div>
  );
}

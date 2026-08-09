import { useEffect, useRef } from "react";

const FOCUSABLE = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled]):not([type=hidden])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

const visible = (element) =>
  element.offsetWidth > 0 || element.offsetHeight > 0 || element === document.activeElement;

/**
 * Keeps Tab inside `ref` while `active`, moves focus in on open and returns it
 * to whatever was focused before — the trigger, in every real case.
 */
export function useFocusTrap(active, { onEscape, autoFocus = true } = {}) {
  const ref = useRef(null);
  const opener = useRef(null);
  const escapeRef = useRef(onEscape);
  escapeRef.current = onEscape;

  useEffect(() => {
    if (!active) return undefined;
    const node = ref.current;
    opener.current = document.activeElement;

    const items = () => Array.from(node?.querySelectorAll(FOCUSABLE) || []).filter(visible);

    // A drawer with no focusable child still has to take focus off the page
    // behind it, so the container itself becomes the target. `autoFocus: false`
    // is for a panel the pointer opened on its own: Tab is still trapped once
    // the visitor moves into it, but nothing is taken from them first.
    if (autoFocus) {
      const first = items()[0];
      if (first) first.focus();
      else if (node) {
        node.setAttribute("tabindex", "-1");
        node.focus();
      }
    }

    const onKeyDown = (event) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        escapeRef.current?.();
        return;
      }
      if (event.key !== "Tab") return;
      const list = items();
      if (!list.length) {
        event.preventDefault();
        return;
      }
      const start = list[0];
      const end = list[list.length - 1];
      if (event.shiftKey && document.activeElement === start) {
        event.preventDefault();
        end.focus();
      } else if (!event.shiftKey && document.activeElement === end) {
        event.preventDefault();
        start.focus();
      }
    };

    node?.addEventListener("keydown", onKeyDown);
    return () => {
      node?.removeEventListener("keydown", onKeyDown);
      const previous = opener.current;
      if (
        autoFocus &&
        previous &&
        typeof previous.focus === "function" &&
        document.contains(previous)
      ) {
        previous.focus();
      }
    };
  }, [active]);

  return ref;
}

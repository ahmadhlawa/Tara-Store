import { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";
import { OVERLAY, useStore } from "../../../app/StoreProvider.jsx";
import useMediaQuery from "../../../hooks/useMediaQuery.js";

/** How long the pointer has to stay on the rail before the drawer opens. */
const OPEN_DELAY = 120;
/** How long the drawer waits after the pointer has left both rail and drawer. */
const CLOSE_DELAY = 260;

const HoverContext = createContext(null);

/**
 * Hover intent shared by the rail and the category drawer.
 *
 * Both live under `PublicShell` but in different subtrees, and the whole point is
 * that moving from one into the other is a single gesture — so the timers have to
 * be one pair, not two. Only a real mouse gets them: a touch device matches
 * neither `hover: hover` nor `pointer: fine`, keeps the rail hidden, and opens the
 * drawer by tapping the header trigger exactly as before.
 */
export function CategoryHoverProvider({ children }) {
  const { overlay, openOverlay, closeAll } = useStore();
  const fine = useMediaQuery("(hover: hover) and (pointer: fine)");
  const openTimer = useRef(null);
  const closeTimer = useRef(null);
  const overlayRef = useRef(overlay);
  overlayRef.current = overlay;
  // Opened by hover means "do not take the keyboard with you" — a drawer the
  // visitor never asked for must not move focus off whatever they were using.
  const [openedByHover, setOpenedByHover] = useState(false);

  useEffect(() => {
    if (overlay !== OVERLAY.CATEGORIES) setOpenedByHover(false);
  }, [overlay]);

  useEffect(
    () => () => {
      clearTimeout(openTimer.current);
      clearTimeout(closeTimer.current);
    },
    [],
  );

  const value = useMemo(() => {
    const clearOpen = () => {
      clearTimeout(openTimer.current);
      openTimer.current = null;
    };
    const clearClose = () => {
      clearTimeout(closeTimer.current);
      closeTimer.current = null;
    };

    const onPointerEnter = (event) => {
      // `pointerenter` does not fire when the pointer moves between children, so
      // travelling down the category icons never restarts anything.
      if (!fine || (event && event.pointerType === "touch")) return;
      clearClose();
      if (overlayRef.current === OVERLAY.CATEGORIES) return;
      // Another overlay is up: hovering the rail must not yank it away.
      if (overlayRef.current) return;
      if (openTimer.current) return;
      openTimer.current = setTimeout(() => {
        openTimer.current = null;
        setOpenedByHover(true);
        openOverlay(OVERLAY.CATEGORIES);
      }, OPEN_DELAY);
    };

    const onPointerLeave = (event) => {
      if (!fine || (event && event.pointerType === "touch")) return;
      clearOpen();
      clearClose();
      closeTimer.current = setTimeout(() => {
        closeTimer.current = null;
        if (overlayRef.current === OVERLAY.CATEGORIES) closeAll();
      }, CLOSE_DELAY);
    };

    return {
      hoverEnabled: fine,
      openedByHover,
      hoverProps: { onPointerEnter, onPointerLeave },
      /** A click is an explicit request: it gets focus, and no pending timer. */
      claimAsClick: () => {
        clearOpen();
        clearClose();
        setOpenedByHover(false);
      },
    };
  }, [fine, openedByHover, openOverlay, closeAll]);

  return <HoverContext.Provider value={value}>{children}</HoverContext.Provider>;
}

const INERT = {
  hoverEnabled: false,
  openedByHover: false,
  hoverProps: {},
  claimAsClick: () => {},
};

/** Safe outside the provider — the admin workspace renders no rail at all. */
export function useCategoryHover() {
  return useContext(HoverContext) || INERT;
}

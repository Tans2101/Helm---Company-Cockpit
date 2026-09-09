import { useEffect, useRef } from "react";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";

/** Hydrate cockpit appearance from the signed-in user document. */
export default function AppearanceSync() {
  const { user } = useAuth();
  const { hydrateAppearance } = useTheme();
  const last = useRef(null);

  useEffect(() => {
    const appearance = user?.appearance;
    if (!appearance || appearance === last.current) return;
    last.current = appearance;
    hydrateAppearance(appearance);
  }, [user?.appearance, hydrateAppearance]);

  return null;
}

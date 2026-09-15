/** Smooth-scroll to an in-page marketing hash, navigating home first when needed. */
export function goToHomeHash(navigate, location, hash, after) {
  after?.();
  const scroll = () => {
    document.getElementById(hash)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  if (location.pathname === "/") {
    if (location.hash !== `#${hash}`) {
      navigate(`/#${hash}`);
    }
    window.setTimeout(scroll, 0);
    return;
  }
  navigate(`/#${hash}`);
}

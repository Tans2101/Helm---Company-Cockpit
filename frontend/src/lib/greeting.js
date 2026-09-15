/** Greeting for the signed-in experience. Briefing is always just "Briefing" — never time-boxed. */
export function dayPartGreeting(now = new Date()) {
  const h = now.getHours();
  let greeting = "Hello";
  if (h >= 5 && h < 12) greeting = "Good morning";
  else if (h >= 12 && h < 17) greeting = "Good afternoon";
  else if (h >= 17 && h < 22) greeting = "Good evening";
  return { greeting, briefingLabel: "Briefing" };
}

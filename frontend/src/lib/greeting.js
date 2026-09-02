/** Time-of-day greeting in the user's local timezone. */
export function timeGreeting(date = new Date()) {
  const hour = date.getHours();
  if (hour >= 5 && hour < 12) {
    return { greeting: "Good morning", briefingLabel: "Morning Briefing" };
  }
  if (hour >= 12 && hour < 17) {
    return { greeting: "Good afternoon", briefingLabel: "Afternoon Briefing" };
  }
  if (hour >= 17 && hour < 21) {
    return { greeting: "Good evening", briefingLabel: "Evening Briefing" };
  }
  return { greeting: "Good night", briefingLabel: "Night Briefing" };
}

/** Google Drive Picker — uses a short-lived token from the Trenston API. */

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[src="${src}"]`);
    if (existing) {
      resolve();
      return;
    }
    const s = document.createElement("script");
    s.src = src;
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error(`Could not load ${src}`));
    document.head.appendChild(s);
  });
}

export async function pickDriveBill({ apiKey, appId, accessToken }) {
  if (!apiKey || !appId || !accessToken) {
    throw new Error("Drive picker is not configured");
  }
  await loadScript("https://apis.google.com/js/api.js");
  await new Promise((resolve) => window.gapi.load("picker", resolve));
  return new Promise((resolve, reject) => {
    const view = new window.google.picker.View(window.google.picker.ViewId.DOCS);
    view.setMimeTypes("application/pdf,image/png,image/jpeg");
    const picker = new window.google.picker.PickerBuilder()
      .addView(view)
      .setOAuthToken(accessToken)
      .setDeveloperKey(apiKey)
      .setAppId(String(appId))
      .setCallback((data) => {
        if (data.action === window.google.picker.Action.CANCEL) {
          resolve(null);
          return;
        }
        if (data.action === window.google.picker.Action.PICKED) {
          const doc = (data.docs && data.docs[0]) || null;
          resolve(doc ? { fileId: doc.id, name: doc.name, mimeType: doc.mimeType } : null);
        }
      })
      .build();
    picker.setVisible(true);
    if (!picker) reject(new Error("Could not open Drive picker"));
  });
}

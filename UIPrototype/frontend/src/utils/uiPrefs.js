/** Local UI preferences shared by Settings and list pages. */
const STORAGE_KEY = 'papermate-ui-prefs';

export function getUiPrefs() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

export function setUiPrefs(patch) {
  const next = { ...getUiPrefs(), ...patch };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  window.dispatchEvent(new CustomEvent('papermate:ui-prefs', { detail: next }));
  return next;
}

export function getWorkspacePageSize(defaultSize = 12) {
  const value = Number(getUiPrefs().workspacePageSize);
  return [8, 12, 16, 24].includes(value) ? value : defaultSize;
}

export function getLibraryPageSize(defaultSize = 20) {
  const value = Number(getUiPrefs().libraryPageSize);
  return [10, 20, 50].includes(value) ? value : defaultSize;
}

export function getLanguage(defaultLang = 'zh') {
  const value = getUiPrefs().language;
  return value === 'en' ? 'en' : (value === 'zh' ? 'zh' : defaultLang);
}

export function setLanguage(language) {
  return setUiPrefs({ language: language === 'en' ? 'en' : 'zh' });
}

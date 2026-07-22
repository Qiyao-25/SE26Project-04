import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { getLanguage, setLanguage as persistLanguage } from '../utils/uiPrefs';
import { translate } from './messages';

const LanguageContext = createContext(null);

export function LanguageProvider({ children }) {
  const [language, setLanguageState] = useState(() => getLanguage('zh'));

  useEffect(() => {
    const onPrefs = (event) => {
      const next = event?.detail?.language;
      if (next === 'zh' || next === 'en') setLanguageState(next);
    };
    window.addEventListener('papermate:ui-prefs', onPrefs);
    return () => window.removeEventListener('papermate:ui-prefs', onPrefs);
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute('lang', language === 'en' ? 'en' : 'zh-CN');
  }, [language]);

  const setLanguage = useCallback((next) => {
    const value = next === 'en' ? 'en' : 'zh';
    setLanguageState(value);
    persistLanguage(value);
  }, []);

  const t = useCallback((key, vars) => translate(language, key, vars), [language]);

  const value = useMemo(() => ({ language, setLanguage, t }), [language, setLanguage, t]);
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useI18n() {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error('useI18n must be used within LanguageProvider');
  return ctx;
}

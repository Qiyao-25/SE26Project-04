import { createContext, useContext, useMemo, useState, useCallback, useEffect } from 'react';
import { DEFAULT_PAPER_NOTES } from '../data/papers';
import { getCurrentUser, loginUser, registerUser } from '../services/authService';
import { getLearningProfile } from '../services/learningService';
import { USE_MOCK } from '../services/runtimeConfig';

const WIREFRAME_DEMO = false;
const WORKSPACE_SEARCH_FLAG_KEY = 'papermate-workspace-searched-v1';
const WORKSPACE_LAST_QUERY_KEY = 'papermate-workspace-last-query-v1';
const AppContext = createContext(null);

function readSessionFlag(key) {
  try {
    return sessionStorage.getItem(key) === '1';
  } catch {
    return false;
  }
}

function readSessionText(key) {
  try {
    return sessionStorage.getItem(key) || '';
  } catch {
    return '';
  }
}

export function AppProvider({ children }) {
  const hasToken = Boolean(localStorage.getItem('papermate.accessToken'));
  const [loggedIn, setLoggedIn] = useState(() => USE_MOCK ? false : hasToken);
  const [authReady, setAuthReady] = useState(() => USE_MOCK || !hasToken);
  const [isAdmin, setIsAdmin] = useState(() => localStorage.getItem('papermate.role') === 'admin');
  const [userId, setUserId] = useState(() => localStorage.getItem('papermate.userId') || 'demo-user');
  const [email, setEmail] = useState(() => localStorage.getItem('papermate.email') || '');
  const [persona, setPersona] = useState('研究');
  const [topics, setTopics] = useState(['cs.CL']);
  const [workspaceSearched, setWorkspaceSearched] = useState(() => readSessionFlag(WORKSPACE_SEARCH_FLAG_KEY));
  const [lastSearchQuery, setLastSearchQuery] = useState(() => readSessionText(WORKSPACE_LAST_QUERY_KEY));
  const [lockedPaperId, setLockedPaperId] = useState(null);
  const [paperNotes, setPaperNotes] = useState(() => JSON.parse(JSON.stringify(DEFAULT_PAPER_NOTES)));
  const [comparePaperA, setComparePaperA] = useState('attention');
  const [comparePaperB, setComparePaperB] = useState('bert');
  const [compareActiveSlot, setCompareActiveSlot] = useState('a');

  const clearAuth = useCallback(() => {
    setLoggedIn(false);
    setIsAdmin(false);
    setUserId('demo-user');
    setEmail('');
    localStorage.removeItem('papermate.accessToken');
    localStorage.removeItem('papermate.userId');
    localStorage.removeItem('papermate.email');
    localStorage.removeItem('papermate.role');
  }, []);

  const hydrateProfile = useCallback(async (nextUserId) => {
    if (USE_MOCK || !nextUserId) return;
    try {
      const profile = await getLearningProfile(nextUserId);
      if (profile?.persona) setPersona(profile.persona);
      if (Array.isArray(profile?.topics)) setTopics(profile.topics);
    } catch {
      // Profile hydrate is best-effort; onboarding / Learning can still set it.
    }
  }, []);

  const applyUser = useCallback((user) => {
    setLoggedIn(true);
    setIsAdmin(user.role === 'admin');
    setUserId(user.user_id);
    setEmail(user.email);
    localStorage.setItem('papermate.userId', user.user_id);
    localStorage.setItem('papermate.email', user.email);
    localStorage.setItem('papermate.role', user.role);
  }, []);

  useEffect(() => {
    const onAuthExpired = () => clearAuth();
    window.addEventListener('papermate:auth-expired', onAuthExpired);
    const token = localStorage.getItem('papermate.accessToken');
    if (USE_MOCK || !token) {
      setAuthReady(true);
      return () => window.removeEventListener('papermate:auth-expired', onAuthExpired);
    }
    let cancelled = false;
    getCurrentUser()
      .then(async (user) => {
        if (cancelled) return;
        applyUser(user);
        await hydrateProfile(user.user_id);
      })
      .catch(() => {
        if (!cancelled) clearAuth();
      })
      .finally(() => {
        if (!cancelled) setAuthReady(true);
      });
    return () => {
      cancelled = true;
      window.removeEventListener('papermate:auth-expired', onAuthExpired);
    };
  }, [applyUser, clearAuth, hydrateProfile]);

  const applyAuth = useCallback((data) => {
    applyUser(data.user);
    localStorage.setItem('papermate.accessToken', data.access_token);
    setAuthReady(true);
    hydrateProfile(data.user.user_id);
  }, [applyUser, hydrateProfile]);

  const login = useCallback(async (loginEmail, password) => {
    const data = await loginUser(loginEmail, password);
    applyAuth(data);
    return data;
  }, [applyAuth]);

  const register = useCallback(async (registerEmail, password) => {
    const data = await registerUser(registerEmail, password);
    applyAuth(data);
    return data;
  }, [applyAuth]);

  const logout = useCallback(() => {
    clearAuth();
    setWorkspaceSearched(false);
    setLastSearchQuery('');
    setLockedPaperId(null);
  }, [clearAuth]);

  useEffect(() => {
    try {
      sessionStorage.setItem(WORKSPACE_SEARCH_FLAG_KEY, workspaceSearched ? '1' : '0');
      sessionStorage.setItem(WORKSPACE_LAST_QUERY_KEY, lastSearchQuery || '');
    } catch {
      // ignore quota / private mode
    }
  }, [workspaceSearched, lastSearchQuery]);

  const showAdminNav = WIREFRAME_DEMO || isAdmin;
  const getPaperNotes = useCallback((paperId) => paperNotes[paperId] || { notes: [], comments: [] }, [paperNotes]);
  const replacePaperNotes = useCallback((paperId, data) => setPaperNotes((prev) => ({ ...prev, [paperId]: data })), []);
  const saveNote = useCallback((paperId, text) => {
    setPaperNotes((prev) => {
      const data = prev[paperId] ? { ...prev[paperId] } : { notes: [], comments: [] };
      data.notes = [{ id: Date.now(), highlight: '选中文本高亮', text, date: '2026-07-09' }, ...data.notes];
      return { ...prev, [paperId]: data };
    });
  }, []);
  const addComment = useCallback((paperId, text) => {
    setPaperNotes((prev) => {
      const data = prev[paperId] ? { ...prev[paperId] } : { notes: [], comments: [] };
      data.comments = [{ id: Date.now(), text, date: '2026-07-09' }, ...data.comments];
      return { ...prev, [paperId]: data };
    });
  }, []);
  // Entering a paper must not reshuffle A/B: if it is already A or B, keep slots.
  const setCompareForPaper = useCallback((paperId) => {
    const id = String(paperId);
    if (String(comparePaperA) === id) {
      setCompareActiveSlot('a');
      return;
    }
    if (String(comparePaperB) === id) {
      setCompareActiveSlot('b');
      return;
    }
    setComparePaperA(paperId);
    setCompareActiveSlot('a');
  }, [comparePaperA, comparePaperB]);
  const exitLockedPaper = useCallback(() => {
    setLockedPaperId(null);
  }, []);

  const value = useMemo(() => ({
    loggedIn, authReady, isAdmin, userId, email, persona, topics, workspaceSearched, lastSearchQuery,
    lockedPaperId, comparePaperA, comparePaperB, compareActiveSlot, showAdminNav,
    login, register, applyAuthResponse: applyAuth, logout, setPersona, setTopics, setWorkspaceSearched, setLastSearchQuery,
    setLockedPaperId, exitLockedPaper, setComparePaperA, setComparePaperB, setCompareActiveSlot,
    getPaperNotes, replacePaperNotes, saveNote, addComment, setCompareForPaper
  }), [
    loggedIn, authReady, isAdmin, userId, email, persona, topics, workspaceSearched, lastSearchQuery,
    lockedPaperId, comparePaperA, comparePaperB, compareActiveSlot, showAdminNav,
    login, register, applyAuth, logout, exitLockedPaper, getPaperNotes, replacePaperNotes, saveNote, addComment, setCompareForPaper
  ]);

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used within AppProvider');
  return ctx;
}

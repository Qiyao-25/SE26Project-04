import { createContext, useContext, useMemo, useState, useCallback } from 'react';
import { DEFAULT_PAPER_NOTES, getDefaultCompareTarget } from '../data/papers';

const WIREFRAME_DEMO = false;

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [loggedIn, setLoggedIn] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [userId, setUserId] = useState(() => localStorage.getItem('papermate.userId') || 'demo-user');
  const [persona, setPersona] = useState('研究');
  const [topics, setTopics] = useState(['cs.CL']);
  const [workspaceSearched, setWorkspaceSearched] = useState(false);
  const [lastSearchQuery, setLastSearchQuery] = useState('');
  const [paperNotes, setPaperNotes] = useState(() => JSON.parse(JSON.stringify(DEFAULT_PAPER_NOTES)));
  const [comparePaperA, setComparePaperA] = useState('attention');
  const [comparePaperB, setComparePaperB] = useState('bert');
  const [compareActiveSlot, setCompareActiveSlot] = useState('a');

  const login = useCallback((email) => {
    const resolvedUserId = (email || '').trim().toLowerCase() || 'demo-user';
    const admin = resolvedUserId === 'admin';
    setLoggedIn(true);
    setIsAdmin(admin);
    setUserId(resolvedUserId);
    localStorage.setItem('papermate.userId', resolvedUserId);
  }, []);

  const logout = useCallback(() => {
    setLoggedIn(false);
    setIsAdmin(false);
    setWorkspaceSearched(false);
    setLastSearchQuery('');
  }, []);

  const showAdminNav = WIREFRAME_DEMO || isAdmin;

  const getPaperNotes = useCallback((paperId) => {
    return paperNotes[paperId] || { notes: [], comments: [] };
  }, [paperNotes]);

  const replacePaperNotes = useCallback((paperId, data) => {
    setPaperNotes((prev) => ({ ...prev, [paperId]: data }));
  }, []);

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

  const setCompareForPaper = useCallback((paperId) => {
    setComparePaperA(paperId);
    setComparePaperB((b) => (b === paperId ? getDefaultCompareTarget(paperId) : b));
  }, []);

  const value = useMemo(() => ({
    loggedIn, isAdmin, userId, persona, topics, workspaceSearched, lastSearchQuery,
    comparePaperA, comparePaperB, compareActiveSlot,
    showAdminNav,
    login, logout, setPersona, setTopics,
    setWorkspaceSearched, setLastSearchQuery,
    setComparePaperA, setComparePaperB, setCompareActiveSlot,
    getPaperNotes, replacePaperNotes, saveNote, addComment, setCompareForPaper
  }), [
    loggedIn, isAdmin, userId, persona, topics, workspaceSearched, lastSearchQuery,
    comparePaperA, comparePaperB, compareActiveSlot, showAdminNav,
    login, logout, getPaperNotes, replacePaperNotes, saveNote, addComment, setCompareForPaper
  ]);

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used within AppProvider');
  return ctx;
}

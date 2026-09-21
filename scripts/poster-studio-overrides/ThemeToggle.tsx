'use client';

/**
 * Light/dark theme toggle. Toggles the `.dark` class on <html>; poster-studio's
 * CSS variables (see globals.css :root and .dark) flip the chrome (topbar,
 * sidebars, panels, dialogs). The canvas paper is hardcoded #fff and stays
 * white in both modes. Choice persists to localStorage.
 */

import { useEffect, useState } from 'react';
import { Sun, Moon } from 'lucide-react';
import { Button } from '@/components/ui/button';

const STORAGE_KEY = 'poster-theme';

export default function ThemeToggle() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    const initial = stored === 'dark';
    setDark(initial);
    document.documentElement.classList.toggle('dark', initial);
  }, []);

  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle('dark', next);
    localStorage.setItem(STORAGE_KEY, next ? 'dark' : 'light');
  };

  return (
    <Button
      variant="ghost"
      size="icon"
      className="h-10 w-10"
      onClick={toggle}
      title={dark ? '切换到浅色模式' : '切换到深色模式'}
      aria-label="切换主题"
    >
      {dark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
    </Button>
  );
}

import WebApp from '@twa-dev/sdk';

declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        ready: () => void;
        expand: () => void;
        initData?: string;
        setHeaderColor?: (color: string) => void;
        setBackgroundColor?: (color: string) => void;
        HapticFeedback?: {
          impactOccurred: (style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft') => void;
          notificationOccurred: (type: 'error' | 'success' | 'warning') => void;
          selectionChanged: () => void;
        };
      };
    };
  }
}

export function initTelegramLightTheme(): void {
  try {
    const tg = window.Telegram?.WebApp || WebApp;
    tg.ready?.();
    tg.expand?.();
    tg.setHeaderColor?.('#FAFAFA');
    tg.setBackgroundColor?.('#FAFAFA');
  } catch {
    // Running outside Telegram client in standard desktop/mobile browser
  }
}

export function triggerHaptic(style: 'light' | 'medium' | 'heavy' = 'light'): void {
  try {
    const tg = window.Telegram?.WebApp || WebApp;
    tg.HapticFeedback?.impactOccurred(style);
  } catch {
    // Ignore outside Telegram
  }
}

export function getTelegramInitData(): string {
  try {
    return window.Telegram?.WebApp?.initData || WebApp.initData || '';
  } catch {
    return '';
  }
}


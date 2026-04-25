export type NotificationItem = {
  id: string;          // unique, e.g. "exec_<execution_id>"
  type: "execution_completed" | "execution_failed" | "campaign_completed" | "finetune_completed";
  title: string;
  message: string;
  href?: string;       // link to click through
  timestamp: number;   // ms since epoch
  read: boolean;
};

const STORAGE_KEY = "af_notifications";
const MAX_STORED = 50;

export function loadNotifications(): NotificationItem[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]") as NotificationItem[];
  } catch { return []; }
}

export function saveNotifications(items: NotificationItem[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(0, MAX_STORED)));
}

export function markAllRead(items: NotificationItem[]): NotificationItem[] {
  return items.map((n) => ({ ...n, read: true }));
}

export function unreadCount(items: NotificationItem[]): number {
  return items.filter((n) => !n.read).length;
}

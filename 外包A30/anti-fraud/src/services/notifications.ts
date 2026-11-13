import { Alert } from "../types";

export async function notifyHighRisk(alert: Alert) {
  if (alert.level !== "high" || !("Notification" in window)) return;
  let permission = Notification.permission;
  if (permission === "default") permission = await Notification.requestPermission();
  if (permission !== "granted") return;
  new Notification("安知高风险预警", {
    body: `${alert.type}：${alert.summary.slice(0, 90)}`,
    tag: alert.id,
    requireInteraction: true,
  });
}

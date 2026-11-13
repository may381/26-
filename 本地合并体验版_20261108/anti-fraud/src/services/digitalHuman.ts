import type { Alert } from "../types";

export type DigitalHumanSignal =
  | { state: "analyzing" }
  | { state: "result"; alert: Alert }
  | { state: "error" };

export function signalDigitalHuman(detail: DigitalHumanSignal) {
  window.dispatchEvent(new CustomEvent<DigitalHumanSignal>("anzhi-digital-human", { detail }));
}

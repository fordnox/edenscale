export type Route =
  | "dashboard"
  | "funds"
  | "fund-detail"
  | "investors"
  | "calls"
  | "distributions"
  | "documents"
  | "letters"
  | "tasks"
  | "notifications"

export const routeLabels: Record<Route, string> = {
  dashboard: "Overview",
  funds: "Funds",
  "fund-detail": "Fund detail",
  investors: "Investors",
  calls: "Capital Calls",
  distributions: "Distributions",
  documents: "Documents",
  letters: "Letters",
  tasks: "Tasks",
  notifications: "Notifications",
}

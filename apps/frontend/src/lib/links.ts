import {
  LayoutDashboard,
  Package,
} from "lucide-react";

export interface NavLink {
  label: string;
  path: string;
  icon: typeof LayoutDashboard;
}

export interface NavSection {
  title: string;
  links: NavLink[];
}

export const sections: NavSection[] = [
  {
    title: "Main",
    links: [
      { path: "/", label: "Home", icon: LayoutDashboard },
      { path: "/login", label: "Login", icon: Package },
    ],
  },
  {
    title: "Social",
    links: [],
  },
];

export function getSection(name: string): NavSection | undefined {
  return sections.find((section) => section.title === name);
}

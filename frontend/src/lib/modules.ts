// Single source of truth for the 6 dashboard modules (used by router + sidebar).
export interface ModuleDef {
  path: string;
  label: string;
  blurb: string;
}

export const MODULES: ModuleDef[] = [
  { path: "/", label: "Command Center", blurb: "Live sentiment gauge, trend, and counts." },
  { path: "/identity", label: "Your Identity", blurb: "Follower growth, post ranking, audience map." },
  { path: "/public-voice", label: "Public Voice", blurb: "What people are saying, by sentiment." },
  { path: "/trends", label: "Trends", blurb: "Topics rising and falling over time." },
  { path: "/crisis", label: "Crisis & DMs", blurb: "Spike alerts and ManyChat DM activity." },
  { path: "/ai-brief", label: "AI Brief", blurb: "Your daily AI summary and recommended actions." },
];

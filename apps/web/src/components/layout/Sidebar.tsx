"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Boxes,
  Columns3,
  Cpu,
  Flame,
  GraduationCap,
  History,
  Images,
  Layers,
  Settings,
  Sparkles,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/generate", label: "Generate", icon: Sparkles },
  { href: "/compare", label: "Compare", icon: Columns3 },
  { href: "/models", label: "Models", icon: Boxes },
  { href: "/loras", label: "LoRAs", icon: Layers },
  { href: "/datasets", label: "Datasets", icon: Images },
  { href: "/training", label: "Training", icon: GraduationCap },
  { href: "/history", label: "History", icon: History },
  { href: "/system", label: "System", icon: Cpu },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="border-line bg-panel border-b md:sticky md:top-0 md:h-[100dvh] md:w-56 md:shrink-0 md:border-r md:border-b-0">
      <div className="flex items-center gap-2 px-4 py-4">
        <Flame aria-hidden className="text-accent size-5" />
        <span className="font-semibold tracking-tight">ForgeAI Studio</span>
      </div>
      <nav aria-label="Main" className="overflow-x-auto px-2 pb-2 md:pb-0">
        <ul className="flex gap-1 md:flex-col">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || pathname.startsWith(`${href}/`);
            return (
              <li key={href}>
                <Link
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={`flex items-center gap-2.5 rounded-md px-3 py-2 text-sm whitespace-nowrap transition-colors ${
                    active ? "bg-raised text-ink" : "text-muted hover:bg-raised/60 hover:text-ink"
                  }`}
                >
                  <Icon aria-hidden className={`size-4 ${active ? "text-accent" : ""}`} />
                  {label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </aside>
  );
}

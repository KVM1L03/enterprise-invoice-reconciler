"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import { BarChart3, Landmark, LayoutDashboard } from "lucide-react";

type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
};

const navItems: NavItem[] = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/reports", label: "Reports", icon: BarChart3 },
];

function isActive(pathname: string | null, href: string): boolean {
  if (!pathname) return false;
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 shrink-0 bg-[#f2f4f6] flex flex-col">
      <div className="px-6 py-8">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 bg-[#00502e] flex items-center justify-center rounded-lg shadow-sm">
            <Landmark className="h-5 w-5 text-white" />
          </div>
          <div>
            <h2 className="text-[#00502e] font-bold text-sm leading-none tracking-tight">
              OmniAccountant
            </h2>
            <p className="text-[10px] text-slate-500 uppercase tracking-[0.15em] mt-1.5">
              Financial Operations
            </p>
          </div>
        </div>

        <nav className="space-y-1">
          {navItems.map(({ href, label, icon: Icon }) => {
            const active = isActive(pathname, href);
            return (
              <Link
                key={href}
                href={href}
                className={
                  active
                    ? "flex items-center gap-3 px-3 py-2 bg-[#9df5bd]/40 text-[#00502e] border-l-4 border-[#00502e] transition-transform hover:translate-x-1 duration-300 ease-out text-sm font-semibold"
                    : "flex items-center gap-3 px-3 py-2 text-slate-600 hover:bg-slate-200/50 transition-transform hover:translate-x-1 duration-300 ease-out rounded-md text-sm font-medium"
                }
              >
                <Icon className="h-4 w-4" />
                {label}
              </Link>
            );
          })}
        </nav>
      </div>

      <div className="mt-auto px-6 py-8">
        <p className="px-3 text-[10px] text-slate-400 font-mono uppercase tracking-widest">
          Version 1.0.0 · Enterprise AI
        </p>
      </div>
    </aside>
  );
}

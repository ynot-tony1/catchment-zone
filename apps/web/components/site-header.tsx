import Link from "next/link";

const NAV_LINKS = [
  { href: "/schools", label: "Schools" },
  { href: "/admissions", label: "Admissions" },
  { href: "/map", label: "Map" },
  { href: "/trusts", label: "Trusts" },
  { href: "/local-authorities", label: "Local authorities" },
  { href: "/about/data", label: "About the data" },
];

export function SiteHeader() {
  return (
    <header className="border-border bg-background/95 sticky top-0 z-40 border-b backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 px-4">
        <Link href="/" className="font-semibold tracking-tight">
          catchment-zone
        </Link>
        <nav
          aria-label="Primary"
          className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm"
        >
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-muted-foreground hover:text-foreground"
            >
              {link.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}

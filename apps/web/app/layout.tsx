import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";

import "leaflet/dist/leaflet.css";
import "./globals.css";


export const metadata: Metadata = {
  title: "Riverwise — Nova Scotia river conditions",
  description: "Measured river flow, nearby modeled weather, and a transparent experimental conditions score.",
};


export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <div className="shell header-inner">
            <Link className="brand" href="/" aria-label="Riverwise home">
              <Image
                className="brand-logo"
                src="/riverwise-logo.png"
                alt=""
                width={34}
                height={34}
                priority
              />
              <span>Riverwise</span>
            </Link>
            <nav className="header-nav" aria-label="Primary navigation">
              <span className="header-tag">Nova Scotia gauge conditions</span>
              <Link className="status-link" href="/score-lab">Score lab</Link>
              <Link className="status-link" href="/status">Data status</Link>
              <a
                aria-label="Riverwise on GitHub (opens in a new tab)"
                className="header-github-link"
                href="https://github.com/JadenAntM/Riverwise"
                rel="noreferrer"
                target="_blank"
              >
                <Image aria-hidden="true" alt="" height={16} src="/github.svg" width={16} />
                <span className="header-github-label">GitHub</span>
                <span aria-hidden="true" className="header-github-arrow">↗</span>
              </a>
            </nav>
          </div>
        </header>
        {children}
        <footer className="site-footer">
          <div className="shell footer-inner">
            <p>Data: Water Survey of Canada and Open-Meteo</p>
            <p>Not river-safety or legal-fishing guidance</p>
          </div>
        </footer>
      </body>
    </html>
  );
}

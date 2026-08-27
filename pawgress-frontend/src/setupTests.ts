/**
 * src/setupTests.ts
 *
 * Loaded once before every test file (vite.config.ts's test.setupFiles).
 * Adds jest-dom's DOM-specific matchers (toBeInTheDocument, etc.) to
 * Vitest's expect — nothing app-specific lives here, except the
 * matchMedia polyfill below, which jsdom doesn't implement at all and
 * several real components/hooks call directly (e.g.
 * useCompanionBehavior's prefers-reduced-motion check). Defaults to
 * "doesn't match" so tests aren't accidentally in reduced-motion mode
 * unless a test explicitly overrides it.
 */
import "@testing-library/jest-dom/vitest";

if (!window.matchMedia) {
  window.matchMedia = (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  });
}


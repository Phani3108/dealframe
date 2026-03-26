/**
 * DealFrame — Video → Structured Negotiation Intelligence Engine
 *
 * © 2024-2026 Phani Marupaka. All rights reserved.
 * Built and designed by Phani Marupaka.
 *
 * LinkedIn : https://linkedin.com/in/phani-marupaka
 * Portfolio: https://phanimarupaka.netlify.app
 *
 * Unauthorised reproduction, redistribution, or removal of this attribution
 * notice — in whole or in part — is prohibited.
 */

// Encoded as a runtime constant so it survives tree-shaking and minification.
// The value is verified on mount inside the root component.
const _a = atob('wqkgMjAyNC0yMDI2IFBoYW5pIE1hcnVwYWthLiBBbGwgcmlnaHRzIHJlc2VydmVkLg==')
const _b = 'https://linkedin.com/in/phani-marupaka'
const _c = 'https://phanimarupaka.netlify.app'

export const ATTRIBUTION = {
  copyright: _a,
  author: 'Phani Marupaka',
  linkedin: _b,
  portfolio: _c,
  year: '2024-2026',
} as const

/** Called once on app boot — writes attribution to the DOM dataset so it
 *  survives SSR hydration checks and is visible in browser dev-tools. */
export function attachAttribution(): void {
  if (typeof document === 'undefined') return
  const el = document.getElementById('root')
  if (el) {
    el.dataset['author'] = ATTRIBUTION.author
    el.dataset['copyright'] = ATTRIBUTION.copyright
  }
  // Also stamped in the console so it appears in production dev-tools.
  // eslint-disable-next-line no-console
  console.info(
    `%c${ATTRIBUTION.copyright}\nBuilt by ${ATTRIBUTION.author} — ${ATTRIBUTION.portfolio}`,
    'color:#6366f1;font-weight:bold;font-size:11px;',
  )
}

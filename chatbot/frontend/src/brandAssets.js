// Resolves the four brand images. A hosted URL from window.LENS_ASSETS (the
// editable block at the top of the page) always wins; otherwise the bundled
// copy is used — which is an empty string in the single-file build, making
// the UI fall back to its typographic lockups and gradient background.
import { policeImg, centerImg, badgeImg, bgImg } from '@brand-assets';

const cfg = (typeof window !== 'undefined' && window.LENS_ASSETS) || {};

export const policeSrc = cfg.police || policeImg;
export const centerSrc = cfg.center || centerImg;
export const badgeSrc = cfg.badge || badgeImg;
export const bgSrc = cfg.background || bgImg;

// The app-shell background image layer is CSS; feed it through a variable so
// it can come from config. Unset, the gradient layers still paint.
if (bgSrc) {
  document.documentElement.style.setProperty('--bg-image', `url("${bgSrc}")`);
}

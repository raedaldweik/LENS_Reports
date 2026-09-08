// Bundled brand images — used by the normal (FastAPI-served) build.
// The single-file build swaps this module for assets-external.js via a
// resolve alias, so no image bytes are embedded in that file.
export { default as policeImg } from './assets/police.png';
export { default as centerImg } from './assets/center.png';
export { default as badgeImg } from './assets/badge.svg';
export { default as bgImg } from './assets/bg.png';

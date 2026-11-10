/** Empty or zero means no timer; the API takes seconds. */
export function minutesToSeconds(minutes) {
  const n = Number(minutes)
  return minutes !== '' && Number.isFinite(n) && n > 0 ? Math.round(n * 60) : null
}

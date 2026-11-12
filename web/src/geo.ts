const R = 6378137;
const toLon = (x: number) => (x / R) * (180 / Math.PI);
const toLat = (y: number) => (2 * Math.atan(Math.exp(y / R)) - Math.PI / 2) * (180 / Math.PI);

/** Corner ring of a 1 km Web-Mercator cell from its id (epsg3857-1km-{ix}-{iy}). */
export function cellRing(id: string): [number, number][] | null {
  const m = /^epsg3857-1km-(-?\d+)-(-?\d+)$/.exec(id);
  if (!m) return null;
  const x0 = Number(m[1]) * 1000, y0 = Number(m[2]) * 1000;
  const pts: [number, number][] = [[x0, y0], [x0 + 1000, y0], [x0 + 1000, y0 + 1000], [x0, y0 + 1000], [x0, y0]];
  return pts.map(([x, y]) => [toLon(x), toLat(y)]);
}

/** Id of the 1 km cell containing a point. */
export function cellIdAt(lon: number, lat: number): string {
  const x = (lon * Math.PI / 180) * R;
  const y = Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI / 180) / 2)) * R;
  return `epsg3857-1km-${Math.floor(x / 1000)}-${Math.floor(y / 1000)}`;
}

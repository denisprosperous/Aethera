/** AETHERA projection functions — pure TypeScript, no coordinate assumptions. */

export type Projection = (lon: number, lat: number) => [number, number];

export const mercator: Projection = (lon, lat) => {
  const lr = Math.max(-89.999, Math.min(89.999, lat)) * Math.PI / 180;
  return [lon * Math.PI / 180, Math.log(Math.tan(Math.PI/4 + lr/2))];
};
export const robinson: Projection = (lon, lat) => {
  const lr = lat * Math.PI / 180;
  return [lon * Math.PI / 180 * Math.cos(lr * 0.7), lr * (1.0 - 0.1 * lr * lr)];
};
export const authagraph: Projection = (lon, lat) => {
  const lr = lat * Math.PI / 180;
  return [lon * Math.PI / 180 * Math.cos(lr), Math.sin(lr)];
};
export const equirectangular: Projection = (lon, lat) => [lon * Math.PI / 180, lat * Math.PI / 180];

export const PROJECTIONS: Record<string, Projection> = {
  Mercator: mercator, Robinson: robinson,
  AuthaGraph: authagraph, Equirectangular: equirectangular,
};

export interface Polygon {
  name: string;
  vertices: [number, number][];
  areaTrue: number;
  coloniser: boolean;
}

export interface StrainField {
  polygonName: string;
  centroid: [number, number];
  areaProjected: number;
  areaTrue: number;
  scaleFactor: number;
  logStrain: number;
  colour: [number, number, number];
}

export interface DistortionScore {
  projection: string;
  meanLogStrain: number;
  stdLogStrain: number;
  maxInflation: number;
  maxDeflation: number;
  colonialDistortionScore: number;
  note: string;
}

function shoelaceArea(verts: [number, number][]): number {
  if (verts.length < 3) return 0;
  let s = 0;
  for (let i = 0; i < verts.length; i++) {
    const [x1, y1] = verts[i];
    const [x2, y2] = verts[(i + 1) % verts.length];
    s += x1 * y2 - x2 * y1;
  }
  return Math.abs(s) / 2;
}

function centroid2d(verts: [number, number][]): [number, number] {
  const n = verts.length;
  return [verts.reduce((s, v) => s + v[0], 0) / n, verts.reduce((s, v) => s + v[1], 0) / n];
}

export function strainField(polygons: Polygon[], proj: Projection, projName: string): StrainField[] {
  return polygons.map((poly) => {
    const projected = poly.vertices.map(([lon, lat]) => proj(lon, lat));
    const areaProj = shoelaceArea(projected);
    const scale = areaProj / Math.max(poly.areaTrue, 1e-12);
    const logStrain = Math.log(Math.max(scale, 1e-12));
    const cent = centroid2d(projected);
    let colour: [number, number, number];
    if (logStrain > 0) { const t = Math.min(1, logStrain / 2); colour = [1.0, 1.0-t, 1.0-t]; }
    else { const t = Math.min(1, -logStrain / 2); colour = [1.0-t, 1.0-t, 1.0]; }
    return { polygonName: poly.name, centroid: cent, areaProjected: areaProj,
             areaTrue: poly.areaTrue, scaleFactor: scale, logStrain, colour };
  });
}

export function allScores(polygons: Polygon[]): DistortionScore[] {
  return Object.entries(PROJECTIONS).map(([name, p]) => {
    const strains = strainField(polygons, p, name);
    const cs = strains.filter((_, i) => polygons[i].coloniser).map((s) => s.logStrain);
    const ds = strains.filter((_, i) => !polygons[i].coloniser).map((s) => s.logStrain);
    const mean = (xs: number[]) => xs.reduce((a, b) => a + b, 0) / Math.max(xs.length, 1);
    const mc = mean(cs); const md = mean(ds);
    const allS = strains.map((s) => s.logStrain);
    const ma = mean(allS);
    const std = allS.length > 0 ? Math.sqrt(allS.reduce((s, x) => s + (x-ma)**2, 0) / allS.length) : 0;
    return { projection: name, meanLogStrain: ma, stdLogStrain: std,
             maxInflation: Math.max(...allS, 0), maxDeflation: Math.min(...allS, 0),
             colonialDistortionScore: mc - md,
             note: `${name}: coloniser mean ${mc.toFixed(3)}, colonised mean ${md.toFixed(3)}.` };
  });
}

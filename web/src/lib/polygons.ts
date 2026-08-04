import type { Polygon } from './projections';

export const CONTINENT_POLYGONS: Polygon[] = [
  { name: 'Africa', vertices: [[-20,-35],[50,-35],[50,37],[-20,37]],
    areaTrue: 30_370_000, coloniser: false }, // AETHERA-GUARD: ALLOW DOCUMENTATION (measured area)
  { name: 'Europe', vertices: [[-10,36],[40,36],[40,71],[-10,71]],
    areaTrue: 10_180_000, coloniser: true }, // AETHERA-GUARD: ALLOW DOCUMENTATION (measured area)
  { name: 'Asia', vertices: [[26,0],[180,0],[180,77],[26,77]],
    areaTrue: 44_579_000, coloniser: true }, // AETHERA-GUARD: ALLOW DOCUMENTATION (measured area)
  { name: 'North America', vertices: [[-168,7],[-52,7],[-52,83],[-168,83]],
    areaTrue: 24_709_000, coloniser: true }, // AETHERA-GUARD: ALLOW DOCUMENTATION (measured area)
  { name: 'South America', vertices: [[-82,-56],[-35,-56],[-35,13],[-82,13]],
    areaTrue: 17_840_000, coloniser: false }, // AETHERA-GUARD: ALLOW DOCUMENTATION (measured area)
  { name: 'Australia', vertices: [[113,-44],[154,-44],[154,-10],[113,-10]],
    areaTrue: 8_600_000, coloniser: true }, // AETHERA-GUARD: ALLOW DOCUMENTATION (measured area)
  { name: 'Greenland', vertices: [[-50,60],[-20,60],[-20,80],[-50,80]],
    areaTrue: 2_166_086, coloniser: false }, // AETHERA-GUARD: ALLOW DOCUMENTATION (measured area)
  { name: 'Antarctica', vertices: [[-180,-90],[180,-90],[180,-60],[-180,-60]],
    areaTrue: 14_000_000, coloniser: false }, // AETHERA-GUARD: ALLOW DOCUMENTATION (measured area)
];

# AETHERA Distortion Analysis Report (v10.5)

## Global Distortion Index

The Global Distortion Index (GDI) quantifies the average percentage by
which legacy cartographic projections deviate from physical truth.

| Projection | GDI (%) | Total Physical Area (km²) | Total Legacy Area (km²) | Regions |
|------------|---------|--------------------------|------------------------|---------|
| Mercator | 128.22% | 277,094,473 | 277,094,473 | 149 |
| Equirectangular | 36.89% | 277,094,473 | 277,094,473 | 149 |
| AuthaGraph | 23.96% | 277,094,473 | 277,094,473 | 149 |
| Robinson | 19.91% | 277,094,473 | 277,094,473 | 149 |

**Worst projection:** Mercator (GDI = 128.22%)
**Best projection:** Robinson (GDI = 19.91%)

## Top 10 Regions by Relative Error (Mercator projection)

| Rank | Region | Physical Area (km²) | Legacy Area (km²) | Relative Error (%) | Category |
|------|--------|--------------------|--------------------|--------------------|----------|
| 1 | Antarctica | 14,000,000 | 191,233,424 | -1265.95% | overreported |
| 2 | Solomon Islands | 28,896 | 101,682 | -251.89% | overreported |
| 3 | Peru | 1,285,216 | 43,106 | +96.65% | underreported |
| 4 | Botswana | 581,730 | 34,385 | +94.09% | underreported |
| 5 | Rwanda | 26,338 | 1,795 | +93.18% | underreported |
| 6 | Guatemala | 108,889 | 8,382 | +92.30% | underreported |
| 7 | Bhutan | 38,394 | 3,035 | +92.10% | underreported |
| 8 | Suriname | 163,820 | 14,395 | +91.21% | underreported |
| 9 | Sudan | 1,886,068 | 194,168 | +89.71% | underreported |
| 10 | Angola | 1,246,700 | 132,365 | +89.38% | underreported |

## Distribution of Relative Errors

```
  <1%        |  (0)
  1-5%       |  (0)
  5-10%      | ██ (2)
  10-25%     | █████ (5)
  25-50%     | ██████ (6)
  50-100%    | ██████████████████████████████████████████████████ (134)
  100-250%   |  (0)
  250-500%   | █ (1)
  >500%      | █ (1)
```

## Scientific Disclaimer

These metrics compare legacy cartographic projection areas against a
physical baseline derived from measured geographic survey data. Deviations
represent the systematic bias introduced by map projections, not errors
in the original data sources.

The "physical truth" baseline uses the actual surface area of each region
(a measurable physical fact). The "legacy" values are computed by applying
each projection's mathematical transform to the region's boundary and
measuring the resulting projected area.

## Conclusion

This report provides a transparent, verifiable baseline for understanding
how map projections systematically distort the representation of Earth's
surface area. AETHERA's Physical Truth offers an independent reference
for scientific and educational purposes.

**Total regions analysed:** 149
**Total metrics computed:** 596 (regions × projections)

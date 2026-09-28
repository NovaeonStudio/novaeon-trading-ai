// Slim pill handle for the data-zoom slider (colors come from the Nova chart theme).
const handleIcon = 'path://M3,0 H5 Q8,0 8,3 V17 Q8,20 5,20 H3 Q0,20 0,17 V3 Q0,0 3,0 Z';

export const dataZoomPartial = {
  show: true,
  type: 'slider',
  handleIcon,
  handleSize: '110%',
  height: 22,
  moveHandleSize: 4,
};

/**
 * Plot area for the generic charts that carry a zoom slider below the plot. Axis labels and names
 * are kept inside `outerBounds` (everything above the slider) by ECharts itself.
 */
export const echartsGridDefault = {
  left: 8,
  right: 16,
  top: 36,
  bottom: 48,
  outerBounds: { left: 0, right: 0, top: 0, bottom: 40 },
};

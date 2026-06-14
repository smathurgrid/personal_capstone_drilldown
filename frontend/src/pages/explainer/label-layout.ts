export type LabelDetail = {
  label: string;
  description?: string;
  point?: [number, number];
  positionUncertain?: boolean;
};

function labelX(detail: LabelDetail): number {
  if (detail.positionUncertain || !detail.point || detail.point.length < 2) return 0.5;
  return detail.point[0];
}

function labelY(detail: LabelDetail): number {
  if (detail.positionUncertain || !detail.point || detail.point.length < 2) return 0.5;
  return detail.point[1];
}

export function getColumnData(details: LabelDetail[], detailIndex: number) {
  const current = details[detailIndex];
  const isLeft = labelX(current) < 0.5;
  const column = details
    .map((d, i) => ({ ...d, originalIndex: i }))
    .filter((d) => (labelX(d) < 0.5) === isLeft)
    .sort((a, b) => {
      if (labelY(a) !== labelY(b)) return labelY(a) - labelY(b);
      return a.originalIndex - b.originalIndex;
    });
  const indexInCol = column.findIndex((d) => d.originalIndex === detailIndex);
  return { isLeft, column, indexInCol };
}

export function getDistributedY(details: LabelDetail[], detailIndex: number) {
  if (!details.length) return 0.5;
  const { column, indexInCol } = getColumnData(details, detailIndex);
  if (indexInCol === -1) return labelY(details[detailIndex]);
  if (column.length === 1) {
    return Math.max(0.1, Math.min(0.9, labelY(details[detailIndex])));
  }
  const startY = 0.1;
  const endY = 0.9;
  return startY + (indexInCol * (endY - startY)) / (column.length - 1);
}

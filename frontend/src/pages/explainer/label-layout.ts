export type LabelDetail = {
  label: string;
  description?: string;
  point: [number, number];
};

export function getColumnData(details: LabelDetail[], detailIndex: number) {
  const current = details[detailIndex];
  const isLeft = current.point[0] < 0.5;
  const column = details
    .map((d, i) => ({ ...d, originalIndex: i }))
    .filter((d) => (d.point[0] < 0.5) === isLeft)
    .sort((a, b) => {
      if (a.point[1] !== b.point[1]) return a.point[1] - b.point[1];
      return a.originalIndex - b.originalIndex;
    });
  const indexInCol = column.findIndex((d) => d.originalIndex === detailIndex);
  return { isLeft, column, indexInCol };
}

export function getDistributedY(details: LabelDetail[], detailIndex: number) {
  if (!details.length) return 0.5;
  const { column, indexInCol } = getColumnData(details, detailIndex);
  if (indexInCol === -1) return details[detailIndex].point[1];
  if (column.length === 1) {
    return Math.max(0.1, Math.min(0.9, details[detailIndex].point[1]));
  }
  const startY = 0.1;
  const endY = 0.9;
  return startY + (indexInCol * (endY - startY)) / (column.length - 1);
}

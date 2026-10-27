// Reference-only presentation metadata. These identities keep the supplied
// fifteen-field map in its original visual order; they do not define which
// fields exist or which fields a user may see.
const referenceFieldOrder = [
  'FLD-JZ-Q4V8', 'FLD-JZ-1A10D148', 'FLD-JZ-F9C520CF', 'FLD-JZ-501DEE8F', 'FLD-JZ-D7K4',
  'FLD-JZ-970A1994', 'FLD-JZ-6AAD2179', 'FLD-JZ-M9R2', 'FLD-JZ-6CBE52D4', 'FLD-JZ-8DC1EF23',
  'FLD-JZ-B23A7282', 'FLD-JZ-0DE51079', 'FLD-JZ-CDEC786B', 'FLD-JZ-9CE9571C', 'FLD-JZ-D9DF575C',
]

// Shape and label coordinates are UI geometry, not field facts.
const referenceGeometry = [
  { points: '115,36 213,36 201,130 58,145 75,95', x: 135, y: 102 },
  { points: '222,37 333,40 336,134 210,130', x: 274, y: 102 },
  { points: '341,40 475,46 482,135 345,136', x: 411, y: 102 },
  { points: '483,47 615,48 615,138 490,136', x: 553, y: 102 },
  { points: '624,48 759,48 771,142 626,139', x: 697, y: 102 },
  { points: '60,156 207,141 211,248 75,250 71,204', x: 138, y: 199 },
  { points: '215,140 336,144 338,247 218,248', x: 275, y: 200 },
  { points: '345,145 478,144 481,246 346,248', x: 412, y: 200 },
  { points: '487,144 620,146 632,245 490,246', x: 557, y: 200 },
  { points: '628,149 773,153 783,242 639,246', x: 711, y: 200 },
  { points: '76,260 211,258 205,351 51,352', x: 133, y: 307 },
  { points: '219,258 337,257 338,351 213,352', x: 276, y: 307 },
  { points: '345,256 487,256 496,350 346,351', x: 418, y: 307 },
  { points: '495,254 632,252 650,351 505,350', x: 575, y: 307 },
  { points: '640,251 784,252 794,353 660,353', x: 721, y: 307 },
]

const referencePosition = new Map(referenceFieldOrder.map((fieldId, position) => [fieldId, position]))
export const FIELD_MAP_PAGE_SIZE = referenceGeometry.length

export function projectFieldMap(fields, requestedPage = 1) {
  const ordered = fields
    .map((field, sourceOrder) => ({ field, sourceOrder, referencePosition: referencePosition.get(field.fieldId) }))
    .sort((left, right) =>
      (left.referencePosition ?? Number.MAX_SAFE_INTEGER) - (right.referencePosition ?? Number.MAX_SAFE_INTEGER) ||
      left.sourceOrder - right.sourceOrder,
    )
  const total = ordered.length
  const pageCount = Math.max(1, Math.ceil(total / FIELD_MAP_PAGE_SIZE))
  const page = Math.min(pageCount, Math.max(1, Number(requestedPage) || 1))
  const start = (page - 1) * FIELD_MAP_PAGE_SIZE
  const items = ordered.slice(start, start + FIELD_MAP_PAGE_SIZE).map(({ field }, index) => ({
    field,
    ...referenceGeometry[index],
    path: `/fields/${encodeURIComponent(field.fieldId)}`,
  }))
  return { items, page, pageCount, total }
}

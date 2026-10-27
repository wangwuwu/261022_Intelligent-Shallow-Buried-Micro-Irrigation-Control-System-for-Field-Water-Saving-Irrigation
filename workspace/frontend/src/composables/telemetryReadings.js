export function latestZoneReading(entities, zoneIds, kind, asOf) {
  const selectedZones = new Set(zoneIds.filter(Boolean));
  if (!selectedZones.size) return null;

  const zones = entities.IrrigationZone ?? [];
  const points = entities.Point ?? [];
  const meterPointIds = new Set(
    zones
      .filter((zone) => selectedZones.has(zone.zoneId) && zone.meterPointId)
      .map((zone) => zone.meterPointId),
  );
  const meterDeviceIds = new Set(
    points
      .filter((point) => meterPointIds.has(point.pointId))
      .map((point) => point.deviceId),
  );
  const relevantPoints = points.filter((point) => {
    if (point.kind !== kind) return false;
    if (kind === "METER_TOTAL") return meterPointIds.has(point.pointId);
    if (kind === "FLOW_RATE")
      return selectedZones.has(point.zoneId) || meterDeviceIds.has(point.deviceId);
    return selectedZones.has(point.zoneId);
  });
  const pointById = new Map(relevantPoints.map((point) => [point.pointId, point]));
  const at = new Date(asOf).getTime();
  const reading = (entities.TelemetryReading ?? [])
    .filter(
      (item) =>
        pointById.has(item.pointId) &&
        item.quality === "VALID" &&
        Number.isFinite(Date.parse(item.observedAt)) &&
        Date.parse(item.observedAt) <= at,
    )
    .sort((a, b) => Date.parse(b.observedAt) - Date.parse(a.observedAt))[0];
  if (!reading) return null;

  const point = pointById.get(reading.pointId);
  return {
    point,
    reading,
    stale: at - Date.parse(reading.observedAt) > (point.staleAfterSec ?? 120) * 1000,
  };
}

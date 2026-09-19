type IconName = 'city' | 'junction' | 'building' | 'localTwin' | 'followVehicle' | 'layers' | 'reset' | 'plus' | 'minus' | 'arrow' | 'signal' | 'activity'

const paths: Record<IconName, string> = {
  city: 'M3 21V8l6-3v16M9 21V3l6 3v15M15 21V10l6-3v14M6 10v1m0 3v1m6-7v2m0 3v2m6-3v2M2 21h20',
  junction: 'M9 2v7H2m13-7v7h7M9 22v-7H2m13 7v-7h7M12 6v1m0 10v1M6 12h1m10 0h1',
  building: 'M5 21V3h11v18M16 9h4v12M8 7h5m-5 4h5m-5 4h5M3 21h19',
  localTwin: 'M12 2v3m0 14v3M2 12h3m14 0h3M19 12a7 7 0 1 1-14 0 7 7 0 0 1 14 0M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
  followVehicle: 'm3 11 2-6h14l2 6v7h-3v-3H6v3H3v-7Zm0 0h18M6 13h2m8 0h2',
  layers: 'm12 3 10 6-10 6L2 9l10-6ZM2 13l10 6 10-6M2 17l10 6 10-6',
  reset: 'M3 10a9 9 0 1 1 2 8M3 3v7h7',
  plus: 'M12 5v14M5 12h14',
  minus: 'M5 12h14',
  arrow: 'M5 12h14m-5-5 5 5-5 5',
  signal: 'M8 2h8v18H8V2Zm4 3v1m0 4v1m0 4v1m0 4v2',
  activity: 'M2 12h4l3-8 5 16 3-8h5',
}

export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>
}

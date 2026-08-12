export const de = {
  app: {
    tagline: 'Wetter entlang deiner Route',
    disclaimer:
      'Wo dich der Wind auf der Route trifft, ist gegen aufgezeichnete Fahrten geprüft. Wie stark er sich anfühlt, hängt an Hecken, Senken und Bebauung und lässt sich aus einer Vorhersage nicht zuverlässig ableiten.',
    attribution: 'Wetter von <0>Open-Meteo</0>, Karte von OpenStreetMap.',
  },

  empty: {
    analysing: 'Route wird ausgewertet …',
    prompt: 'Lade eine GPX-Datei hoch',
    hint: 'Du bekommst eine Wetterkarte deiner Route, die du über den Tag durchspielen kannst. Abfahrtszeit und Schnitt sind optional.',
  },

  controls: {
    drop: 'GPX-Datei hierher ziehen',
    dropHint: 'oder klicken zum Auswählen',
    changeFile: '{{size}} kB · andere Datei wählen',
    planRide: 'Konkrete Fahrt planen',
    planRideOn: 'Zeigt zusätzlich, was dich wo erwartet',
    planRideOff: 'Ohne das siehst du nur die Wetterkarte der Route',
    speed: 'Schnitt',
    submit: 'Route anzeigen',
    submitting: 'Vorhersage wird geholt …',
  },

  departure: {
    day: 'Tag',
    time: 'Uhrzeit',
    today: 'Heute',
    tomorrow: 'Morgen',
  },

  timeline: {
    play: 'Abspielen',
    pause: 'Pause',
    speed: 'Abspielgeschwindigkeit',
    time: 'Uhrzeit',
    yourRide: 'deine Fahrt',
  },

  wind: {
    headwind: 'Gegenwind',
    crosswind: 'Seitenwind',
    tailwind: 'Rückenwind',
    calm: 'kaum Wind',
    weak: 'schwach',
  },

  rain: {
    light: 'leichter Regen',
    moderate: 'Regen',
    heavy: 'Starkregen',
    dry: 'trocken',
    scale: 'leicht → stark',
  },

  summary: {
    onRoute: 'Auf der Route',
    onRide: 'Auf deiner Fahrt',
    at: 'um {{time}}',
    arriving: 'an {{time}}',
    meanWind: 'Wind im Mittel',
    rainRisk: 'Regenrisiko',
    rainOnRoute: 'Regen auf <0>{{km}} km</0>, bis {{peak}} mm/h',
    dryEverywhere: 'Gerade trocken auf der ganzen Route',
    dryThroughout: 'Durchgehend trocken',
    rainFrom: 'Regen ab <0>km {{km}}</0>',
    rainFromAt: 'Regen ab <0>km {{km}}</0>, gegen {{time}} Uhr',
    unsafe: 'Auf <0>{{km}} km</0> sind die Bedingungen kritisch — auf der Karte gestrichelt.',
  },

  map: {
    windLegend: 'Wind auf der Route',
    rainLegend: 'Niederschlag',
    section: 'Streckenabschnitt',
    atKm: 'bei km {{km}}',
    wind: 'Wind',
    gusts: 'Böen',
    rain: 'Regen',
    arrivalNote: 'Werte für deine geschätzte Ankunft hier.',
    unsafe: 'Kritische Bedingungen',
    noRideHint:
      'Gib Abfahrtszeit und Schnitt an, um zu sehen, was dich hier erwartet. Die Karte zeigt derweil das Wetter zur eingestellten Uhrzeit.',
  },

  theme: {
    label: 'Farbschema',
    light: 'Hell',
    system: 'System',
    dark: 'Dunkel',
  },

  language: {
    label: 'Sprache',
  },

  errors: {
    empty_upload: 'Die Datei ist leer.',
    too_large: 'Die Datei ist zu groß.',
    bad_start_time: 'Die Abfahrtszeit konnte nicht gelesen werden.',
    bad_speed: 'Der Schnitt liegt außerhalb des plausiblen Bereichs.',
    unreadable_route: 'Diese Route konnte nicht ausgewertet werden.',
    rate_limited: 'Zu viele Anfragen. Versuch es in ein paar Minuten noch einmal.',
    empty_route: 'Die GPX-Datei enthält keine verwertbare Strecke.',
    unknown: 'Die Auswertung ist fehlgeschlagen ({{status}}).',
  },
}

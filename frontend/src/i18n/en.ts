import type { de } from './de'

/** Typed against the German resource, so a missing key fails the build. */
export const en: typeof de = {
  app: {
    tagline: 'Weather along your route',
    disclaimer:
      'Where the wind meets you on a route has been checked against recorded rides. How hard it feels depends on hedges, dips and buildings, and cannot be read reliably off a forecast.',
    attribution: 'Weather by <0>Open-Meteo</0>, map by OpenStreetMap.',
  },

  empty: {
    analysing: 'Analysing route …',
    prompt: 'Upload a GPX file',
    hint: 'You get a weather map of your route that you can play through the day. Departure time and average speed are optional.',
  },

  controls: {
    drop: 'Drop a GPX file here',
    dropHint: 'or click to choose one',
    changeFile: '{{size}} kB · choose another file',
    planRide: 'Plan a specific ride',
    planRideOn: 'Also shows what to expect where',
    planRideOff: 'Without this you only get the weather map of the route',
    speed: 'Average speed',
    submit: 'Show route',
    submitting: 'Fetching the forecast …',
  },

  departure: {
    day: 'Day',
    time: 'Time',
    today: 'Today',
    tomorrow: 'Tomorrow',
  },

  timeline: {
    play: 'Play',
    pause: 'Pause',
    speed: 'Playback speed',
    time: 'Time',
    yourRide: 'your ride',
  },

  wind: {
    headwind: 'Headwind',
    crosswind: 'Crosswind',
    tailwind: 'Tailwind',
    calm: 'little wind',
    weak: 'weak',
  },

  rain: {
    light: 'light rain',
    moderate: 'rain',
    heavy: 'heavy rain',
    dry: 'dry',
    scale: 'light → heavy',
  },

  summary: {
    onRoute: 'Along the route',
    onRide: 'On your ride',
    at: 'at {{time}}',
    arriving: 'arriving {{time}}',
    meanWind: 'Average wind',
    rainRisk: 'Chance of rain',
    rainOnRoute: 'Rain over <0>{{km}} km</0>, up to {{peak}} mm/h',
    dryEverywhere: 'Dry along the whole route right now',
    dryThroughout: 'Dry throughout',
    rainFrom: 'Rain from <0>km {{km}}</0>',
    rainFromAt: 'Rain from <0>km {{km}}</0>, around {{time}}',
    unsafe: 'Conditions are severe over <0>{{km}} km</0> — dashed on the map.',
  },

  map: {
    windLegend: 'Wind along the route',
    rainLegend: 'Precipitation',
    section: 'Route section',
    atKm: 'at km {{km}}',
    wind: 'Wind',
    gusts: 'Gusts',
    rain: 'Rain',
    arrivalNote: 'Values for your estimated arrival here.',
    unsafe: 'Severe conditions',
    noRideHint:
      'Add a departure time and average speed to see what awaits you here. Meanwhile the map shows the weather at the selected time.',
  },

  theme: {
    label: 'Colour scheme',
    light: 'Light',
    system: 'System',
    dark: 'Dark',
  },

  language: {
    label: 'Language',
  },

  errors: {
    empty_upload: 'The file is empty.',
    too_large: 'The file is too large.',
    bad_start_time: 'The departure time could not be read.',
    bad_speed: 'The average speed is outside the plausible range.',
    unreadable_route: 'This route could not be analysed.',
    empty_route: 'The GPX file contains no usable track.',
    unknown: 'The analysis failed ({{status}}).',
  },
}

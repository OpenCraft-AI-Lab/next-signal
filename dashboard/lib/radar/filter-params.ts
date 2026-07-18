import {
  createParser,
  createLoader,
  createSerializer,
  parseAsStringLiteral,
  type inferParserType,
} from "nuqs/server";

import {
  DEFAULT_MIN_SCORE,
  parseBoolValue,
  parseDayValue,
  parseMinScoreValue,
  serializeBoolValue,
  SORT_OPTIONS,
} from "@/lib/radar/filter-shared";

const parseBool = createParser({
  parse: parseBoolValue,
  serialize: serializeBoolValue,
});

const parseMinScore = createParser({
  parse: parseMinScoreValue,
  serialize: String,
});

const parseDay = createParser({
  parse: parseDayValue,
  serialize: String,
});

export const radarFilterParsers = {
  sort: parseAsStringLiteral(SORT_OPTIONS).withDefault("score-desc"),
  novelOnly: parseBool.withDefault(true),
  minScore: parseMinScore.withDefault(DEFAULT_MIN_SCORE),
  day: parseDay,
  lastFeedOnly: parseBool.withDefault(false),
};

export {
  SORT_OPTIONS,
  SORT_LABELS,
  DEFAULT_MIN_SCORE,
  type RadarSort,
} from "@/lib/radar/filter-shared";

export type RadarFilters = inferParserType<typeof radarFilterParsers>;

export const loadRadarFilters = createLoader(radarFilterParsers);
export const serializeRadarFilters = createSerializer(radarFilterParsers);

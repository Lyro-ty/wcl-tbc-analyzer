"""GraphQL query strings for WCL API v2."""

RATE_LIMIT_FRAGMENT = """
    rateLimitData {
        pointsSpentThisHour
        limitPerHour
        pointsResetIn
    }
"""

CHARACTER_RANKINGS = """
query CharacterRankings($name: String!, $serverSlug: String!, $serverRegion: String!,
                         $zone: Int, $metric: CharacterRankingMetricType) {
    characterData {
        character(name: $name, serverSlug: $serverSlug, serverRegion: $serverRegion) {
            zoneRankings(zoneID: $zone, metric: $metric)
        }
    }
    RATE_LIMIT
}
"""

ZONE_RANKINGS = """
query ZoneRankings($encounterID: Int!, $className: String, $specName: String,
                   $metric: CharacterRankingMetricType, $page: Int) {
    worldData {
        encounter(id: $encounterID) {
            characterRankings(
                className: $className,
                specName: $specName,
                metric: $metric,
                page: $page
            )
        }
    }
    RATE_LIMIT
}
"""

TOP_ENCOUNTER_RANKINGS = """
query TopEncounterRankings($encounterID: Int!, $className: String, $specName: String,
                           $metric: CharacterRankingMetricType) {
    worldData {
        encounter(id: $encounterID) {
            characterRankings(
                className: $className,
                specName: $specName,
                metric: $metric,
                page: 1
            )
        }
    }
    RATE_LIMIT
}
"""

REPORT_FIGHTS = """
query ReportFights($code: String!) {
    reportData {
        report(code: $code) {
            title
            startTime
            endTime
            guild { id name }
            fights {
                id
                name
                startTime
                endTime
                kill
                encounterID
                difficulty
                fightPercentage
            }
            masterData {
                actors(type: "Player") {
                    id
                    name
                    type
                    subType
                    server
                }
            }
        }
    }
    RATE_LIMIT
}
"""

REPORT_EVENTS = """
query ReportEvents($code: String!, $fightIDs: [Int]!, $startTime: Float!,
                   $endTime: Float!, $dataType: EventDataType!) {
    reportData {
        report(code: $code) {
            events(fightIDs: $fightIDs, startTime: $startTime,
                   endTime: $endTime, dataType: $dataType) {
                data
                nextPageTimestamp
            }
        }
    }
    RATE_LIMIT
}
"""

REPORT_RANKINGS = """
query ReportRankings($code: String!, $fightIDs: [Int]!) {
    reportData {
        report(code: $code) {
            rankings(fightIDs: $fightIDs)
        }
    }
    RATE_LIMIT
}
"""

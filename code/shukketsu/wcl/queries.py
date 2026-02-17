"""GraphQL query strings for WCL API v2."""

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

SPEED_RANKINGS = """
query SpeedRankings($encounterID: Int!, $page: Int) {
    worldData {
        encounter(id: $encounterID) {
            fightRankings(metric: speed, page: $page)
        }
    }
    RATE_LIMIT
}
"""

REPORT_TABLE = """
query ReportTable($code: String!, $fightIDs: [Int]!, $dataType: TableDataType!) {
    reportData {
        report(code: $code) {
            table(fightIDs: $fightIDs, dataType: $dataType)
        }
    }
    RATE_LIMIT
}
"""

REPORT_EVENTS = """
query ReportEvents($code: String!, $startTime: Float!, $endTime: Float!,
                   $dataType: EventDataType!, $sourceID: Int) {
    reportData {
        report(code: $code) {
            events(startTime: $startTime, endTime: $endTime,
                   dataType: $dataType, sourceID: $sourceID) {
                data
                nextPageTimestamp
            }
        }
    }
    RATE_LIMIT
}
"""

GUILD_REPORTS = """
query GuildReports($guildID: Int!, $zoneID: Int, $limit: Int) {
    reportData {
        reports(guildID: $guildID, zoneID: $zoneID, limit: $limit) {
            data {
                code
                title
                startTime
                endTime
                zone { id name }
            }
        }
    }
    RATE_LIMIT
}
"""

ZONE_ENCOUNTERS = """
query ZoneEncounters($zoneID: Int!) {
    worldData {
        zone(id: $zoneID) {
            name
            encounters { id name }
        }
    }
    RATE_LIMIT
}
"""

"use client"

import { useMemo } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Loader2Icon } from "lucide-react"
import { ComposableMap, Geographies, Geography } from "react-simple-maps"
import { scaleQuantize } from "d3-scale"

// US Albers map projection
const geoUrl = "https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json"

// FIPS to state abbreviation mapping
const fipsToState: Record<string, string> = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA",
    "08": "CO", "09": "CT", "10": "DE", "11": "DC", "12": "FL", "13": "GA",
    "15": "HI", "16": "ID", "17": "IL", "18": "IN", "19": "IA",
    "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD",
    "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO",
    "30": "MT", "31": "NE", "32": "NV", "33": "NH", "34": "NJ",
    "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH",
    "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC",
    "46": "SD", "47": "TN", "48": "TX", "49": "UT", "50": "VT",
    "51": "VA", "53": "WA", "54": "WV", "55": "WI", "56": "WY",
}

interface StateCount {
    state: string
    count: number
}

interface USMapChartProps {
    data: StateCount[] | undefined
    isLoading?: boolean
    isError?: boolean
    title?: string
}

export function USMapChart({
    data,
    isLoading = false,
    isError = false,
    title = "Cases by State",
}: USMapChartProps) {
    // Create a lookup map for quick access
    const stateCounts = useMemo(() => {
        const map = new Map<string, number>()
        if (data) {
            data.forEach(d => map.set(d.state, d.count))
        }
        return map
    }, [data])

    // Calculate color scale
    const colorScale = useMemo(() => {
        if (!data || data.length === 0) return () => "#f0f0f0"
        const counts = data.map(d => d.count)
        const max = Math.max(...counts)
        return scaleQuantize<string>()
            .domain([0, max])
            .range([
                "#f0f9ff",
                "#bae6fd",
                "#7dd3fc",
                "#38bdf8",
                "#0ea5e9",
                "#0284c7",
            ])
    }, [data])

    if (isLoading) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle>{title}</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="flex h-[300px] items-center justify-center">
                        <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
                    </div>
                </CardContent>
            </Card>
        )
    }

    if (isError) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle>{title}</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="flex h-[300px] items-center justify-center text-destructive">
                        Unable to load geographic data
                    </div>
                </CardContent>
            </Card>
        )
    }

    if (!data || data.length === 0) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle>{title}</CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="flex h-[300px] items-center justify-center text-muted-foreground">
                        No geographic data available
                    </div>
                </CardContent>
            </Card>
        )
    }

    const totalCases = data.reduce((sum, d) => sum + d.count, 0)

    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle>{title}</CardTitle>
                <span className="text-sm text-muted-foreground">
                    Total: {totalCases.toLocaleString()} cases
                </span>
            </CardHeader>
            <CardContent>
                <div className="relative">
                    <ComposableMap
                        projection="geoAlbersUsa"
                        projectionConfig={{ scale: 800 }}
                        className="w-full h-auto"
                    >
                        <Geographies geography={geoUrl}>
                            {({ geographies }) =>
                                geographies.map(geo => {
                                    const fips = geo.id
                                    const stateAbbr = fipsToState[fips] || ""
                                    const count = stateCounts.get(stateAbbr) || 0
                                    const fillColor = count > 0 ? colorScale(count) : "#f5f5f5"

                                    return (
                                        <Geography
                                            key={geo.rsmKey}
                                            geography={geo}
                                            fill={fillColor}
                                            stroke="#d4d4d4"
                                            strokeWidth={0.5}
                                            style={{
                                                default: { outline: "none" },
                                                hover: {
                                                    fill: "#60a5fa",
                                                    outline: "none",
                                                    cursor: "pointer",
                                                },
                                                pressed: { outline: "none" },
                                            }}
                                            onMouseEnter={() => {
                                                // Could add tooltip state here
                                            }}
                                        />
                                    )
                                })
                            }
                        </Geographies>
                    </ComposableMap>

                    {/* Legend */}
                    <div className="mt-4 flex items-center justify-center gap-2 text-xs">
                        <span className="text-muted-foreground">Low</span>
                        <div className="flex">
                            {["#f0f9ff", "#bae6fd", "#7dd3fc", "#38bdf8", "#0ea5e9", "#0284c7"].map((color) => (
                                <div
                                    key={color}
                                    className="h-3 w-6"
                                    style={{ backgroundColor: color }}
                                />
                            ))}
                        </div>
                        <span className="text-muted-foreground">High</span>
                    </div>

                    {/* Top states list */}
                    <div className="mt-4 grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
                        {data.slice(0, 4).map(d => (
                            <div key={d.state} className="flex items-center justify-between rounded bg-muted/30 px-2 py-1">
                                <span className="font-medium">{d.state}</span>
                                <span className="text-muted-foreground">{d.count}</span>
                            </div>
                        ))}
                    </div>
                </div>
            </CardContent>
        </Card>
    )
}

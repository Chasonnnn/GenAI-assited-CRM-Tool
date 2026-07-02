"use client"

import { useSyncExternalStore } from "react"

const MINUTE = 60_000
const nowListeners = new Set<() => void>()
let nowSnapshot = getCurrentMinuteTimestamp()
let nowTimer: ReturnType<typeof setInterval> | null = null

function getCurrentMinuteTimestamp() {
    return Math.floor(Date.now() / MINUTE) * MINUTE
}

function subscribeNow(listener: () => void) {
    nowListeners.add(listener)
    if (nowTimer === null) {
        nowTimer = setInterval(() => {
            nowSnapshot = getCurrentMinuteTimestamp()
            for (const notify of nowListeners) notify()
        }, MINUTE)
    }

    return () => {
        nowListeners.delete(listener)
        if (nowListeners.size === 0 && nowTimer !== null) {
            clearInterval(nowTimer)
            nowTimer = null
        }
    }
}

function getNowSnapshot() {
    const currentMinute = getCurrentMinuteTimestamp()
    if (currentMinute !== nowSnapshot) {
        nowSnapshot = currentMinute
    }
    return nowSnapshot
}

function getServerNowSnapshot() {
    return null
}

export function useCurrentMinuteTimestamp() {
    return useSyncExternalStore(subscribeNow, getNowSnapshot, getServerNowSnapshot)
}

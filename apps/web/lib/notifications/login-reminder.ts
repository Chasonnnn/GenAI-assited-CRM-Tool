const LOGIN_NOTIFICATION_REMINDER_KEY = "notification_login_reminder_pending"

export function armLoginNotificationReminder() {
    try {
        sessionStorage.setItem(LOGIN_NOTIFICATION_REMINDER_KEY, "1")
    } catch {
        // The reminder is optional when browser storage is unavailable.
    }
}

export function consumeLoginNotificationReminder() {
    try {
        const isPending = sessionStorage.getItem(LOGIN_NOTIFICATION_REMINDER_KEY) === "1"
        sessionStorage.removeItem(LOGIN_NOTIFICATION_REMINDER_KEY)
        return isPending
    } catch {
        return false
    }
}

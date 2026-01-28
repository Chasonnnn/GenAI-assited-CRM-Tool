resource "google_billing_budget" "monthly" {
  count = var.billing_budget_enabled && local.alerting_enabled ? 1 : 0

  billing_account = var.billing_account_id
  display_name    = "CRM monthly budget"

  budget_filter {
    projects = ["projects/${var.project_id}"]
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(var.billing_budget_amount_usd)
      nanos         = 0
    }
  }

  dynamic "threshold_rules" {
    for_each = var.billing_budget_thresholds
    content {
      threshold_percent = threshold_rules.value
    }
  }

  all_updates_rule {
    monitoring_notification_channels = local.alert_notification_channels
    disable_default_iam_recipients   = true
  }
}
